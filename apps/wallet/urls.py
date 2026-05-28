from django.urls import path

from apps.wallet.views import (
    WalletBalanceView,
    WalletDepositView,
    WalletWithdrawView,
)


app_name = "wallet"

urlpatterns = [
    path("balance/", WalletBalanceView.as_view(), name="balance"),
    path("deposit/", WalletDepositView.as_view(), name="deposit"),
    path("withdraw/", WalletWithdrawView.as_view(), name="withdraw"),
]
