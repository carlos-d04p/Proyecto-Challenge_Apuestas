import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class AuditLogQuerySet(models.QuerySet):
    def update(self, *args, **kwargs):
        raise ValidationError("AuditLog es inmutable y no puede ser modificado.")

    def delete(self, *args, **kwargs):
        raise ValidationError("AuditLog es inmutable y no puede ser eliminado.")


class AuditLogManager(models.Manager):
    def get_queryset(self):
        return AuditLogQuerySet(self.model, using=self._db)


class AuditLog(models.Model):
    sequence = models.BigIntegerField(unique=True)
    event_type = models.CharField(max_length=128)
    payload = models.JSONField()
    payload_canonical = models.TextField()
    previous_hash = models.CharField(max_length=64)
    hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AuditLogManager()

    class Meta:
        indexes = [
            models.Index(fields=["sequence"], name="audit_sequence_idx"),
            models.Index(fields=["event_type"], name="audit_event_type_idx"),
            models.Index(fields=["created_at"], name="audit_created_at_idx"),
        ]
        ordering = ["sequence"]

    def __str__(self):
        return f"{self.sequence} {self.event_type}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("AuditLog es inmutable y no puede ser modificado.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("AuditLog es inmutable y no puede ser eliminado.")


class SuspiciousActivity(models.Model):
    class Reason(models.TextChoices):
        SHARED_IP = "SHARED_IP", "Inicio de sesión desde IP compartida"
        DEP_WD = "DEP_WD", "Depósito y retiro rápido sin juego"
        PATTERN = "PATTERN", "Patrón sospechoso de apuestas o KYC"
        LIMIT_EXCEEDED = "LIMIT_EXCEEDED", "Exceso de límite de depósito"

    class Status(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        REVISADO = "REVISADO", "Revisado"
        FALSO_POSITIVO = "FALSO_POSITIVO", "Falso Positivo"

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="suspicious_activities",
        null=True,
        blank=True
    )
    reason = models.CharField(max_length=50, choices=Reason.choices)
    evidence = models.JSONField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDIENTE)
    detected_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer_note = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "actividad_sospechosa"
        ordering = ["-detected_at"]
        verbose_name = "Actividad Sospechosa"
        verbose_name_plural = "Actividades Sospechosas"

    def __str__(self):
        return f"{self.reason} — {self.user} — {self.status}"

