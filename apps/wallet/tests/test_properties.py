import uuid
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from hypothesis import given, settings
from hypothesis import strategies as st

from apps.wallet.models import Transaction
from apps.wallet.selectors import get_wallet_balance
from apps.wallet.services import (
    deposit_simulated,
    internal_transfer,
    withdraw_simulated,
)


MONEY_QUANT = Decimal("0.0001")
VALID_MONEY = st.decimals(
    min_value=Decimal("0.0001"),
    max_value=Decimal("1000.0000"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)
SMALL_VALID_MONEY = st.decimals(
    min_value=Decimal("0.0001"),
    max_value=Decimal("100.0000"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)


def create_user():
    username = f"property-{uuid.uuid4()}"
    return get_user_model().objects.create_user(username=username)


def ledger_balance_for(transaction):
    balance = Decimal("0.0000")

    for entry in transaction.entries.all():
        if entry.direction == "CREDIT":
            balance += entry.amount
        elif entry.direction == "DEBIT":
            balance -= entry.amount

    return balance.quantize(MONEY_QUANT)


@pytest.mark.django_db
@settings(max_examples=15, deadline=None)
@given(amounts=st.lists(SMALL_VALID_MONEY, min_size=1, max_size=8))
def test_property_every_service_transaction_is_balanced(amounts):
    user = create_user()

    for amount in amounts:
        deposit_simulated(user=user, amount=amount, created_by=user)
        withdraw_simulated(user=user, amount=amount, created_by=user)
        deposit_simulated(user=user, amount=amount, created_by=user)
        internal_transfer(
            source_account="USER_WALLET",
            target_account="PENDING_BETS",
            owner=user,
            amount=amount,
            created_by=user,
        )

    for transaction in Transaction.objects.filter(created_by=user):
        assert transaction.entries.count() >= 2
        assert ledger_balance_for(transaction) == Decimal("0.0000")


@pytest.mark.django_db
@settings(max_examples=20, deadline=None)
@given(
    operations=st.lists(
        st.tuples(st.sampled_from(["deposit", "withdraw"]), SMALL_VALID_MONEY),
        min_size=1,
        max_size=12,
    )
)
def test_property_valid_deposit_withdraw_sequences_never_make_balance_negative(operations):
    user = create_user()
    expected_balance = Decimal("0.0000")

    for operation, amount in operations:
        if operation == "deposit":
            deposit_simulated(user=user, amount=amount, created_by=user)
            expected_balance += amount
        elif expected_balance >= amount:
            withdraw_simulated(user=user, amount=amount, created_by=user)
            expected_balance -= amount

        assert get_wallet_balance(user) >= Decimal("0.0000")


@pytest.mark.django_db
@settings(max_examples=20, deadline=None)
@given(amount=VALID_MONEY)
def test_property_valid_amounts_are_preserved_as_decimal_with_four_places(amount):
    user = create_user()

    transaction = deposit_simulated(user=user, amount=amount, created_by=user)

    for entry in transaction.entries.all():
        assert isinstance(entry.amount, Decimal)
        assert entry.amount.as_tuple().exponent == -4
        assert entry.amount == amount.quantize(MONEY_QUANT)
