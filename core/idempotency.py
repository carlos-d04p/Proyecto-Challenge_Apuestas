"""
Utilities for idempotent operations.

This module keeps two compatible use cases:
- Wallet services build a canonical request hash for domain operations.
- DRF views can use IdempotencyMixin with RegistroIdempotencia.
"""

import hashlib
import json
from decimal import Decimal

from apps.accounts.models import RegistroIdempotencia


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


class IdempotencyMixin:
    """
    DRF view mixin that reuses stored responses for repeated Idempotency-Key.
    """

    IDEMPOTENCY_HEADER = "HTTP_IDEMPOTENCY_KEY"

    def _compute_hash(self, body: bytes) -> str:
        return hashlib.sha256(body).hexdigest()

    def _get_idempotency_key(self, request) -> str | None:
        return request.META.get(self.IDEMPOTENCY_HEADER)

    def _check_idempotency(self, request):
        key = self._get_idempotency_key(request)
        if not key or not request.user.is_authenticated:
            return None
        try:
            return RegistroIdempotencia.objects.get(user=request.user, key=key)
        except RegistroIdempotencia.DoesNotExist:
            return None

    def _save_idempotency(self, request, response) -> None:
        key = self._get_idempotency_key(request)
        if not key or not request.user.is_authenticated:
            return

        response_body = response.data if hasattr(response, "data") else {}

        RegistroIdempotencia.objects.get_or_create(
            user=request.user,
            key=key,
            defaults={
                "request_hash": self._compute_hash(request.body or b""),
                "response_status": response.status_code,
                "response_body": response_body,
            },
        )
