from decimal import Decimal

import pytest

from core.money import normalize_money


FOUR_DECIMAL_EXPONENT = Decimal("0.0001")


@pytest.mark.parametrize(
    ("raw_amount", "expected"),
    [
        ("10", Decimal("10.0000")),
        ("10.5", Decimal("10.5000")),
        ("10.5000", Decimal("10.5000")),
        (Decimal("7.1"), Decimal("7.1000")),
        (1, Decimal("1.0000")),
    ],
)
def test_normalize_money_returns_decimal_with_four_places(raw_amount, expected):
    amount = normalize_money(raw_amount)

    assert amount == expected
    assert isinstance(amount, Decimal)
    assert amount.as_tuple().exponent == FOUR_DECIMAL_EXPONENT.as_tuple().exponent


@pytest.mark.parametrize("raw_amount", [10.5, 0.1])
def test_normalize_money_rejects_float_amounts(raw_amount):
    with pytest.raises(TypeError):
        normalize_money(raw_amount)


@pytest.mark.parametrize(
    "raw_amount",
    ["-0.0001", "-10.0000", Decimal("-1.0000"), -1],
)
def test_normalize_money_rejects_negative_amounts(raw_amount):
    with pytest.raises(ValueError):
        normalize_money(raw_amount)


@pytest.mark.parametrize(
    "raw_amount",
    ["0", "0.0000", Decimal("0.0000"), 0],
)
def test_normalize_money_rejects_zero_amounts(raw_amount):
    with pytest.raises(ValueError):
        normalize_money(raw_amount)


def test_normalize_money_accepts_valid_numeric_string():
    assert normalize_money("10.5000") == Decimal("10.5000")


@pytest.mark.parametrize("raw_amount", ["3", "3.2", Decimal("3.2000")])
def test_normalize_money_result_always_keeps_four_decimal_places(raw_amount):
    amount = normalize_money(raw_amount)

    assert amount.as_tuple().exponent == -4
