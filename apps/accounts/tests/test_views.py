"""
Tests de la API REST de la app accounts:
  - POST /api/accounts/registro/
  - POST /api/accounts/login/
  - GET  /api/accounts/perfil/
  - POST /api/accounts/kyc/verificar/
  - GET/PATCH /api/accounts/limites/
  - POST /api/accounts/autoexclusion/
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from unittest.mock import patch
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import CustomUser, PerfilKYC


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def usuario_verificado(db):
    """Usuario con perfil KYC en estado VERIFIED."""
    user = CustomUser.objects.create_user(
        username="usuario_ok", password="testpass123"
    )
    PerfilKYC.objects.create(
        user=user,
        dni="12345670",
        birth_date=date(1995, 1, 1),
        status=PerfilKYC.Status.VERIFIED,
        verified_at=timezone.now(),
    )
    return user


@pytest.fixture
def auth_client(api_client, usuario_verificado):
    """Cliente API autenticado con JWT."""
    refresh = RefreshToken.for_user(usuario_verificado)
    api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}"
    )
    return api_client


@pytest.fixture
def staff_user(db):
    """Usuario con permisos de staff."""
    return CustomUser.objects.create_user(
        username="staff_user", password="staffpass123", is_staff=True
    )


@pytest.fixture
def staff_client(api_client, staff_user):
    """Cliente API autenticado como staff."""
    refresh = RefreshToken.for_user(staff_user)
    api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}"
    )
    return api_client


# ── Tests de Registro ─────────────────────────────────────────────────────────

class TestRegistroView:
    URL = "/api/accounts/registro/"

    @patch("apps.accounts.serializers.verificar_kyc_async.delay")
    def test_registro_exitoso(self, mock_delay, db, api_client):
        """Registro con datos válidos devuelve 201 y encola tarea."""
        response = api_client.post(self.URL, {
            "username": "nuevo_user",
            "password": "seguro123",
            "password_confirm": "seguro123",
            "birth_date": "1995-05-15",
            "dni": "12345670",  # DNI válido
        })
        assert response.status_code == 201
        assert PerfilKYC.objects.filter(user__username="nuevo_user").exists()
        perfil = PerfilKYC.objects.get(user__username="nuevo_user")
        assert perfil.status == PerfilKYC.Status.PENDING
        mock_delay.assert_called_once_with(perfil.user.id)

    def test_registro_menor_de_edad(self, db, api_client):
        """Registro con usuario menor de 18 años devuelve 400."""
        menor = (date.today() - timedelta(days=365 * 17)).isoformat()
        response = api_client.post(self.URL, {
            "username": "menor_user",
            "password": "seguro123",
            "password_confirm": "seguro123",
            "birth_date": menor,
            "dni": "45678901",
        })
        assert response.status_code == 400
        assert "birth_date" in response.data.get("errors", {})

    def test_registro_dni_invalido(self, db, api_client):
        """Registro con DNI inválido devuelve 400."""
        response = api_client.post(self.URL, {
            "username": "user_dni_malo",
            "password": "seguro123",
            "password_confirm": "seguro123",
            "birth_date": "1995-05-15",
            "dni": "12345678",  # dígito verificador incorrecto
        })
        assert response.status_code == 400
        assert "dni" in response.data.get("errors", {})

    def test_registro_passwords_no_coinciden(self, db, api_client):
        """Registro con contraseñas diferentes devuelve 400."""
        response = api_client.post(self.URL, {
            "username": "user_pw_no_match",
            "password": "pass1234",
            "password_confirm": "pass9999",
            "birth_date": "1995-05-15",
            "dni": "12345670",
        })
        assert response.status_code == 400

    def test_registro_username_duplicado(self, db, api_client, usuario_verificado):
        """Registro con username ya existente devuelve 400."""
        response = api_client.post(self.URL, {
            "username": "usuario_ok",  # Ya existe
            "password": "seguro123",
            "password_confirm": "seguro123",
            "birth_date": "1995-05-15",
            "dni": "45678901",
        })
        assert response.status_code == 400


# ── Tests de Login ────────────────────────────────────────────────────────────

class TestLoginView:
    URL = "/api/accounts/login/"

    def test_login_exitoso(self, db, usuario_verificado, api_client):
        """Login con credenciales correctas devuelve tokens JWT."""
        response = api_client.post(self.URL, {
            "username": "usuario_ok",
            "password": "testpass123",
        })
        assert response.status_code == 200
        assert "access" in response.data
        assert "refresh" in response.data

    def test_login_credenciales_incorrectas(self, db, api_client):
        """Login con contraseña incorrecta devuelve 400."""
        response = api_client.post(self.URL, {
            "username": "inexistente",
            "password": "wrongpass",
        })
        assert response.status_code == 400


# ── Tests de Perfil ───────────────────────────────────────────────────────────

class TestPerfilView:
    URL = "/api/accounts/perfil/"

    def test_perfil_autenticado(self, db, auth_client):
        """Usuario autenticado puede ver su perfil."""
        response = auth_client.get(self.URL)
        assert response.status_code == 200
        assert "username" in response.data
        assert "status" in response.data

    def test_perfil_sin_autenticacion(self, db, api_client):
        """Sin JWT devuelve 401."""
        response = api_client.get(self.URL)
        assert response.status_code == 401


# ── Tests de Verificación KYC ─────────────────────────────────────────────────

class TestVerificarKYCView:
    URL = "/api/accounts/kyc/verificar/"

    def test_staff_puede_verificar(self, db, staff_client, db_kyc_pending):
        """Staff puede cambiar estado a VERIFIED."""
        user, perfil = db_kyc_pending
        response = staff_client.post(self.URL, {"username": user.username})
        assert response.status_code == 200
        perfil.refresh_from_db()
        assert perfil.status == PerfilKYC.Status.VERIFIED

    def test_no_staff_no_puede_verificar(self, db, auth_client, db_kyc_pending):
        """Usuario normal no puede verificar KYC (403)."""
        user, _ = db_kyc_pending
        response = auth_client.post(self.URL, {"username": user.username})
        assert response.status_code == 403


@pytest.fixture
def db_kyc_pending(db):
    """Crea un usuario con KYC en PENDING para tests de verificación."""
    user = CustomUser.objects.create_user(username="pending_user", password="pass123")
    perfil = PerfilKYC.objects.create(
        user=user, dni="45678901", birth_date=date(1998, 3, 10),
        status=PerfilKYC.Status.PENDING,
    )
    return user, perfil


# ── Tests de Límites ──────────────────────────────────────────────────────────

class TestLimitesView:
    URL = "/api/accounts/limites/"

    def test_ver_limites(self, db, auth_client):
        """Puede ver límites actuales."""
        response = auth_client.get(self.URL)
        assert response.status_code == 200
        assert "daily_deposit_limit" in response.data

    def test_bajar_limite_inmediato(self, db, auth_client, usuario_verificado):
        """Bajar un límite se aplica inmediatamente."""
        perfil = usuario_verificado.perfil_kyc
        perfil.daily_deposit_limit = Decimal("100.00")
        perfil.save()

        response = auth_client.patch(self.URL, {"daily_deposit_limit": "50.00"})
        assert response.status_code == 200
        perfil.refresh_from_db()
        assert perfil.daily_deposit_limit == Decimal("50.0000")

    def test_subir_limite_requiere_cooldown(self, db, auth_client, usuario_verificado):
        """Subir un límite recién bajado requiere cooldown de 24h."""
        perfil = usuario_verificado.perfil_kyc
        perfil.daily_deposit_limit = Decimal("100.00")
        perfil.limits_last_raised_at = timezone.now()  # Justo ahora
        perfil.save()

        response = auth_client.patch(self.URL, {"daily_deposit_limit": "200.00"})
        assert response.status_code == 400
        assert "cooldown" in str(response.data).lower() or "horas" in str(response.data).lower()


# ── Tests de Autoexclusión ────────────────────────────────────────────────────

class TestAutoexclusionView:
    URL = "/api/accounts/autoexclusion/"

    def test_autoexclusion_30_dias(self, db, auth_client, usuario_verificado):
        """Usuario puede activar autoexclusión de 30 días."""
        response = auth_client.post(self.URL, {"duracion_dias": 30})
        assert response.status_code == 200
        perfil = usuario_verificado.perfil_kyc
        perfil.refresh_from_db()
        assert perfil.status == PerfilKYC.Status.SELF_EXCLUDED
        assert perfil.self_excluded_until is not None

    def test_autoexclusion_indefinida(self, db, auth_client, usuario_verificado):
        """Usuario puede activar autoexclusión indefinida (duracion=0)."""
        response = auth_client.post(self.URL, {"duracion_dias": 0})
        assert response.status_code == 200
        perfil = usuario_verificado.perfil_kyc
        perfil.refresh_from_db()
        assert perfil.status == PerfilKYC.Status.SELF_EXCLUDED
        assert perfil.self_excluded_until is None

    def test_duracion_invalida(self, db, auth_client):
        """Duración inválida devuelve 400."""
        response = auth_client.post(self.URL, {"duracion_dias": 45})
        assert response.status_code == 400
