from decimal import Decimal
from django.core.exceptions import ValidationError

from django.contrib.auth import get_user_model
from django.db import transaction as db_transaction
from django.db.models import DecimalField, Q, Sum
from django.db.models.functions import Coalesce

from apps.compliance.services import append_audit_event
from apps.wallet.models import (
    LedgerAccount,
    LedgerDirection,
    LedgerEntry,
    Transaction,
    TransactionKind,
    WalletIdempotencyRecord,
)
from apps.wallet.selectors import get_wallet_balance, get_account_balance
from core.idempotency import IdempotencyConflict, build_request_hash
from core.money import normalize_money


ZERO_MONEY = Decimal("0.0000")
MONEY_QUANT = Decimal("0.0001")
USER_OWNED_ACCOUNTS = {
    LedgerAccount.USER_WALLET,
    LedgerAccount.PENDING_BETS,
    LedgerAccount.BONUS,
}
WALLET_DEPOSIT_CREATED = "WALLET_DEPOSIT_CREATED"
WALLET_WITHDRAWAL_CREATED = "WALLET_WITHDRAWAL_CREATED"
WALLET_INTERNAL_TRANSFER_CREATED = "WALLET_INTERNAL_TRANSFER_CREATED"


def deposit_simulated(user, amount, created_by, idempotency_key=None):
    amount = normalize_money(amount)

    # --- GUARD: Verificación de correo electrónico obligatoria ---
    if not getattr(user, 'is_email_verified', False):
        raise PermissionError(
            "Debes verificar tu correo electrónico antes de realizar depósitos. "
            "Revisa tu bandeja de entrada."
        )

    # --- GUARD: Estado KYC debe ser VERIFIED ---
    try:
        perfil = user.perfil_kyc
        if perfil.status == "BLOCKED":
            raise PermissionError("Tu cuenta está bloqueada. Contacta al soporte.")
        if perfil.status == "SELF_EXCLUDED":
            raise PermissionError("Tu cuenta está en autoexclusión. No puedes realizar depósitos.")
        if perfil.status != "VERIFIED":
            raise PermissionError(
                "Tu perfil KYC aún no ha sido aprobado. "
                "Un administrador debe verificar tu identidad antes de que puedas depositar."
            )
    except user.__class__.perfil_kyc.RelatedObjectDoesNotExist:
        raise PermissionError(
            "No tienes un perfil KYC registrado. "
            "Completa tu verificación de identidad en tu perfil."
        )

    # --- REGLA DE NEGOCIO: Límites de Depósito simulado ---
    if amount < Decimal("30.0000") or amount > Decimal("30000.0000"):
        raise ValidationError("El depósito debe estar entre 30.0000 y 30,000.0000 fichas.")


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

        _check_deposit_limits(locked_user, amount)

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
        _emit_wallet_audit_event(
            event_type=WALLET_DEPOSIT_CREATED,
            transaction=transaction,
            user=locked_user,
            amount=amount,
        )
        return transaction


