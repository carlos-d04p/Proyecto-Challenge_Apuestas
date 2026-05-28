from django.db import models


class AuditLog(models.Model):
    sequence = models.BigIntegerField(unique=True)
    event_type = models.CharField(max_length=128)
    payload = models.JSONField()
    payload_canonical = models.TextField()
    previous_hash = models.CharField(max_length=64)
    hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["sequence"], name="audit_sequence_idx"),
            models.Index(fields=["event_type"], name="audit_event_type_idx"),
            models.Index(fields=["created_at"], name="audit_created_at_idx"),
        ]
        ordering = ["sequence"]

    def __str__(self):
        return f"{self.sequence} {self.event_type}"
