from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView

from apps.wallet.selectors import (
    get_wallet_account_balances,
    get_wallet_balance,
    get_wallet_movements,
)
from apps.wallet.serializers import WalletAmountSerializer
from apps.wallet.services import deposit_simulated, withdraw_simulated
from core.idempotency import IdempotencyConflict


@method_decorator(ensure_csrf_cookie, name="dispatch")
class WalletPageView(LoginRequiredMixin, TemplateView):
    template_name = "wallet/dashboard.html"


def format_money(amount):
    return f"{amount:.4f}"


def get_idempotency_key(request):
    return request.headers.get("Idempotency-Key")


class WalletBalanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        balances = get_wallet_account_balances(request.user)
        return Response(
            {
                "balance": format_money(balances["available"]),
                "accounts": {
                    "USER_WALLET": format_money(balances["available"]),
                    "PENDING_BETS": format_money(balances["pending_bets"]),
                    "BONUS": format_money(balances["bonus"]),
                },
            }
        )


class WalletHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        movements = get_wallet_movements(request.user)
        return Response(
            {
                "movements": [
                    {
                        "date": movement["date"].isoformat(),
                        "operation_type": movement["operation_type"],
                        "account": movement["account"],
                        "account_label": movement["account_label"],
                        "amount": format_money(movement["amount"]),
                        "status": movement["status"],
                        "transaction_id": movement["transaction_id"],
                        "reference": movement["reference"],
                    }
                    for movement in movements
                ]
            }
        )


class WalletDepositView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        idempotency_key = get_idempotency_key(request)
        if not idempotency_key:
            return Response(
                {"detail": "Idempotency-Key header is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = WalletAmountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            transaction = deposit_simulated(
                user=request.user,
                amount=serializer.validated_data["amount"],
                created_by=request.user,
                idempotency_key=idempotency_key,
            )
        except IdempotencyConflict as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "transaction_id": str(transaction.id),
                "balance": format_money(get_wallet_balance(request.user)),
            },
            status=status.HTTP_201_CREATED,
        )


class WalletWithdrawView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        idempotency_key = get_idempotency_key(request)
        if not idempotency_key:
            return Response(
                {"detail": "Idempotency-Key header is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = WalletAmountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            transaction = withdraw_simulated(
                user=request.user,
                amount=serializer.validated_data["amount"],
                created_by=request.user,
                idempotency_key=idempotency_key,
            )
        except IdempotencyConflict as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "transaction_id": str(transaction.id),
                "balance": format_money(get_wallet_balance(request.user)),
            }
        )
