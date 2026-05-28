from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.wallet.models import LedgerEntry, Transaction
from apps.wallet.selectors import get_wallet_balance
from apps.wallet.services import deposit_simulated


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def create_user(username):
    return get_user_model().objects.create_user(username=username)


@pytest.mark.django_db
def test_wallet_balance_endpoint_returns_derived_balance():
    user = create_user("api-balance")
    deposit_simulated(user=user, amount="12.5000", created_by=user)
    client = authenticated_client(user)

    response = client.get("/api/wallet/balance/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {
        "balance": "12.5000",
        "accounts": {
            "USER_WALLET": "12.5000",
            "PENDING_BETS": "0.0000",
            "BONUS": "0.0000",
        },
    }


@pytest.mark.django_db
def test_wallet_balance_endpoint_returns_account_breakdown():
    user = create_user("api-balance-breakdown")
    deposit_simulated(user=user, amount="20.0000", created_by=user)
    pending_transaction = Transaction.objects.create(
        kind="INTERNAL_TRANSFER",
        created_by=user,
    )
    source_entry = LedgerEntry.objects.create(
        transaction=pending_transaction,
        account="USER_WALLET",
        account_owner=user,
        direction="DEBIT",
        amount=Decimal("7.0000"),
    )
    LedgerEntry.objects.create(
        transaction=pending_transaction,
        account="PENDING_BETS",
        account_owner=user,
        direction="CREDIT",
        amount=Decimal("7.0000"),
    )
    bonus_transaction = Transaction.objects.create(kind="INTERNAL_TRANSFER", created_by=user)
    LedgerEntry.objects.create(
        transaction=bonus_transaction,
        account="HOUSE",
        direction="DEBIT",
        amount=Decimal("2.5000"),
    )
    LedgerEntry.objects.create(
        transaction=bonus_transaction,
        account="BONUS",
        account_owner=user,
        direction="CREDIT",
        amount=Decimal("2.5000"),
    )
    client = authenticated_client(user)

    response = client.get("/api/wallet/balance/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["accounts"] == {
        "USER_WALLET": "13.0000",
        "PENDING_BETS": "7.0000",
        "BONUS": "2.5000",
    }


@pytest.mark.django_db
def test_wallet_history_endpoint_returns_movements_ordered_without_sensitive_accounts():
    user = create_user("api-history")
    deposit_transaction = deposit_simulated(user=user, amount="30.0000", created_by=user)
    withdraw_transaction = Transaction.objects.create(kind="WITHDRAWAL", created_by=user)
    LedgerEntry.objects.create(
        transaction=withdraw_transaction,
        account="USER_WALLET",
        account_owner=user,
        direction="DEBIT",
        amount=Decimal("8.0000"),
    )
    LedgerEntry.objects.create(
        transaction=withdraw_transaction,
        account="HOUSE",
        direction="CREDIT",
        amount=Decimal("8.0000"),
    )
    pending_transaction = Transaction.objects.create(
        kind="INTERNAL_TRANSFER",
        created_by=user,
    )
    source_entry = LedgerEntry.objects.create(
        transaction=pending_transaction,
        account="USER_WALLET",
        account_owner=user,
        direction="DEBIT",
        amount=Decimal("5.0000"),
    )
    pending_entry = LedgerEntry.objects.create(
        transaction=pending_transaction,
        account="PENDING_BETS",
        account_owner=user,
        direction="CREDIT",
        amount=Decimal("5.0000"),
    )
    now = timezone.now()
    LedgerEntry.objects.filter(transaction=deposit_transaction).update(
        created_at=now - timezone.timedelta(minutes=3),
    )
    LedgerEntry.objects.filter(transaction=withdraw_transaction).update(
        created_at=now - timezone.timedelta(minutes=2),
    )
    LedgerEntry.objects.filter(id=source_entry.id).update(
        created_at=now - timezone.timedelta(seconds=90),
    )
    LedgerEntry.objects.filter(id=pending_entry.id).update(
        created_at=now - timezone.timedelta(minutes=1),
    )
    client = authenticated_client(user)

    response = client.get("/api/wallet/history/")

    assert response.status_code == status.HTTP_200_OK
    movements = response.data["movements"]
    assert [movement["operation_type"] for movement in movements[:4]] == [
        "Fichas pendientes en apuestas",
        "Transferencia interna",
        "Retiro simulado",
        "Recarga simulada",
    ]
    assert all(movement["account"] != "HOUSE" for movement in movements)
    assert movements[0]["account_label"] == "Fichas pendientes en apuestas"
    assert movements[0]["amount"] == "5.0000"
    assert movements[1]["amount"] == "-5.0000"
    assert movements[2]["amount"] == "-8.0000"
    assert movements[0]["status"] == "Completado"
    assert movements[0]["reference"] == str(pending_transaction.id)[:8]