def withdraw_simulated(user, amount, created_by, idempotency_key=None):
    amount = normalize_money(amount)

    # --- REGLAS DE NEGOCIO: Límites y KYC ---
    if amount < Decimal("100.0000"):
        raise ValidationError("El retiro mínimo es de 100.0000 fichas.")
    
    if not getattr(user, 'is_email_verified', False):
        raise PermissionError("Debes verificar tu cuenta (KYC) para poder realizar retiros.")

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

        # El saldo en USER_WALLET ya está separado de los bonos (BONUS), por lo tanto, es totalmente retirable.
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
        _emit_wallet_audit_event(
            event_type=WALLET_WITHDRAWAL_CREATED,
            transaction=transaction,
            user=locked_user,
            amount=amount,
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
        _emit_wallet_audit_event(
            event_type=WALLET_INTERNAL_TRANSFER_CREATED,
            transaction=transaction,
            user=locked_owner,
            amount=amount,
        )
        return transaction


def record_bet_placement(user, amount, bet_id, use_bonus=False):
    """
    Descuenta de USER_WALLET y/o BONUS y abona a PENDING_BETS.
    Si use_bonus=True, prioriza el BONUS.
    """
    amount = normalize_money(amount)
    
    with db_transaction.atomic():
        locked_user = _lock_users_in_order(user)[user.pk]
        
        wallet_balance = get_account_balance(locked_user, LedgerAccount.USER_WALLET)
        bonus_balance = get_account_balance(locked_user, LedgerAccount.BONUS)
        
        if use_bonus:
            if wallet_balance + bonus_balance < amount:
                raise ValueError("Saldo total insuficiente para realizar la apuesta (incluyendo bonos).")
            from_bonus = min(amount, bonus_balance)
            from_wallet = amount - from_bonus
        else:
            if wallet_balance < amount:
                raise ValueError("Saldo insuficiente en tu billetera principal (marca 'Usar bono' si deseas usarlo).")
            from_wallet = amount
            from_bonus = Decimal("0.0000")
        
        transaction = Transaction.objects.create(
            kind=TransactionKind.BET_PLACEMENT,
            description=f"Bet placement for bet {bet_id}",
            created_by=locked_user,
        )
        
        entries = []
        if from_wallet > Decimal("0.0000"):
            entries.append(
                _create_entry(
                    transaction=transaction,
                    account=LedgerAccount.USER_WALLET,
                    account_owner=locked_user,
                    direction=LedgerDirection.DEBIT,
                    amount=from_wallet,
                )
            )
            
        if from_bonus > Decimal("0.0000"):
            entries.append(
                _create_entry(
                    transaction=transaction,
                    account=LedgerAccount.BONUS,
                    account_owner=locked_user,
                    direction=LedgerDirection.DEBIT,
                    amount=from_bonus,
                )
            )
            
        entries.append(
            _create_entry(
                transaction=transaction,
                account=LedgerAccount.PENDING_BETS,
                account_owner=locked_user,
                direction=LedgerDirection.CREDIT,
                amount=amount,
            )
        )
        
        _validate_transaction_is_balanced(entries)
        return transaction


def record_bet_settlement_won(user, stake, payout, bet_id):
    """
    Mueve el stake de PENDING_BETS a HOUSE y el payout de HOUSE a USER_WALLET.
    """
    stake = normalize_money(stake)
    payout = normalize_money(payout)
    
    with db_transaction.atomic():
        locked_user = _lock_users_in_order(user)[user.pk]
        
        transaction = Transaction.objects.create(
            kind=TransactionKind.BET_PAYOUT,
            description=f"Bet payout for bet {bet_id}",
            created_by=locked_user,
        )
        
        entries = [
            # 1. Stake from pending bets to house
            _create_entry(
                transaction=transaction,
                account=LedgerAccount.PENDING_BETS,
                account_owner=locked_user,
                direction=LedgerDirection.DEBIT,
                amount=stake,
            ),
            _create_entry(
                transaction=transaction,
                account=LedgerAccount.HOUSE,
                account_owner=None,
                direction=LedgerDirection.CREDIT,
                amount=stake,
            ),
            # 2. Payout from house to user wallet
            _create_entry(
                transaction=transaction,
                account=LedgerAccount.HOUSE,
                account_owner=None,
                direction=LedgerDirection.DEBIT,
                amount=payout,
            ),
            _create_entry(
                transaction=transaction,
                account=LedgerAccount.USER_WALLET,
                account_owner=locked_user,
                direction=LedgerDirection.CREDIT,
                amount=payout,
            ),
        ]
        _validate_transaction_is_balanced(entries)
        return transaction


def record_bet_settlement_lost(user, stake, bet_id):
    """
    Mueve el stake de PENDING_BETS a HOUSE.
    """
    stake = normalize_money(stake)
    
    with db_transaction.atomic():
        locked_user = _lock_users_in_order(user)[user.pk]
        
        transaction = Transaction.objects.create(
            kind=TransactionKind.BET_LOSS,
            description=f"Bet lost for bet {bet_id}",
            created_by=locked_user,
        )
        entries = [
            _create_entry(
                transaction=transaction,
                account=LedgerAccount.PENDING_BETS,
                account_owner=locked_user,
                direction=LedgerDirection.DEBIT,
                amount=stake,
            ),
            _create_entry(
                transaction=transaction,
                account=LedgerAccount.HOUSE,
                account_owner=None,
                direction=LedgerDirection.CREDIT,
                amount=stake,
            ),
        ]
        _validate_transaction_is_balanced(entries)
        return transaction


def record_bet_settlement_void(user, stake, bet_id):
    """
    Devuelve el stake de PENDING_BETS a USER_WALLET (Refund).
    """
    stake = normalize_money(stake)
    
    with db_transaction.atomic():
        locked_user = _lock_users_in_order(user)[user.pk]
        
        transaction = Transaction.objects.create(
            kind=TransactionKind.BET_REFUND,
            description=f"Bet void for bet {bet_id}",
            created_by=locked_user,
        )
        entries = [
            _create_entry(
                transaction=transaction,
                account=LedgerAccount.PENDING_BETS,
                account_owner=locked_user,
                direction=LedgerDirection.DEBIT,
                amount=stake,
            ),
            _create_entry(
                transaction=transaction,
                account=LedgerAccount.USER_WALLET,
                account_owner=locked_user,
                direction=LedgerDirection.CREDIT,
                amount=stake,
            ),
        ]
        _validate_transaction_is_balanced(entries)
        return transaction


def record_bet_cashout(user, stake, payout, bet_id):
    """
    Igual que won pero tipo CASHOUT.
    """
    stake = normalize_money(stake)
    payout = normalize_money(payout)
    
    with db_transaction.atomic():
        locked_user = _lock_users_in_order(user)[user.pk]
        
        transaction = Transaction.objects.create(
            kind=TransactionKind.CASHOUT,
            description=f"Cashout for bet {bet_id}",
            created_by=locked_user,
        )
        
        entries = [
            _create_entry(
                transaction=transaction,
                account=LedgerAccount.PENDING_BETS,
                account_owner=locked_user,
                direction=LedgerDirection.DEBIT,
                amount=stake,
            ),
            _create_entry(
                transaction=transaction,
                account=LedgerAccount.HOUSE,
                account_owner=None,
                direction=LedgerDirection.CREDIT,
                amount=stake,
            ),
            _create_entry(
                transaction=transaction,
                account=LedgerAccount.HOUSE,
                account_owner=None,
                direction=LedgerDirection.DEBIT,
                amount=payout,
            ),
            _create_entry(
                transaction=transaction,
                account=LedgerAccount.USER_WALLET,
                account_owner=locked_user,
                direction=LedgerDirection.CREDIT,
                amount=payout,
            ),
        ]
        _validate_transaction_is_balanced(entries)
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


def _emit_wallet_audit_event(*, event_type, transaction, user, amount):
    append_audit_event(
        event_type=event_type,
        payload={
            "transaction_id": str(transaction.id),
            "user_id": str(user.pk),
            "amount": str(amount),
            "kind": transaction.kind,
            "timestamp": transaction.created_at.isoformat(),
        },
    )


def _check_deposit_limits(user, amount):
    try:
        kyc = user.perfil_kyc
    except AttributeError:
        return
    except Exception:
        return

    if not kyc:
        return

    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Sum
    from apps.compliance.models import SuspiciousActivity
    from apps.compliance.services import append_audit_event

    now = timezone.now()

    def get_deposited_since(dt):
        deposits = Transaction.objects.filter(
            created_by=user,
            kind=TransactionKind.DEPOSIT,
            created_at__gte=dt
        )
        return LedgerEntry.objects.filter(
            transaction__in=deposits,
            account=LedgerAccount.USER_WALLET,
            direction=LedgerDirection.CREDIT
        ).aggregate(total=Sum('amount'))['total'] or Decimal("0.0000")

    # 1. Limite Diario
    if kyc.daily_deposit_limit is not None:
        daily_total = get_deposited_since(now - timedelta(days=1))
        if daily_total + amount > kyc.daily_deposit_limit:
            evidence = {
                "monto_intento": str(amount),
                "limite_diario": str(kyc.daily_deposit_limit),
                "depositado_24h": str(daily_total),
            }
            activity = SuspiciousActivity.objects.create(
                user=user,
                reason=SuspiciousActivity.Reason.LIMIT_EXCEEDED,
                evidence=evidence,
                status=SuspiciousActivity.Status.PENDIENTE
            )
            append_audit_event(
                event_type="SUSPICIOUS_ACTIVITY_DETECTED",
                payload={
                    "activity_id": activity.id,
                    "reason": activity.reason,
                    "user_id": str(user.id),
                    "username": user.username,
                    "evidence": evidence
                }
            )
            raise ValueError(f"Excede el limite de deposito diario ({kyc.daily_deposit_limit}).")

    # 2. Limite Semanal
    if kyc.weekly_deposit_limit is not None:
        weekly_total = get_deposited_since(now - timedelta(days=7))
        if weekly_total + amount > kyc.weekly_deposit_limit:
            evidence = {
                "monto_intento": str(amount),
                "limite_semanal": str(kyc.weekly_deposit_limit),
                "depositado_7d": str(weekly_total),
            }
            activity = SuspiciousActivity.objects.create(
                user=user,
                reason=SuspiciousActivity.Reason.LIMIT_EXCEEDED,
                evidence=evidence,
                status=SuspiciousActivity.Status.PENDIENTE
            )
            append_audit_event(
                event_type="SUSPICIOUS_ACTIVITY_DETECTED",
                payload={
                    "activity_id": activity.id,
                    "reason": activity.reason,
                    "user_id": str(user.id),
                    "username": user.username,
                    "evidence": evidence
                }
            )
            raise ValueError(f"Excede el limite de deposito semanal ({kyc.weekly_deposit_limit}).")

    # 3. Limite Mensual
    if kyc.monthly_deposit_limit is not None:
        monthly_total = get_deposited_since(now - timedelta(days=30))
        if monthly_total + amount > kyc.monthly_deposit_limit:
            evidence = {
                "monto_intento": str(amount),
                "limite_mensual": str(kyc.monthly_deposit_limit),
                "depositado_30d": str(monthly_total),
            }
            activity = SuspiciousActivity.objects.create(
                user=user,
                reason=SuspiciousActivity.Reason.LIMIT_EXCEEDED,
                evidence=evidence,
                status=SuspiciousActivity.Status.PENDIENTE
            )
            append_audit_event(
                event_type="SUSPICIOUS_ACTIVITY_DETECTED",
                payload={
                    "activity_id": activity.id,
                    "reason": activity.reason,
                    "user_id": str(user.id),
                    "username": user.username,
                    "evidence": evidence
                }
            )
            raise ValueError(f"Excede el limite de deposito mensual ({kyc.monthly_deposit_limit}).")



__all__ = [
    "deposit_simulated",
    "get_wallet_balance",
    "internal_transfer",
    "record_bet_placement",
    "record_bet_settlement_won",
    "record_bet_settlement_lost",
    "record_bet_settlement_void",
    "record_bet_cashout",
    "WALLET_DEPOSIT_CREATED",
    "WALLET_WITHDRAWAL_CREATED",
    "WALLET_INTERNAL_TRANSFER_CREATED",
    "withdraw_simulated",
]
