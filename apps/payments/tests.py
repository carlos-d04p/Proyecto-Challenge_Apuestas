"""
Tests del módulo Payments (fachada sobre wallet).

Cubren las reglas RB-PAY-01..09 desde el contrato del endpoint:
- Decimal(18,4) inquebrantable
- Idempotency-Key obligatoria y deduplicación
- Límites de depósito y retiro
- KYC → 403
- Auditoría visible (historial)
"""

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


User = get_user_model()


def _credit(user, amount):
    """Acredita saldo directo para pruebas de retiro, vía servicio real."""
    from apps.wallet.services import deposit_simulated

    deposit_simulated(
        user=user,
        amount=Decimal(amount),
        created_by=user,
        idempotency_key=f"seed-{uuid.uuid4()}",
    )


class PaymentsAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", password="Sup3rPass!"
        )
        self.user.is_email_verified = True
        self.user.save(update_fields=["is_email_verified"])
        self.client.force_authenticate(user=self.user)
        self.deposit_url = reverse("payments:deposit")
        self.withdraw_url = reverse("payments:withdraw")
        self.tx_url = reverse("payments:transactions")

    # ── RB-PAY-03 ──────────────────────────────────────────────────────────
    def test_deposit_requires_idempotency_key(self):
        resp = self.client.post(self.deposit_url, {"amount": "100.0000"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Idempotency-Key", resp.json()["detail"])

    def test_deposit_idempotency_returns_same_transaction(self):
        key = str(uuid.uuid4())
        r1 = self.client.post(
            self.deposit_url, {"amount": "200.0000"},
            format="json", HTTP_IDEMPOTENCY_KEY=key,
        )
        r2 = self.client.post(
            self.deposit_url, {"amount": "200.0000"},
            format="json", HTTP_IDEMPOTENCY_KEY=key,
        )
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r1.json()["transaction_id"], r2.json()["transaction_id"])
        self.assertEqual(r2.json()["balance"], "200.0000")

    # ── RB-PAY-04 ──────────────────────────────────────────────────────────
    def test_deposit_below_minimum_rejected(self):
        resp = self.client.post(
            self.deposit_url, {"amount": "10.0000"},
            format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_deposit_above_maximum_rejected(self):
        resp = self.client.post(
            self.deposit_url, {"amount": "10000.0001"},
            format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── RB-PAY-05 ──────────────────────────────────────────────────────────
    def test_deposit_credits_balance_instantly(self):
        resp = self.client.post(
            self.deposit_url, {"amount": "500.0000"},
            format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.json()["balance"], "500.0000")

    # ── RB-PAY-06 ──────────────────────────────────────────────────────────
    def test_withdraw_insufficient_funds_rejected(self):
        resp = self.client.post(
            self.withdraw_url, {"amount": "500.0000"},
            format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── RB-PAY-07 ──────────────────────────────────────────────────────────
    def test_withdraw_below_minimum_rejected(self):
        _credit(self.user, "1000.0000")
        resp = self.client.post(
            self.withdraw_url, {"amount": "50.0000"},
            format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── RB-PAY-08 ──────────────────────────────────────────────────────────
    def test_withdraw_without_kyc_forbidden(self):
        self.user.is_email_verified = False
        self.user.save(update_fields=["is_email_verified"])
        _credit(self.user, "1000.0000")
        resp = self.client.post(
            self.withdraw_url, {"amount": "200.0000"},
            format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── RB-PAY-09 ──────────────────────────────────────────────────────────
    def test_transactions_history_lists_movements(self):
        self.client.post(
            self.deposit_url, {"amount": "300.0000"},
            format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.client.post(
            self.withdraw_url, {"amount": "150.0000"},
            format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        resp = self.client.get(self.tx_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        kinds = [r["kind"] for r in resp.json()["results"]]
        self.assertIn("DEPOSIT", kinds)
        self.assertIn("WITHDRAWAL", kinds)

    # ── RB-PAY-01 (precisión) ─────────────────────────────────────────────
    def test_deposit_rejects_more_than_four_decimals(self):
        resp = self.client.post(
            self.deposit_url, {"amount": "100.123456"},
            format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
