from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.wallet.models import Transaction
from apps.wallet.selectors import get_wallet_balance
from apps.wallet.services import (
    deposit_simulated,
    internal_transfer,
    withdraw_simulated,
)


def create_user(username):
    return get_user_model().objects.create_user(username=username)


@pytest.mark.django_db
def test_deposit_simulated_with_same_idempotency_key_creates_only_one_transaction():
    user = create_user("idem-deposit")

    first_transaction = deposit_simulated(
        user=user,
        amount="25.0000",
        created_by=user,
        idempotency_key="deposit-key-1",
    )
    second_transaction = deposit_simulated(
        user=user,
        amount="25.0000",
        created_by=user,
        idempotency_key="deposit-key-1",
    )

    assert second_transaction.pk == first_transaction.pk
    assert Transaction.objects.filter(kind="DEPOSIT").count() == 1
    assert get_wallet_balance(user) == Decimal("25.0000")


@pytest.mark.django_db
def test_deposit_simulated_rejects_same_idempotency_key_with_different_payload():
    user = create_user("idem-deposit-conflict")

    deposit_simulated(
        user=user,
        amount="25.0000",
        created_by=user,
        idempotency_key="deposit-key-conflict",
    )

    with pytest.raises(ValueError):
        deposit_simulated(
            user=user,
            amount="30.0000",
            created_by=user,
            idempotency_key="deposit-key-conflict",
        )

    assert Transaction.objects.filter(kind="DEPOSIT").count() == 1
    assert get_wallet_balance(user) == Decimal("25.0000")


@pytest.mark.django_db
def test_withdraw_simulated_with_same_idempotency_key_creates_only_one_transaction():
    user = create_user("idem-withdraw")
    deposit_simulated(user=user, amount="100.0000", created_by=user)

    first_transaction = withdraw_simulated(
        user=user,
        amount="40.0000",
        created_by=user,
        idempotency_key="withdraw-key-1",
    )
    second_transaction = withdraw_simulated(
        user=user,
        amount="40.0000",
        created_by=user,
        idempotency_key="withdraw-key-1",
    )

    assert second_transaction.pk == first_transaction.pk
    assert Transaction.objects.filter(kind="WITHDRAWAL").count() == 1
    assert get_wallet_balance(user) == Decimal("60.0000")


@pytest.mark.django_db
def test_withdraw_simulated_rejects_same_idempotency_key_with_different_payload():
    user = create_user("idem-withdraw-conflict")
    deposit_simulated(user=user, amount="100.0000", created_by=user)

    withdraw_simulated(
        user=user,
        amount="40.0000",
        created_by=user,
        idempotency_key="withdraw-key-conflict",
    )

    with pytest.raises(ValueError):
        withdraw_simulated(
            user=user,
            amount="45.0000",
            created_by=user,
            idempotency_key="withdraw-key-conflict",
        )

    assert Transaction.objects.filter(kind="WITHDRAWAL").count() == 1
    assert get_wallet_balance(user) == Decimal("60.0000")


@pytest.mark.django_db
def test_internal_transfer_with_same_idempotency_key_creates_only_one_transaction():
    user = create_user("idem-transfer")
    deposit_simulated(user=user, amount="100.0000", created_by=user)

    first_transaction = internal_transfer(
        source_account="USER_WALLET",
        target_account="PENDING_BETS",
        owner=user,
        amount="30.0000",
        created_by=user,
        idempotency_key="transfer-key-1",
    )
    second_transaction = internal_transfer(
        source_account="USER_WALLET",
        target_account="PENDING_BETS",
        owner=user,
        amount="30.0000",
        created_by=user,
        idempotency_key="transfer-key-1",
    )

    assert second_transaction.pk == first_transaction.pk
    assert Transaction.objects.filter(kind="INTERNAL_TRANSFER").count() == 1
    assert get_wallet_balance(user) == Decimal("70.0000")


@pytest.mark.django_db
def test_internal_transfer_rejects_same_idempotency_key_with_different_payload():
    user = create_user("idem-transfer-conflict")
    deposit_simulated(user=user, amount="100.0000", created_by=user)

    internal_transfer(
        source_account="USER_WALLET",
        target_account="PENDING_BETS",
        owner=user,
        amount="30.0000",
        created_by=user,
        idempotency_key="transfer-key-conflict",
    )

    with pytest.raises(ValueError):
        internal_transfer(
            source_account="USER_WALLET",
            target_account="BONUS",
            owner=user,
            amount="30.0000",
            created_by=user,
            idempotency_key="transfer-key-conflict",
        )

    assert Transaction.objects.filter(kind="INTERNAL_TRANSFER").count() == 1
    assert get_wallet_balance(user) == Decimal("70.0000")
