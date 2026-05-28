from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.wallet.models import LedgerEntry, Transaction
from apps.wallet.services import get_wallet_balance


def create_user(username):
    return get_user_model().objects.create_user(username=username)


def create_transaction(user, kind="INTERNAL_TRANSFER"):
    return Transaction.objects.create(kind=kind, created_by=user)


def create_ledger_entry(
    *,
    transaction,
    account,
    direction,
    amount,
    account_owner=None,
):
    return LedgerEntry.objects.create(
        transaction=transaction,
        account=account,
        account_owner=account_owner,
        direction=direction,
        amount=Decimal(amount),
    )


@pytest.mark.django_db
def test_wallet_balance_starts_at_zero_without_movements():
    user = create_user("balance-empty")

    assert get_wallet_balance(user) == Decimal("0.0000")


@pytest.mark.django_db
def test_credit_in_user_wallet_increases_balance():
    user = create_user("balance-credit")
    transaction = create_transaction(user, kind="DEPOSIT")
    create_ledger_entry(
        transaction=transaction,
        account="USER_WALLET",
        account_owner=user,
        direction="CREDIT",
        amount="25.5000",
    )

    assert get_wallet_balance(user) == Decimal("25.5000")


@pytest.mark.django_db
def test_debit_in_user_wallet_reduces_balance():
    user = create_user("balance-debit")
    transaction = create_transaction(user, kind="WITHDRAWAL")
    create_ledger_entry(
        transaction=transaction,
        account="USER_WALLET",
        account_owner=user,
        direction="CREDIT",
        amount="30.0000",
    )
    create_ledger_entry(
        transaction=transaction,
        account="USER_WALLET",
        account_owner=user,
        direction="DEBIT",
        amount="12.2500",
    )

    assert get_wallet_balance(user) == Decimal("17.7500")


@pytest.mark.django_db
def test_house_movements_do_not_affect_user_wallet_balance():
    user = create_user("balance-house")
    transaction = create_transaction(user, kind="DEPOSIT")
    create_ledger_entry(
        transaction=transaction,
        account="HOUSE",
        direction="DEBIT",
        amount="99.0000",
    )

    assert get_wallet_balance(user) == Decimal("0.0000")


@pytest.mark.django_db
def test_wallet_balance_is_not_read_from_user_balance_field():
    user = create_user("balance-derived")
    user.balance = Decimal("9999.0000")
    transaction = create_transaction(user, kind="DEPOSIT")
    create_ledger_entry(
        transaction=transaction,
        account="USER_WALLET",
        account_owner=user,
        direction="CREDIT",
        amount="10.0000",
    )

    assert get_wallet_balance(user) == Decimal("10.0000")


@pytest.mark.django_db
def test_wallet_balance_sums_multiple_transactions_for_user_wallet_only():
    user = create_user("balance-many")
    other_user = create_user("balance-other")

    first_transaction = create_transaction(user, kind="DEPOSIT")
    create_ledger_entry(
        transaction=first_transaction,
        account="USER_WALLET",
        account_owner=user,
        direction="CREDIT",
        amount="100.0000",
    )

    second_transaction = create_transaction(user, kind="WITHDRAWAL")
    create_ledger_entry(
        transaction=second_transaction,
        account="USER_WALLET",
        account_owner=user,
        direction="DEBIT",
        amount="35.1250",
    )

    third_transaction = create_transaction(user, kind="INTERNAL_TRANSFER")
    create_ledger_entry(
        transaction=third_transaction,
        account="PENDING_BETS",
        account_owner=user,
        direction="CREDIT",
        amount="500.0000",
    )
    create_ledger_entry(
        transaction=third_transaction,
        account="HOUSE",
        direction="CREDIT",
        amount="20.0000",
    )

    other_transaction = create_transaction(other_user, kind="DEPOSIT")
    create_ledger_entry(
        transaction=other_transaction,
        account="USER_WALLET",
        account_owner=other_user,
        direction="CREDIT",
        amount="777.0000",
    )

    assert get_wallet_balance(user) == Decimal("64.8750")
