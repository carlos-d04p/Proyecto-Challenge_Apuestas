from django.contrib import admin
from .models import Transaction, LedgerEntry, WalletIdempotencyRecord


class LedgerEntryInline(admin.TabularInline):
    model = LedgerEntry
    extra = 0
    readonly_fields = ["account", "account_owner", "direction", "amount", "created_at"]

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["id", "kind", "created_by", "created_at"]
    list_filter = ["kind", "created_at"]
    search_fields = ["id", "created_by__username", "description"]
    readonly_fields = ["id", "kind", "description", "created_by", "created_at"]
    inlines = [LedgerEntryInline]
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ["id", "transaction", "account", "account_owner", "direction", "amount", "created_at"]
    list_filter = ["account", "direction", "created_at"]
    search_fields = ["transaction__id", "account_owner__username"]
    readonly_fields = ["transaction", "account", "account_owner", "direction", "amount", "created_at"]
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WalletIdempotencyRecord)
class WalletIdempotencyRecordAdmin(admin.ModelAdmin):
    list_display = ["user", "key", "transaction", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["user__username", "key", "transaction__id"]
    readonly_fields = ["user", "key", "request_hash", "transaction", "created_at"]
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

