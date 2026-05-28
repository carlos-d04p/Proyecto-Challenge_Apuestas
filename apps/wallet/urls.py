from django.urls import path

from apps.wallet.views import (
    WalletBalanceView,
    WalletBonusesView,
    WalletBonusRedeemView,
    WalletDepositView,
    WalletHistoryView,
    WalletWithdrawView,
)


app_name = "wallet"

urlpatterns = [
    path("balance/", WalletBalanceView.as_view(), name="balance"),
    path("bonuses/", WalletBonusesView.as_view(), name="bonuses"),
    path("bonuses/redeem/", WalletBonusRedeemView.as_view(), name="bonus-redeem"),
    path("history/", WalletHistoryView.as_view(), name="history"),
    path("deposit/", WalletDepositView.as_view(), name="deposit"),
    path("withdraw/", WalletWithdrawView.as_view(), name="withdraw"),
]
