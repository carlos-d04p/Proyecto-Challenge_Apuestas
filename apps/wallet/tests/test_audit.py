from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.compliance.models import AuditLog
from apps.wallet.models import Transaction
from apps.wallet.services import (
    WALLET_DEPOSIT_CREATED,
    WALLET_INTERNAL_TRANSFER_CREATED,
    WALLET_WITHDRAWAL_CREATED,
    deposit_simulated,
    internal_transfer,
    withdraw_simulated,
)


def create_user(username):
    return get_user_model().objects.create_user(username=username)


def assert_wallet_audit_event(event, *, event_type, transaction, user, amount):
    assert event.event_type == event_type
    assert event.payload["transaction_id"] == str(transaction.id)
    assert event.payload["user_id"] == str(user.pk)
    assert event.payload["amount"] == str(Decimal(amount))
    assert event.payload["kind"] == transaction.kind
    assert "timestamp" in event.payload
    assert "password" not in event.payload
    assert "email" not in event.payload


@pytest.mark.django_db
def test_deposit_simulated_emits_audit_event():
    user = create_user("audit-deposit")

    transaction = deposit_simulated(user=user, amount="25.0000", created_by=user)

    event = AuditLog.objects.get()
    assert_wallet_audit_event(
        event,
        event_type=WALLET_DEPOSIT_CREATED,
        transaction=transaction,
        user=user,
        amount="25.0000",
    )


@pytest.mark.django_db
def test_withdraw_simulated_emits_audit_event():
    user = create_user("audit-withdraw")
    deposit_simulated(user=user, amount="40.0000", created_by=user)

    transaction = withdraw_simulated(user=user, amount="15.0000", created_by=user)

    event = AuditLog.objects.order_by("sequence").last()
    assert_wallet_audit_event(
        event,
        event_type=WALLET_WITHDRAWAL_CREATED,
        transaction=transaction,
        user=user,
        amount="15.0000",
    )


@pytest.mark.django_db
def test_internal_transfer_emits_audit_event():
    user = create_user("audit-transfer")
    deposit_simulated(user=user, amount="40.0000", created_by=user)

    transaction = internal_transfer(
        source_account="USER_WALLET",
        target_account="PENDING_BETS",
        owner=user,
        amount="12.0000",
        created_by=user,
    )

    event = AuditLog.objects.order_by("sequence").last()
    assert_wallet_audit_event(
        event,
        event_type=WALLET_INTERNAL_TRANSFER_CREATED,
        transaction=transaction,
        user=user,
        amount="12.0000",
    )


@pytest.mark.django_db
def test_failed_wallet_operation_does_not_emit_audit_event():
    user = create_user("audit-failure")

    with pytest.raises(ValueError):
        withdraw_simulated(user=user, amount="10.0000", created_by=user)

    assert Transaction.objects.count() == 0
    assert AuditLog.objects.count() == 0


@pytest.mark.django_db
def test_idempotent_replay_does_not_emit_duplicate_audit_event():
    user = create_user("audit-idempotent")

    first_transaction = deposit_simulated(
        user=user,
        amount="25.0000",
        created_by=user,
        idempotency_key="audit-deposit-key",
    )
    second_transaction = deposit_simulated(
        user=user,
        amount="25.0000",
        created_by=user,
        idempotency_key="audit-deposit-key",
    )

    assert second_transaction.pk == first_transaction.pk
    assert AuditLog.objects.filter(event_type=WALLET_DEPOSIT_CREATED).count() == 1
