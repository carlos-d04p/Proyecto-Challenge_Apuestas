from decimal import Decimal

from django.db.models import DecimalField, Q, Sum
from django.db.models.functions import Coalesce

from apps.wallet.models import LedgerAccount, LedgerDirection, LedgerEntry


ZERO_MONEY = Decimal("0.0000")
MONEY_QUANT = Decimal("0.0001")


def get_wallet_balance(user):
    totals = LedgerEntry.objects.filter(
        account=LedgerAccount.USER_WALLET,
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
