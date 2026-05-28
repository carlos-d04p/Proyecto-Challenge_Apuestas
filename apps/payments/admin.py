"""
Admin del módulo Payments — vista de auditoría inmutable (RB-PAY-09).

Reutiliza el modelo `apps.wallet.Transaction` vía un Proxy filtrado a
DEPOSIT/WITHDRAWAL para que el equipo de operaciones pueda revisar todos
los movimientos sin posibilidad de modificarlos.
"""

from django.contrib import admin

from apps.wallet.models import Transaction, TransactionKind


class PaymentTransactionProxy(Transaction):
    class Meta:
        proxy = True
        verbose_name = "Movimiento de pago"
        verbose_name_plural = "Movimientos de pagos (Depósitos / Retiros)"


@admin.register(PaymentTransactionProxy)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "created_by", "created_at")
    list_filter = ("kind", "created_at")
    search_fields = ("id", "created_by__email", "created_by__username")
    readonly_fields = ("id", "kind", "description", "created_by", "created_at")
    ordering = ("-created_at",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(
            kind__in=[TransactionKind.DEPOSIT, TransactionKind.WITHDRAWAL]
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
