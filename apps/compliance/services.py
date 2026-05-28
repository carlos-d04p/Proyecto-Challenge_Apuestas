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


def verify_audit_chain():
    """
    Verifica la integridad de toda la cadena de auditoría (hash chain).
    Retorna un diccionario con el resultado del análisis.
    """
    logs = AuditLog.objects.all().order_by("sequence")
    if not logs.exists():
        return {
            "valid": True,
            "message": "La cadena de auditoría está vacía y es válida.",
            "error_sequence": None,
        }

    expected_sequence = 1
    previous_hash = GENESIS_HASH

    for entry in logs:
        # 1. Verificar secuencia consecutiva
        if entry.sequence != expected_sequence:
            return {
                "valid": False,
                "message": f"Quiebre en la secuencia. Esperado: {expected_sequence}, Encontrado: {entry.sequence}.",
                "error_sequence": entry.sequence,
            }

        # 2. Verificar correspondencia del hash previo
        if entry.previous_hash != previous_hash:
            return {
                "valid": False,
                "message": f"Discrepancia en previous_hash en secuencia {entry.sequence}. Esperado: {previous_hash}, Encontrado: {entry.previous_hash}.",
                "error_sequence": entry.sequence,
            }

        # 3. Recalcular y verificar el hash actual
        calculated_canonical = canonicalize_payload(entry.payload)
        recalculated_hash = hashlib.sha256(
            f"{previous_hash}{calculated_canonical}".encode("utf-8")
        ).hexdigest()

        if entry.hash != recalculated_hash:
            return {
                "valid": False,
                "message": f"Hash corrupto en secuencia {entry.sequence}. Calculado: {recalculated_hash}, Almacenado: {entry.hash}.",
                "error_sequence": entry.sequence,
            }

        # Avanzar punteros
        previous_hash = entry.hash
        expected_sequence += 1

    return {
        "valid": True,
        "message": f"Cadena verificada con éxito. Total registros: {logs.count()}.",
        "error_sequence": None,
    }

