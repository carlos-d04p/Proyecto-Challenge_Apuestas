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
