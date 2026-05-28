"""
Registro de modelos de accounts en el admin de Django.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser, PerfilKYC, RegistroIdempotencia


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Admin para el modelo de usuario personalizado."""

    model = CustomUser
    list_display = ["username", "email", "is_staff", "is_active", "date_joined"]
    list_filter = ["is_staff", "is_active"]
    search_fields = ["username", "email"]
    ordering = ["-date_joined"]

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Información personal", {"fields": ("email",)}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser",
                                  "groups", "user_permissions")}),
        ("Fechas", {"fields": ("date_joined",)}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "password1", "password2",
                       "is_active", "is_staff"),
        }),
    )
    readonly_fields = ["date_joined"]


@admin.register(PerfilKYC)
class PerfilKYCAdmin(admin.ModelAdmin):
    """Admin para el perfil KYC."""

    list_display = [
        "user", "dni", "status", "birth_date",
        "verified_at", "self_excluded_until",
    ]
    list_filter = ["status"]
    search_fields = ["user__username", "dni"]
    readonly_fields = ["verified_at", "limits_last_raised_at"]
    ordering = ["-user__date_joined"]

    fieldsets = (
        ("Identidad", {"fields": ("user", "dni", "birth_date")}),
        ("Estado KYC", {"fields": ("status", "verified_at", "self_excluded_until")}),
        ("Límites de depósito", {
            "fields": (
                "daily_deposit_limit",
                "weekly_deposit_limit",
                "monthly_deposit_limit",
                "limits_last_raised_at",
            )
        }),
    )


@admin.register(RegistroIdempotencia)
class RegistroIdempotenciaAdmin(admin.ModelAdmin):
    """Admin para los registros de idempotencia (solo lectura)."""

    list_display = ["user", "key", "response_status", "created_at"]
    list_filter = ["response_status"]
    search_fields = ["user__username", "key"]
    ordering = ["-created_at"]
    readonly_fields = [
        "user", "key", "request_hash",
        "response_status", "response_body", "created_at",
    ]

    def has_add_permission(self, request):
        return False  # Solo lectura

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
