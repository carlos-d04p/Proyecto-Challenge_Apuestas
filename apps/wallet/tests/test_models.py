import uuid
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models

from apps.wallet.models import LedgerEntry, Transaction


ALLOWED_ACCOUNTS = {"USER_WALLET", "HOUSE", "PENDING_BETS", "BONUS"}
ALLOWED_DIRECTIONS = {"DEBIT", "CREDIT"}


def choice_values(field):
    return {value for value, _label in field.choices}


def test_transaction_model_has_required_fields():
    fields = {field.name: field for field in Transaction._meta.fields}

    assert isinstance(fields["id"], models.UUIDField)
    assert fields["id"].primary_key is True
    assert fields["id"].default == uuid.uuid4
    assert "kind" in fields
    assert "description" in fields
    assert "created_by" in fields
    assert "created_at" in fields


def test_ledger_entry_model_has_required_fields():
    fields = {field.name: field for field in LedgerEntry._meta.fields}

    assert "transaction" in fields
    assert "account" in fields
    assert "account_owner" in fields
    assert "direction" in fields
    assert "amount" in fields
    assert "created_at" in fields


def test_ledger_entry_account_choices_are_limited_to_wallet_accounts():
    field = LedgerEntry._meta.get_field("account")

    assert choice_values(field) == ALLOWED_ACCOUNTS


def test_ledger_entry_direction_choices_are_limited_to_debit_and_credit():
    field = LedgerEntry._meta.get_field("direction")

    assert choice_values(field) == ALLOWED_DIRECTIONS


def test_ledger_entry_amount_is_decimal_18_4():
    field = LedgerEntry._meta.get_field("amount")

    assert isinstance(field, models.DecimalField)
    assert field.max_digits == 18
    assert field.decimal_places == 4


@pytest.mark.django_db
def test_ledger_entry_amount_must_be_greater_than_zero():
    user = get_user_model().objects.create_user(username="wallet-user")
    tx = Transaction.objects.create(kind="DEPOSIT", created_by=user)

    entry = LedgerEntry(
        transaction=tx,
        account="USER_WALLET",
        account_owner=user,
        direction="CREDIT",
        amount=Decimal("0.0000"),
    )

    with pytest.raises(ValidationError):
        entry.full_clean()


@pytest.mark.django_db
def test_house_account_allows_null_account_owner():
    user = get_user_model().objects.create_user(username="house-user")
    tx = Transaction.objects.create(kind="DEPOSIT", created_by=user)

    entry = LedgerEntry(
        transaction=tx,
        account="HOUSE",
        account_owner=None,
        direction="DEBIT",
        amount=Decimal("10.0000"),
    )

    entry.full_clean()


@pytest.mark.django_db
@pytest.mark.parametrize("account", ["USER_WALLET", "PENDING_BETS", "BONUS"])
def test_user_owned_accounts_require_account_owner(account):
    user = get_user_model().objects.create_user(username=f"{account.lower()}-user")
    tx = Transaction.objects.create(kind="INTERNAL_TRANSFER", created_by=user)

    entry = LedgerEntry(
        transaction=tx,
        account=account,
        account_owner=None,
        direction="CREDIT",
        amount=Decimal("10.0000"),
    )

    with pytest.raises(ValidationError):
        entry.full_clean()
