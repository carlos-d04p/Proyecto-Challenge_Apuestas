from django.urls import path

from apps.payments.views import (
    DepositView,
    PaymentTransactionListView,
    PaymentsDashboardView,
    WithdrawView,
)

app_name = "payments"

urlpatterns = [
    path("", PaymentsDashboardView.as_view(), name="dashboard"),
    path("api/deposit/", DepositView.as_view(), name="deposit"),
    path("api/withdraw/", WithdrawView.as_view(), name="withdraw"),
    path("api/transactions/", PaymentTransactionListView.as_view(), name="transactions"),
]
