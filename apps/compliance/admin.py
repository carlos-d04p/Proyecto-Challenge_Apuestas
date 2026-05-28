from django.contrib import admin
from django.utils import timezone
from .models import AuditLog, SuspiciousActivity
from .services import append_audit_event


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["sequence", "event_type", "hash", "created_at"]
    list_filter = ["event_type", "created_at"]
    search_fields = ["sequence", "event_type", "hash", "previous_hash"]
    readonly_fields = [
        "sequence", "event_type", "payload", "payload_canonical",
        "previous_hash", "hash", "created_at"
    ]
    ordering = ["sequence"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SuspiciousActivity)
class SuspiciousActivityAdmin(admin.ModelAdmin):
    list_display = ["id", "reason", "user", "status", "detected_at", "reviewed_at"]
    list_filter = ["reason", "status", "detected_at"]
    search_fields = ["user__username", "reason", "reviewer_note"]
    readonly_fields = ["id", "reason", "user", "evidence", "detected_at", "reviewed_at"]
    ordering = ["-detected_at"]

    fieldsets = (
        ("Información General", {"fields": ("id", "user", "reason", "detected_at")}),
        ("Evidencia (JSON)", {"fields": ("evidence",)}),
        ("Revisión Compliance", {"fields": ("status", "reviewed_at", "reviewer_note")}),
    )

    def save_model(self, request, obj, form, change):
        if change:
            # Si se está modificando el estado o agregando nota
            if "status" in form.changed_data or "reviewer_note" in form.changed_data:
                obj.reviewed_at = timezone.now()
                # Registrar el cambio en AuditLog
                append_audit_event(
                    event_type="SUSPICIOUS_ACTIVITY_REVIEWED",
                    payload={
                        "activity_id": str(obj.id),
                        "status_previo": form.initial.get("status"),
                        "status_nuevo": obj.status,
                        "revisor": request.user.username,
                        "reviewed_at": obj.reviewed_at.isoformat(),
                        "reviewer_note": obj.reviewer_note or ""
                    }
                )
        super().save_model(request, obj, form, change)

