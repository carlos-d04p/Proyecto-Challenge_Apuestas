import hashlib
import json

from django.db import transaction

from apps.compliance.models import AuditLog


GENESIS_HASH = "0" * 64


def append_audit_event(*, event_type, payload):
    canonical_payload = canonicalize_payload(payload)

    with transaction.atomic():
        previous_entry = (
            AuditLog.objects.select_for_update()
            .order_by("-sequence")
            .first()
        )
        previous_hash = previous_entry.hash if previous_entry else GENESIS_HASH
        sequence = previous_entry.sequence + 1 if previous_entry else 1
        event_hash = hashlib.sha256(
            f"{previous_hash}{canonical_payload}".encode("utf-8")
        ).hexdigest()

        return AuditLog.objects.create(
            sequence=sequence,
            event_type=event_type,
            payload=payload,
            payload_canonical=canonical_payload,
            previous_hash=previous_hash,
            hash=event_hash,
        )


def canonicalize_payload(payload):
    return json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    )
