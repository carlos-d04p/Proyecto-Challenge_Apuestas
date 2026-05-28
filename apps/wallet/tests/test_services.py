from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.wallet.models import LedgerEntry, Transaction
from apps.wallet.selectors import get_wallet_balance
from apps.wallet.services import (
    deposit_simulated,
    internal_transfer,
    withdraw_simulated,
)


def create_user(username):
    return get_user_model().objects.create_user(username=username)


def assert_transaction_is_balanced(transaction):
    balance = Decimal("0.0000")

    for entry in transaction.entries.all():
        if entry.direction == "CREDIT":
            balance += entry.amount
        elif entry.direction == "DEBIT":
            balance -= entry.amount

    assert balance == Decimal("0.0000")


@pytest.mark.django_db
def test_deposit_simulated_creates_balanced_deposit_and_increases_balance():
    user = create_user("deposit-user")

    transaction = deposit_simulated(
        user=user,
        amount="50.2500",
        created_by=user,
        idempotency_key=None,
    )

    assert transaction.kind == "DEPOSIT"
    assert transaction.entries.count() == 2
    assert transaction.entries.filter(
        account="HOUSE",
        account_owner=None,
        direction="DEBIT",
        amount=Decimal("50.2500"),
    ).exists()
    assert transaction.entries.filter(
        account="USER_WALLET",
        account_owner=user,
        direction="CREDIT",
        amount=Decimal("50.2500"),
    ).exists()
    assert_transaction_is_balanced(transaction)
    assert get_wallet_balance(user) == Decimal("50.2500")


@pytest.mark.django_db
def test_withdraw_simulated_creates_balanced_withdrawal_and_reduces_balance():
    user = create_user("withdraw-user")
    deposit_simulated(user=user, amount="80.0000", created_by=user)

    transaction = withdraw_simulated(
        user=user,
        amount="30.1250",
        created_by=user,
        idempotency_key=None,
    )

    assert transaction.kind == "WITHDRAWAL"
    assert transaction.entries.count() == 2
    assert transaction.entries.filter(
        account="USER_WALLET",
        account_owner=user,
        direction="DEBIT",
        amount=Decimal("30.1250"),
    ).exists()
    assert transaction.entries.filter(
        account="HOUSE",
        account_owner=None,
        direction="CREDIT",
        amount=Decimal("30.1250"),
    ).exists()
    assert_transaction_is_balanced(transaction)
    assert get_wallet_balance(user) == Decimal("49.8750")


@pytest.mark.django_db
def test_internal_transfer_creates_balanced_debit_and_credit_entries():
    user = create_user("transfer-user")
    deposit_simulated(user=user, amount="40.0000", created_by=user)

    transaction = internal_transfer(
        source_account="USER_WALLET",
        target_account="PENDING_BETS",
        owner=user,
        amount="15.5000",
        created_by=user,
    )

    assert transaction.kind == "INTERNAL_TRANSFER"
    assert transaction.entries.count() == 2
    assert transaction.entries.filter(
        account="USER_WALLET",
        account_owner=user,
        direction="DEBIT",
        amount=Decimal("15.5000"),
    ).exists()
    assert transaction.entries.filter(
        account="PENDING_BETS",
        account_owner=user,
        direction="CREDIT",
        amount=Decimal("15.5000"),
    ).exists()
    assert_transaction_is_balanced(transaction)


@pytest.mark.django_db
def test_withdraw_simulated_fails_without_sufficient_balance_and_creates_no_entries():
    user = create_user("insufficient-user")

    with pytest.raises(ValueError):
        withdraw_simulated(
            user=user,
            amount="10.0000",
            created_by=user,
            idempotency_key=None,
        )

    assert Transaction.objects.count() == 0
    assert LedgerEntry.objects.count() == 0
    assert get_wallet_balance(user) == Decimal("0.0000")


@pytest.mark.django_db
def test_failed_operation_does_not_leave_partial_transaction_or_entries():
    user = create_user("partial-failure-user")

    with pytest.raises(ValueError):
        deposit_simulated(
            user=user,
            amount="0.0000",
            created_by=user,
            idempotency_key=None,
        )

    assert Transaction.objects.count() == 0
    assert LedgerEntry.objects.count() == 0
