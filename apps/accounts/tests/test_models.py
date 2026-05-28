"""
Tests de los modelos de la app accounts:
  - CustomUser: creación, manager, UUID PK
  - PerfilKYC: FSM, propiedades de negocio
  - RegistroIdempotencia: restricción unique
"""
import pytest
from datetime import date, timedelta
from django.utils import timezone
from django.db import IntegrityError

from apps.accounts.models import CustomUser, PerfilKYC, RegistroIdempotencia


@pytest.fixture
def usuario_base(db):
    """Crea un usuario de prueba estándar."""
    user = CustomUser.objects.create_user(
        username="testuser",
        password="testpass123",
        email="test@example.com",
    )
    return user


@pytest.fixture
def perfil_kyc_base(db, usuario_base):
    """Crea un perfil KYC para el usuario base."""
    return PerfilKYC.objects.create(
        user=usuario_base,
        dni="12345670",
        birth_date=date(1995, 6, 15),
        status=PerfilKYC.Status.PENDING,
    )


class TestCustomUser:
    """Tests del modelo CustomUser."""

    def test_crear_usuario(self, db):
        """Se puede crear un usuario con username y password."""
        user = CustomUser.objects.create_user(
            username="nuevo_usuario",
            password="password123",
        )
        assert user.username == "nuevo_usuario"
        assert user.is_active is True
        assert user.is_staff is False
        assert user.check_password("password123")

    def test_pk_es_uuid(self, usuario_base):
        """El campo id debe ser un UUID, no un entero."""
        import uuid
        assert isinstance(usuario_base.id, uuid.UUID)

    def test_username_unico(self, db, usuario_base):
        """No se pueden crear dos usuarios con el mismo username."""
        with pytest.raises(Exception):
            CustomUser.objects.create_user(
                username="testuser",  # Ya existe
                password="otrapass123",
            )

    def test_crear_superuser(self, db):
        """Crear superuser establece is_staff e is_superuser."""
        superuser = CustomUser.objects.create_superuser(
            username="admin_test",
            password="adminpass123",
        )
        assert superuser.is_staff is True
        assert superuser.is_superuser is True

    def test_str_retorna_username(self, usuario_base):
        """__str__ retorna el username del usuario."""
        assert str(usuario_base) == "testuser"


class TestPerfilKYC:
    """Tests del modelo PerfilKYC y su FSM de estados."""

    def test_estado_inicial_es_pending(self, perfil_kyc_base):
        """El perfil KYC inicia en estado PENDING."""
        assert perfil_kyc_base.status == PerfilKYC.Status.PENDING

    def test_transicion_pending_a_verified(self, perfil_kyc_base):
        """Se puede cambiar el estado de PENDING a VERIFIED."""
        perfil_kyc_base.status = PerfilKYC.Status.VERIFIED
        perfil_kyc_base.verified_at = timezone.now()
        perfil_kyc_base.save()
        perfil_kyc_base.refresh_from_db()
        assert perfil_kyc_base.status == PerfilKYC.Status.VERIFIED

    def test_puede_apostar_solo_si_verified(self, perfil_kyc_base):
        """puede_apostar es True solo cuando status == VERIFIED."""
        assert perfil_kyc_base.puede_apostar is False  # PENDING
        perfil_kyc_base.status = PerfilKYC.Status.VERIFIED
        perfil_kyc_base.save()
        assert perfil_kyc_base.puede_apostar is True

    def test_autoexclusion_temporal(self, perfil_kyc_base):
        """Auto-exclusión temporal está activa si la fecha no ha expirado."""
        perfil_kyc_base.status = PerfilKYC.Status.SELF_EXCLUDED
        perfil_kyc_base.self_excluded_until = timezone.now() + timedelta(days=30)
        perfil_kyc_base.save()
        assert perfil_kyc_base.is_autoexcluido is True

    def test_autoexclusion_expirada(self, perfil_kyc_base):
        """Auto-exclusión expirada ya no bloquea al usuario."""
        perfil_kyc_base.status = PerfilKYC.Status.SELF_EXCLUDED
        perfil_kyc_base.self_excluded_until = timezone.now() - timedelta(days=1)
        perfil_kyc_base.save()
        assert perfil_kyc_base.is_autoexcluido is False

    def test_autoexclusion_indefinida(self, perfil_kyc_base):
        """Auto-exclusión indefinida (sin fecha) siempre está activa."""
        perfil_kyc_base.status = PerfilKYC.Status.SELF_EXCLUDED
        perfil_kyc_base.self_excluded_until = None  # Indefinida
        perfil_kyc_base.save()
        assert perfil_kyc_base.is_autoexcluido is True

    def test_dni_unico(self, db, perfil_kyc_base):
        """No se pueden registrar dos perfiles con el mismo DNI."""
        otro_usuario = CustomUser.objects.create_user(
            username="otro_user", password="pass123"
        )
        with pytest.raises(IntegrityError):
            PerfilKYC.objects.create(
                user=otro_usuario,
                dni="12345670",  # DNI ya en uso
                birth_date=date(1990, 1, 1),
            )


class TestRegistroIdempotencia:
    """Tests del modelo RegistroIdempotencia."""

    def test_crear_registro(self, db, usuario_base):
        """Se puede crear un registro de idempotencia."""
        registro = RegistroIdempotencia.objects.create(
            user=usuario_base,
            key="mi-clave-unica-001",
            request_hash="abc123" * 10,
            response_status=201,
            response_body={"status": "ok"},
        )
        assert registro.pk is not None

    def test_restriccion_unique_user_key(self, db, usuario_base):
        """No se puede duplicar (user, key) — debe ser único."""
        RegistroIdempotencia.objects.create(
            user=usuario_base,
            key="clave-duplicada",
            request_hash="hash1" * 12,
            response_status=200,
            response_body={},
        )
        with pytest.raises(IntegrityError):
            RegistroIdempotencia.objects.create(
                user=usuario_base,
                key="clave-duplicada",  # Misma clave, mismo usuario
                request_hash="hash2" * 12,
                response_status=200,
                response_body={},
            )
