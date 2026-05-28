from decimal import Decimal

from django.db.models import DecimalField, Q, Sum
from django.db.models.functions import Coalesce

from apps.wallet.models import LedgerAccount, LedgerDirection, LedgerEntry


ZERO_MONEY = Decimal("0.0000")
MONEY_QUANT = Decimal("0.0001")


def get_account_balance(user, account):
    totals = LedgerEntry.objects.filter(
        account=account,
        account_owner=user,
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


def get_wallet_balance(user):
    return get_account_balance(user, LedgerAccount.USER_WALLET)


def get_wallet_account_balances(user):
    return {
        "available": get_account_balance(user, LedgerAccount.USER_WALLET),
        "pending_bets": get_account_balance(user, LedgerAccount.PENDING_BETS),
        "bonus": get_account_balance(user, LedgerAccount.BONUS),
    }


ACCOUNT_LABELS = {
    LedgerAccount.USER_WALLET: "Saldo disponible",
    LedgerAccount.PENDING_BETS: "Fichas pendientes en apuestas",
    LedgerAccount.BONUS: "Bonos",
}


TRANSACTION_LABELS = {
    "DEPOSIT": "Recarga simulada",
    "WITHDRAWAL": "Retiro simulado",
    "BET_REFUND": "Devolucion o ajuste",
    "BET_PAYOUT": "Devolucion o ajuste",
    "CASHOUT": "Devolucion o ajuste",
}


def get_operation_label(entry):
    kind = entry.transaction.kind
    if kind == "INTERNAL_TRANSFER":
        if entry.account == LedgerAccount.PENDING_BETS:
            return "Fichas pendientes en apuestas"
        if entry.account == LedgerAccount.BONUS:
            return "Bono"
        return "Transferencia interna"
    if kind == "BET_PLACEMENT":
        return "Fichas pendientes en apuestas"
    if kind == "BET_LOSS":
        return "Ajuste"
    return TRANSACTION_LABELS.get(kind, kind.replace("_", " ").title())


def get_wallet_movements(user, limit=25):
    entries = (
        LedgerEntry.objects.select_related("transaction")
        .filter(
            account__in=[
                LedgerAccount.USER_WALLET,
                LedgerAccount.PENDING_BETS,
                LedgerAccount.BONUS,
            ],
            account_owner=user,
        )
        .order_by("-created_at", "-id")[:limit]
    )

    movements = []
    for entry in entries:
        signed_amount = entry.amount
        if entry.direction == LedgerDirection.DEBIT:
            signed_amount = -signed_amount
        movements.append(
            {
                "date": entry.created_at,
                "operation_type": get_operation_label(entry),
                "account": entry.account,
                "account_label": ACCOUNT_LABELS.get(entry.account, entry.account),
                "amount": signed_amount.quantize(MONEY_QUANT),
                "status": "Completado",
                "transaction_id": str(entry.transaction_id),
                "reference": str(entry.transaction_id)[:8],
            }
        )
    return movements
