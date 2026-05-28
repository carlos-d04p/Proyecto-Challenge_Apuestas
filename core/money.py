from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


MONEY_QUANT = Decimal("0.0001")


def normalize_money(value):
    if isinstance(value, float):
        raise TypeError("Money values must not be float.")

    try:
        amount = Decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid money amount.") from exc

    if amount <= Decimal("0.0000"):
        raise ValueError("Money amount must be greater than zero.")

    return amount
