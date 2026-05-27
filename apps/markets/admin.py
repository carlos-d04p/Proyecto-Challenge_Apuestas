from django.contrib import admin
from .models import Event, Market, Selection


class MarketInline(admin.TabularInline):
    model = Market
    extra = 0
    fields = ("kind", "name", "is_active")
    show_change_link = True


class SelectionInline(admin.TabularInline):
    model = Selection
    extra = 0
    fields = ("name", "odds", "is_active", "updated_at")
    readonly_fields = ("updated_at",)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "sport", "starts_at", "status")
    list_filter = ("sport", "status")
    search_fields = ("name",)
    ordering = ("starts_at",)
    inlines = [MarketInline]
    readonly_fields = ("id", "created_at", "updated_at")
    fieldsets = (
        ("Información del evento", {
            "fields": ("id", "name", "sport", "starts_at")
        }),
        ("Estado", {
            "fields": ("status", "suspended_until")
        }),
        ("Auditoría", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = ("name", "event", "kind", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("name", "event__name")
    inlines = [SelectionInline]
    readonly_fields = ("id",)


@admin.register(Selection)
class SelectionAdmin(admin.ModelAdmin):
    list_display = ("name", "market", "odds", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "market__name")
    readonly_fields = ("id", "updated_at")
