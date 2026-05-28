from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction as db_transaction
from django.db.models import DecimalField, Q, Sum
from django.db.models.functions import Coalesce

from apps.wallet.models import (
    LedgerAccount,
    LedgerDirection,
    LedgerEntry,
    Transaction,
    TransactionKind,
    WalletIdempotencyRecord,
)
from apps.wallet.selectors import get_wallet_balance
from core.idempotency import IdempotencyConflict, build_request_hash
from core.money import normalize_money


ZERO_MONEY = Decimal("0.0000")
MONEY_QUANT = Decimal("0.0001")
USER_OWNED_ACCOUNTS = {
    LedgerAccount.USER_WALLET,
    LedgerAccount.PENDING_BETS,
    LedgerAccount.BONUS,
}


def deposit_simulated(user, amount, created_by, idempotency_key=None):
    amount = normalize_money(amount)
    payload = _build_payload(
        operation="deposit_simulated",
        user=user,
        amount=amount,
    )

    with db_transaction.atomic():
        locked_user = _lock_users_in_order(user)[user.pk]
        existing_transaction = _get_existing_idempotent_transaction(
            user=locked_user,
            idempotency_key=idempotency_key,
            payload=payload,
        )
        if existing_transaction is not None:
            return existing_transaction

        transaction = Transaction.objects.create(
            kind=TransactionKind.DEPOSIT,
            created_by=created_by,
        )
        entries = [
            _create_entry(
                transaction=transaction,
                account=LedgerAccount.HOUSE,
                account_owner=None,
                direction=LedgerDirection.DEBIT,
                amount=amount,
            ),
            _create_entry(
                transaction=transaction,
                account=LedgerAccount.USER_WALLET,
                account_owner=locked_user,
                direction=LedgerDirection.CREDIT,
                amount=amount,
            ),
        ]
        _validate_transaction_is_balanced(entries)
        _record_idempotency(
            user=locked_user,
            idempotency_key=idempotency_key,
            payload=payload,
            transaction=transaction,
        )
        return transaction


def withdraw_simulated(user, amount, created_by, idempotency_key=None):
    amount = normalize_money(amount)
    payload = _build_payload(
        operation="withdraw_simulated",
        user=user,
        amount=amount,
    )

    with db_transaction.atomic():
        locked_user = _lock_users_in_order(user)[user.pk]
        existing_transaction = _get_existing_idempotent_transaction(
            user=locked_user,
            idempotency_key=idempotency_key,
            payload=payload,
        )
        if existing_transaction is not None:
            return existing_transaction

        _ensure_sufficient_balance(
            owner=locked_user,
            account=LedgerAccount.USER_WALLET,
            amount=amount,
            message="Insufficient wallet balance.",
        )

        transaction = Transaction.objects.create(
            kind=TransactionKind.WITHDRAWAL,
            created_by=created_by,
        )
        entries = [
            _create_entry(
                transaction=transaction,
                account=LedgerAccount.USER_WALLET,
                account_owner=locked_user,
                direction=LedgerDirection.DEBIT,
                amount=amount,
            ),
            _create_entry(
                transaction=transaction,
                account=LedgerAccount.HOUSE,
                account_owner=None,
                direction=LedgerDirection.CREDIT,
                amount=amount,
            ),
        ]
        _validate_transaction_is_balanced(entries)
        _record_idempotency(
            user=locked_user,
            idempotency_key=idempotency_key,
            payload=payload,
            transaction=transaction,
        )
        return transaction


