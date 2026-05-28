"""
apps.payments — Fachada de Depósitos / Retiros simulados.

La lógica financiera vive en `apps.wallet.services` (ledger de partida doble,
idempotencia, KYC, atomicidad). Esta app expone esos servicios bajo el
namespace "payments" con su propio dashboard HTML y endpoints REST.

Reglas aplicadas (manifiesto Módulo 2 — Payments):
- RB-PAY-01: amount como Decimal(18,4) en serializers (no float).
- RB-PAY-02: atomicidad y select_for_update() viven en wallet.services.
- RB-PAY-03: header Idempotency-Key obligatorio.
- RB-PAY-04: límites 30.0000–30,000.0000 (wallet.services.deposit_simulated).
- RB-PAY-05: depósito instantáneo COMPLETED (wallet).
- RB-PAY-06: verificación de fondos (wallet) — sin sobregiro.
- RB-PAY-07: mínimo 100.0000 para retiros (wallet).
- RB-PAY-08: KYC (is_email_verified) → 403 Forbidden.
- RB-PAY-09: trazabilidad inmutable via wallet.LedgerEntry append-only.
"""

from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.serializers import PaymentAmountSerializer
from apps.wallet.models import LedgerDirection, Transaction, TransactionKind
from apps.wallet.selectors import get_wallet_balance
from apps.wallet.services import deposit_simulated, withdraw_simulated
from core.idempotency import IdempotencyConflict


def _money(value):
    return f"{value:.4f}"


def _idempotency_key(request):
    return request.headers.get("Idempotency-Key")


def _normalize_error(exc):
    if hasattr(exc, "messages") and exc.messages:
        return exc.messages[0]
    return str(exc) or "Solicitud inválida."


class _PaymentMutationView(APIView):
    """Base común: valida idempotency-key, serializa amount y delega al servicio."""

    permission_classes = [IsAuthenticated]
    service = None
    success_message = ""
    success_status = status.HTTP_201_CREATED

    def post(self, request):
        key = _idempotency_key(request)
        if not key:
            # RB-PAY-03
            return Response(
                {"detail": "Falta el header Idempotency-Key."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PaymentAmountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            tx = self.service(
                user=request.user,
                amount=serializer.validated_data["amount"],
                created_by=request.user,
                idempotency_key=key,
            )
        except PermissionError as exc:
            # RB-PAY-08
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except IdempotencyConflict as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except (ValueError, ValidationError) as exc:
            return Response(
                {"detail": _normalize_error(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "detail": self.success_message,
                "transaction_id": str(tx.id),
                "balance": _money(get_wallet_balance(request.user)),
            },
            status=self.success_status,
        )


class DepositView(_PaymentMutationView):
    service = staticmethod(deposit_simulated)
    success_message = "Depósito simulado completado."
    success_status = status.HTTP_201_CREATED


class WithdrawView(_PaymentMutationView):
    service = staticmethod(withdraw_simulated)
    success_message = "Retiro simulado completado."
    success_status = status.HTTP_200_OK


class PaymentTransactionListView(APIView):
    """
    RB-PAY-09: historial inmutable de depósitos y retiros del usuario.
    Lee del libro mayor (LedgerEntry) filtrando por kind DEPOSIT/WITHDRAWAL.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            Transaction.objects.filter(
                kind__in=[TransactionKind.DEPOSIT, TransactionKind.WITHDRAWAL],
                entries__account_owner=request.user,
            )
            .distinct()
            .order_by("-created_at")
            .prefetch_related("entries")[:200]
        )

        items = []
        for tx in qs:
            user_entry = next(
                (e for e in tx.entries.all() if e.account_owner_id == request.user.id),
                None,
            )
            if user_entry is None:
                continue
            sign = Decimal("1") if user_entry.direction == LedgerDirection.CREDIT else Decimal("-1")
            items.append(
                {
                    "id": str(tx.id),
                    "kind": tx.kind,
                    "amount": _money(user_entry.amount * sign),
                    "created_at": tx.created_at.isoformat(),
                }
            )
        return Response({"results": items})


@method_decorator(ensure_csrf_cookie, name="dispatch")
class PaymentsDashboardView(LoginRequiredMixin, TemplateView):
    """Página HTML del módulo Payments: saldo, formularios y historial."""

    template_name = "payments/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["balance"] = _money(get_wallet_balance(user))
        # Verificacion de correo
        email_ok = bool(getattr(user, "is_email_verified", False))
        # Estado KYC aprobado
        try:
            kyc_ok = email_ok and user.perfil_kyc.status == "VERIFIED"
            kyc_status = user.perfil_kyc.get_status_display()
        except Exception:
            kyc_ok = False
            kyc_status = "Sin perfil KYC"
        ctx["email_verified"] = email_ok
        ctx["is_kyc_verified"] = kyc_ok   # retiros
        ctx["can_deposit"] = kyc_ok       # depósitos
        ctx["kyc_status"] = kyc_status
        ctx["min_deposit"] = "30.0000"
        ctx["max_deposit"] = "30000.0000"
        ctx["min_withdrawal"] = "100.0000"
        return ctx
