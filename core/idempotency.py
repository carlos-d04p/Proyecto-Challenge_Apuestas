import hashlib
import json
from decimal import Decimal


class IdempotencyConflict(ValueError):
    pass


def build_request_hash(payload):
    canonical_payload = json.dumps(
        payload,
        default=_json_default,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def _json_default(value):
    if isinstance(value, Decimal):
        return str(value)
    return str(value)
