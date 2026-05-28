from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView
from django.core.exceptions import ValidationError

from apps.wallet.selectors import (
    get_wallet_account_balances,
    get_wallet_balance,
    get_wallet_movements,
)
from apps.wallet.bonus_services import (
    BonusAlreadyRedeemed,
    BonusError,
    BonusInactive,
    BonusNotEligible,
    BonusNotFound,
    get_available_bonuses,
    get_bonus_balance,
    redeem_bonus_code,
)
from apps.wallet.serializers import BonusRedeemSerializer, WalletAmountSerializer
from apps.wallet.services import deposit_simulated, withdraw_simulated
from core.idempotency import IdempotencyConflict


@method_decorator(ensure_csrf_cookie, name="dispatch")
class WalletPageView(LoginRequiredMixin, TemplateView):
    template_name = "wallet/dashboard.html"


def format_money(amount):
    return f"{amount:.4f}"


def get_idempotency_key(request):
    return request.headers.get("Idempotency-Key")


def wallet_error_detail(exc):
    message = str(exc)
    if message == "Insufficient wallet balance.":
        return "Saldo disponible insuficiente para completar el retiro simulado."
    if message == "Invalid money amount.":
        return "Ingresa un monto valido."
    if message == "Money amount must be greater than zero.":
        return "El monto debe ser mayor a cero."
    if message == "Money values must not be float.":
        return "El monto debe enviarse como decimal valido, no como float."
    return message


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


class WalletBonusesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "bonus_balance": format_money(get_bonus_balance(request.user)),
                "bonuses": get_available_bonuses(request.user),
            }
        )


class WalletBonusRedeemView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = BonusRedeemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = redeem_bonus_code(
                user=request.user,
                code=serializer.validated_data["code"],
            )
        except BonusAlreadyRedeemed as exc:
            return Response(
                {"detail": str(exc), "code": exc.code},
                status=status.HTTP_409_CONFLICT,
            )
        except (BonusNotFound, BonusInactive, BonusNotEligible) as exc:
            return Response(
                {"detail": str(exc), "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except BonusError as exc:
            return Response(
                {"detail": str(exc), "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(result, status=status.HTTP_201_CREATED)


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
        except (ValueError, ValidationError) as exc:
            error_message = exc.messages[0] if hasattr(exc, 'messages') else wallet_error_detail(exc)
            return Response({"detail": error_message}, status=status.HTTP_400_BAD_REQUEST)

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
        except (ValueError, ValidationError) as exc:
            error_message = exc.messages[0] if hasattr(exc, 'messages') else wallet_error_detail(exc)
            return Response({"detail": error_message}, status=status.HTTP_400_BAD_REQUEST)
