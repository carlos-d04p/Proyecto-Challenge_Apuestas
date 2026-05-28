from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.wallet.selectors import get_wallet_balance
from apps.wallet.serializers import WalletAmountSerializer
from apps.wallet.services import deposit_simulated, withdraw_simulated
from core.idempotency import IdempotencyConflict


def format_money(amount):
    return f"{amount:.4f}"


def get_idempotency_key(request):
    return request.headers.get("Idempotency-Key")


class WalletBalanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        balance = get_wallet_balance(request.user)
        return Response({"balance": format_money(balance)})


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
