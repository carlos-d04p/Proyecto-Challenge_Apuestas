"""
Vistas de la API REST para la app accounts.

Endpoints:
  POST   /api/accounts/registro/         — Registro de usuario
  POST   /api/accounts/login/            — Login con JWT
  POST   /api/accounts/token/refresh/    — Refresh del token JWT
  GET    /api/accounts/perfil/           — Perfil + estado KYC
  POST   /api/accounts/kyc/verificar/    — Verificar KYC (solo staff)
  PATCH  /api/accounts/limites/          — Actualizar límites de depósito
  POST   /api/accounts/autoexclusion/    — Activar autoexclusión
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PerfilKYC
from .serializers import (
    AutoexclusionSerializer,
    LimitesSerializer,
    LoginSerializer,
    PerfilKYCSerializer,
    RegistroSerializer,
)


# ── Registro ──────────────────────────────────────────────────────────────────

class RegistroView(APIView):
    """
    POST /api/accounts/registro/

    Registra un nuevo usuario con validación de:
      - Mayoría de edad (≥ 18 años via birth_date)
      - DNI peruano (dígito verificador)
      - Contraseñas coincidentes

    Crea CustomUser + PerfilKYC en estado PENDING.
    No requiere autenticación.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegistroSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = serializer.save()
        return Response(
            {
                "mensaje": "Registro exitoso. Tu cuenta está pendiente de verificación KYC.",
                "username": user.username,
                "estado_kyc": PerfilKYC.Status.PENDING,
            },
            status=status.HTTP_201_CREATED,
        )


# ── Login ─────────────────────────────────────────────────────────────────────

class LoginView(APIView):
    """
    POST /api/accounts/login/

    Autenticación con username + password.
    Devuelve access token (1h) y refresh token (7d).
    No requiere autenticación previa.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = serializer.validated_data["user"]
        tokens = serializer.get_tokens(user)
        return Response(
            {
                "mensaje": f"Bienvenido, {user.username}.",
                "access": tokens["access"],
                "refresh": tokens["refresh"],
            },
            status=status.HTTP_200_OK,
        )


# ── Perfil ────────────────────────────────────────────────────────────────────

class PerfilView(APIView):
    """
    GET /api/accounts/perfil/

    Devuelve los datos del usuario autenticado y su perfil KYC
    (estado, límites de depósito, autoexclusión).
    Requiere autenticación JWT.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            perfil = request.user.perfil_kyc
        except PerfilKYC.DoesNotExist:
            return Response(
                {"error": "No se encontró un perfil KYC para este usuario."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = PerfilKYCSerializer(perfil)
        return Response(serializer.data)


# ── Verificación KYC ──────────────────────────────────────────────────────────

class VerificarKYCView(APIView):
    """
    POST /api/accounts/kyc/verificar/

    Cambia el estado del KYC de PENDING a VERIFIED.
    Solo puede ser ejecutado por staff (administradores).

    Body: { "username": "usuario_a_verificar" }
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        username = request.data.get("username")
        if not username:
            return Response(
                {"error": "El campo 'username' es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            from .models import CustomUser
            user = CustomUser.objects.get(username=username)
            perfil = user.perfil_kyc
        except (CustomUser.DoesNotExist, PerfilKYC.DoesNotExist):
            return Response(
                {"error": f"No se encontró usuario o perfil KYC para '{username}'."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if perfil.status == PerfilKYC.Status.BLOCKED:
            return Response(
                {"error": "No se puede verificar un usuario bloqueado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if perfil.status == PerfilKYC.Status.VERIFIED:
            return Response(
                {"mensaje": f"El usuario '{username}' ya está verificado."},
                status=status.HTTP_200_OK,
            )

        perfil.status = PerfilKYC.Status.VERIFIED
        perfil.verified_at = timezone.now()
        perfil.save()

        return Response(
            {
                "mensaje": f"KYC de '{username}' verificado exitosamente.",
                "estado": PerfilKYC.Status.VERIFIED,
                "verified_at": perfil.verified_at,
            },
            status=status.HTTP_200_OK,
        )


# ── Límites de depósito ───────────────────────────────────────────────────────

class LimitesView(APIView):
    """
    GET  /api/accounts/limites/   — Ver límites actuales
    PATCH /api/accounts/limites/  — Actualizar límites

    Reglas:
      - Bajar un límite: efecto inmediato.
      - Subir un límite: cooldown de 24h desde la última subida.
    Requiere autenticación JWT y estado KYC VERIFIED.
    """
    permission_classes = [IsAuthenticated]

    def _get_perfil_o_error(self, request):
        try:
            return request.user.perfil_kyc, None
        except PerfilKYC.DoesNotExist:
            return None, Response(
                {"error": "No se encontró perfil KYC."},
                status=status.HTTP_404_NOT_FOUND,
            )

    def get(self, request):
        perfil, error = self._get_perfil_o_error(request)
        if error:
            return error
        return Response({
            "daily_deposit_limit": perfil.daily_deposit_limit,
            "weekly_deposit_limit": perfil.weekly_deposit_limit,
            "monthly_deposit_limit": perfil.monthly_deposit_limit,
            "limits_last_raised_at": perfil.limits_last_raised_at,
        })

    def patch(self, request):
        perfil, error = self._get_perfil_o_error(request)
        if error:
            return error

        serializer = LimitesSerializer(
            data=request.data,
            context={"perfil": perfil},
        )
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        perfil_actualizado = serializer.save(perfil=perfil)
        return Response({
            "mensaje": "Límites actualizados correctamente.",
            "daily_deposit_limit": perfil_actualizado.daily_deposit_limit,
            "weekly_deposit_limit": perfil_actualizado.weekly_deposit_limit,
            "monthly_deposit_limit": perfil_actualizado.monthly_deposit_limit,
            "limits_last_raised_at": perfil_actualizado.limits_last_raised_at,
        })


# ── Autoexclusión ─────────────────────────────────────────────────────────────

class AutoexclusionView(APIView):
    """
    POST /api/accounts/autoexclusion/

    Activa la autoexclusión del usuario.
    Duraciones válidas: 7, 30, 90 días o 0 (indefinida).
    El usuario NO puede revertirla antes del tiempo establecido.
    Requiere autenticación JWT.

    Body: { "duracion_dias": 30 }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            perfil = request.user.perfil_kyc
        except PerfilKYC.DoesNotExist:
            return Response(
                {"error": "No se encontró perfil KYC."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AutoexclusionSerializer(
            data=request.data,
            context={"perfil": perfil},
        )
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        perfil_actualizado = serializer.save(perfil=perfil)
        hasta = perfil_actualizado.self_excluded_until

        return Response(
            {
                "mensaje": "Autoexclusión activada correctamente.",
                "estado": PerfilKYC.Status.SELF_EXCLUDED,
                "excluido_hasta": hasta if hasta else "Indefinida",
                "aviso": (
                    "FairBet Lab se compromete al juego responsable. "
                    "Durante tu período de autoexclusión no podrás realizar apuestas."
                ),
            },
            status=status.HTTP_200_OK,
        )
