"""
Mixin de idempotencia para vistas de la API REST.

Previene operaciones duplicadas almacenando el hash SHA-256 del
request body y reutilizando la respuesta anterior si la clave
de idempotencia ya existe para ese usuario.

Uso:
    class MiView(IdempotencyMixin, APIView):
        ...

    El cliente debe enviar el header: Idempotency-Key: <uuid-único>
"""
import hashlib
import json

from apps.accounts.models import RegistroIdempotencia


class IdempotencyMixin:
    """
    Mixin que implementa el patrón de idempotencia para views de DRF.

    Si el header 'Idempotency-Key' está presente y ya existe un registro
    para ese (user, key), se devuelve la respuesta almacenada sin
    volver a procesar la solicitud.
    """

    IDEMPOTENCY_HEADER = "HTTP_IDEMPOTENCY_KEY"

    def _compute_hash(self, body: bytes) -> str:
        """Calcula el SHA-256 del cuerpo de la petición."""
        return hashlib.sha256(body).hexdigest()

    def _get_idempotency_key(self, request) -> str | None:
        """Obtiene la clave de idempotencia del header de la request."""
        return request.META.get(self.IDEMPOTENCY_HEADER)

    def _check_idempotency(self, request):
        """
        Verifica si ya existe un registro para (user, key).

        Returns:
            RegistroIdempotencia | None
        """
        key = self._get_idempotency_key(request)
        if not key or not request.user.is_authenticated:
            return None
        try:
            return RegistroIdempotencia.objects.get(
                user=request.user, key=key
            )
        except RegistroIdempotencia.DoesNotExist:
            return None

    def _save_idempotency(self, request, response) -> None:
        """
        Guarda el registro de idempotencia tras procesar la request.
        Solo guarda si el header está presente y el usuario está autenticado.
        """
        key = self._get_idempotency_key(request)
        if not key or not request.user.is_authenticated:
            return

        body = request.body or b""
        request_hash = self._compute_hash(body)

        try:
            response_body = response.data if hasattr(response, "data") else {}
        except Exception:
            response_body = {}

        RegistroIdempotencia.objects.get_or_create(
            user=request.user,
            key=key,
            defaults={
                "request_hash": request_hash,
                "response_status": response.status_code,
                "response_body": response_body,
            },
        )