@pytest.mark.django_db
def test_wallet_deposit_endpoint_requires_idempotency_key():
    user = create_user("api-deposit-no-key")
    client = authenticated_client(user)

    response = client.post("/api/wallet/deposit/", {"amount": "10.0000"}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Transaction.objects.count() == 0


@pytest.mark.django_db
def test_wallet_deposit_endpoint_creates_simulated_deposit():
    user = create_user("api-deposit")
    client = authenticated_client(user)

    response = client.post(
        "/api/wallet/deposit/",
        {"amount": "10.5000"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="api-deposit-key",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["balance"] == "10.5000"
    assert Transaction.objects.filter(kind="DEPOSIT").count() == 1
    assert get_wallet_balance(user) == Decimal("10.5000")


@pytest.mark.django_db
def test_wallet_deposit_endpoint_rejects_float_amount():
    user = create_user("api-deposit-float")
    client = authenticated_client(user)

    response = client.post(
        "/api/wallet/deposit/",
        {"amount": 10.5},
        format="json",
        HTTP_IDEMPOTENCY_KEY="api-float-key",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Transaction.objects.count() == 0


@pytest.mark.django_db
def test_wallet_deposit_endpoint_replays_same_idempotency_key():
    user = create_user("api-deposit-idem")
    client = authenticated_client(user)
    payload = {"amount": "15.0000"}

    first_response = client.post(
        "/api/wallet/deposit/",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY="api-deposit-idem-key",
    )
    second_response = client.post(
        "/api/wallet/deposit/",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY="api-deposit-idem-key",
    )

    assert first_response.status_code == status.HTTP_201_CREATED
    assert second_response.status_code == status.HTTP_201_CREATED
    assert second_response.data["transaction_id"] == first_response.data["transaction_id"]
    assert Transaction.objects.filter(kind="DEPOSIT").count() == 1
    assert get_wallet_balance(user) == Decimal("15.0000")


@pytest.mark.django_db
def test_wallet_deposit_endpoint_rejects_idempotency_conflict():
    user = create_user("api-deposit-conflict")
    client = authenticated_client(user)

    client.post(
        "/api/wallet/deposit/",
        {"amount": "15.0000"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="api-conflict-key",
    )
    response = client.post(
        "/api/wallet/deposit/",
        {"amount": "20.0000"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="api-conflict-key",
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert Transaction.objects.filter(kind="DEPOSIT").count() == 1
    assert get_wallet_balance(user) == Decimal("15.0000")


@pytest.mark.django_db
def test_wallet_withdraw_endpoint_requires_idempotency_key():
    user = create_user("api-withdraw-no-key")
    client = authenticated_client(user)

    response = client.post("/api/wallet/withdraw/", {"amount": "10.0000"}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Transaction.objects.count() == 0


@pytest.mark.django_db
def test_wallet_withdraw_endpoint_creates_simulated_withdrawal():
    user = create_user("api-withdraw")
    deposit_simulated(user=user, amount="30.0000", created_by=user)
    client = authenticated_client(user)

    response = client.post(
        "/api/wallet/withdraw/",
        {"amount": "12.0000"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="api-withdraw-key",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["balance"] == "18.0000"
    assert Transaction.objects.filter(kind="WITHDRAWAL").count() == 1
    assert get_wallet_balance(user) == Decimal("18.0000")


@pytest.mark.django_db
def test_wallet_withdraw_endpoint_rejects_insufficient_balance():
    user = create_user("api-withdraw-insufficient")
    client = authenticated_client(user)

    response = client.post(
        "/api/wallet/withdraw/",
        {"amount": "12.0000"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="api-withdraw-insufficient-key",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Transaction.objects.count() == 0
    assert get_wallet_balance(user) == Decimal("0.0000")


@pytest.mark.django_db
def test_wallet_bonuses_endpoint_lists_promotional_campaigns():
    user = create_user("api-bonuses")
    client = authenticated_client(user)

    response = client.get("/api/wallet/bonuses/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["bonus_balance"] == "0.0000"
    assert {bonus["code"] for bonus in response.data["bonuses"]} == {
        "BIENVENIDA",
        "PRIMERA_RECARGA",
        "JUEGO_RESPONSABLE",
    }


@pytest.mark.django_db
def test_wallet_bonus_redeem_endpoint_applies_welcome_bonus():
    user = create_user("api-bonus-redeem")
    client = authenticated_client(user)

    response = client.post(
        "/api/wallet/bonuses/redeem/",
        {"code": "BIENVENIDA"},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["status"] == "applied"
    assert response.data["amount"] == "50.0000"
    assert response.data["bonus_balance"] == "50.0000"