def internal_transfer(
    source_account,
    target_account,
    owner,
    amount,
    created_by,
    description=None,
    idempotency_key=None,
):
    amount = normalize_money(amount)
    source_account = _validate_account(source_account)
    target_account = _validate_account(target_account)
    payload = _build_payload(
        operation="internal_transfer",
        user=owner,
        amount=amount,
        source_account=source_account,
        target_account=target_account,
        description=description or "",
    )

    with db_transaction.atomic():
        locked_owner = _lock_users_in_order(owner)[owner.pk]
        existing_transaction = _get_existing_idempotent_transaction(
            user=locked_owner,
            idempotency_key=idempotency_key,
            payload=payload,
        )
        if existing_transaction is not None:
            return existing_transaction

        if source_account in USER_OWNED_ACCOUNTS:
            _ensure_sufficient_balance(
                owner=locked_owner,
                account=source_account,
                amount=amount,
                message="Insufficient source account balance.",
            )

        transaction = Transaction.objects.create(
            kind=TransactionKind.INTERNAL_TRANSFER,
            description=description or "",
            created_by=created_by,
        )
        entries = [
            _create_entry(
                transaction=transaction,
                account=source_account,
                account_owner=_account_owner(source_account, locked_owner),
                direction=LedgerDirection.DEBIT,
                amount=amount,
            ),
            _create_entry(
                transaction=transaction,
                account=target_account,
                account_owner=_account_owner(target_account, locked_owner),
                direction=LedgerDirection.CREDIT,
                amount=amount,
            ),
        ]
        _validate_transaction_is_balanced(entries)
        _record_idempotency(
            user=locked_owner,
            idempotency_key=idempotency_key,
            payload=payload,
            transaction=transaction,
        )
        return transaction


def _lock_users_in_order(*users):
    user_ids = sorted({user.pk for user in users}, key=str)
    locked_users = (
        get_user_model()
        .objects.select_for_update()
        .filter(pk__in=user_ids)
        .order_by("pk")
    )
    return {locked_user.pk: locked_user for locked_user in locked_users}


def _create_entry(*, transaction, account, account_owner, direction, amount):
    return LedgerEntry.objects.create(
        transaction=transaction,
        account=account,
        account_owner=account_owner,
        direction=direction,
        amount=amount,
    )


def _get_account_balance(owner, account):
    totals = LedgerEntry.objects.filter(
        account=account,
        account_owner=owner,
    ).aggregate(
        credits=Coalesce(
            Sum("amount", filter=Q(direction=LedgerDirection.CREDIT)),
            ZERO_MONEY,
            output_field=DecimalField(max_digits=18, decimal_places=4),
        ),
        debits=Coalesce(
            Sum("amount", filter=Q(direction=LedgerDirection.DEBIT)),
            ZERO_MONEY,
            output_field=DecimalField(max_digits=18, decimal_places=4),
        ),
    )
    return (totals["credits"] - totals["debits"]).quantize(MONEY_QUANT)


def _ensure_sufficient_balance(*, owner, account, amount, message):
    balance = _get_account_balance(owner, account)
    if balance < amount:
        raise ValueError(message)


def _validate_transaction_is_balanced(entries):
    if len(entries) < 2:
        raise ValueError("A transaction requires at least two ledger entries.")

    balance = ZERO_MONEY
    for entry in entries:
        if entry.direction == LedgerDirection.CREDIT:
            balance += entry.amount
        elif entry.direction == LedgerDirection.DEBIT:
            balance -= entry.amount
        else:
            raise ValueError("Invalid ledger direction.")

    if balance.quantize(MONEY_QUANT) != ZERO_MONEY:
        raise ValueError("Transaction is not balanced.")


def _validate_account(account):
    allowed_accounts = {choice.value for choice in LedgerAccount}
    if account not in allowed_accounts:
        raise ValueError("Invalid ledger account.")
    return account


def _account_owner(account, owner):
    if account == LedgerAccount.HOUSE:
        return None
    return owner


def _build_payload(operation, user, amount, **extra):
    payload = {
        "operation": operation,
        "user_id": str(user.pk),
        "amount": str(amount),
    }
    payload.update(extra)
    return payload


def _get_existing_idempotent_transaction(*, user, idempotency_key, payload):
    if not idempotency_key:
        return None

    request_hash = build_request_hash(payload)
    record = (
        WalletIdempotencyRecord.objects.select_for_update()
        .select_related("transaction")
        .filter(user=user, key=idempotency_key)
        .first()
    )
    if record is None:
        return None
    if record.request_hash != request_hash:
        raise IdempotencyConflict("Idempotency key was reused with a different payload.")
    return record.transaction


def _record_idempotency(*, user, idempotency_key, payload, transaction):
    if not idempotency_key:
        return

    WalletIdempotencyRecord.objects.create(
        user=user,
        key=idempotency_key,
        request_hash=build_request_hash(payload),
        transaction=transaction,
    )


__all__ = [
    "deposit_simulated",
    "get_wallet_balance",
    "internal_transfer",
    "withdraw_simulated",
]
