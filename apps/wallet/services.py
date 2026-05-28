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
)
from apps.wallet.selectors import get_wallet_balance
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

    with db_transaction.atomic():
        locked_user = _lock_user(user)
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
        return transaction


def withdraw_simulated(user, amount, created_by, idempotency_key=None):
    amount = normalize_money(amount)

    with db_transaction.atomic():
        locked_user = _lock_user(user)
        balance = get_wallet_balance(locked_user)
        if balance < amount:
            raise ValueError("Insufficient wallet balance.")

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
        return transaction


def internal_transfer(
    source_account,
    target_account,
    owner,
    amount,
    created_by,
    description=None,
):
    amount = normalize_money(amount)
    source_account = _validate_account(source_account)
    target_account = _validate_account(target_account)

    with db_transaction.atomic():
        locked_owner = _lock_user(owner)

        if source_account in USER_OWNED_ACCOUNTS:
            source_balance = _get_account_balance(locked_owner, source_account)
            if source_balance < amount:
                raise ValueError("Insufficient source account balance.")

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
        return transaction


def _lock_user(user):
    return get_user_model().objects.select_for_update().get(pk=user.pk)


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


__all__ = [
    "deposit_simulated",
    "get_wallet_balance",
    "internal_transfer",
    "withdraw_simulated",
]
