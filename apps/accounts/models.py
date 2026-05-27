"""
Modelos de la app accounts.

Tablas:
  - usuario            → CustomUser (modelo personalizado)
  - perfil_kyc         → PerfilKYC (DNI, edad, FSM de estados, límites)
  - registro_idempotencia → RegistroIdempotencia (prevención de duplicados)
"""
import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone

from .managers import CustomUserManager


# ── Usuario ───────────────────────────────────────────────────────────────────

class CustomUser(AbstractBaseUser, PermissionsMixin):
    """
    Modelo de usuario personalizado.
    Reemplaza al User de Django con UUID como PK y tabla 'usuario'.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(blank=True, null=True)
    is_email_verified = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = CustomUserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "usuario"
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return self.username


# ── Perfil KYC ────────────────────────────────────────────────────────────────

class PerfilKYC(models.Model):
    """
    Perfil de verificación de identidad (KYC) del usuario.

    FSM de estados:
      PENDING → VERIFIED (solo staff)
      PENDING → BLOCKED  (admin)
      VERIFIED → BLOCKED (admin)
      VERIFIED → SELF_EXCLUDED (el propio usuario)
      SELF_EXCLUDED → VERIFIED (solo si expiró self_excluded_until)
      BLOCKED → (estado terminal, irreversible)
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente de verificación"
        VERIFIED = "VERIFIED", "Verificado"
        BLOCKED = "BLOCKED", "Bloqueado"
        SELF_EXCLUDED = "SELF_EXCLUDED", "Auto-excluido"

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="perfil_kyc",
    )
    dni = models.CharField(max_length=8, unique=True)
    birth_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    self_excluded_until = models.DateTimeField(null=True, blank=True)

    # Límites de depósito configurables
    daily_deposit_limit = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    weekly_deposit_limit = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    monthly_deposit_limit = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    limits_last_raised_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "perfil_kyc"
        verbose_name = "Perfil KYC"
        verbose_name_plural = "Perfiles KYC"

    def __str__(self):
        return f"KYC de {self.user.username} — {self.status}"

    # ── Propiedades de negocio ─────────────────────────────────────────────

    @property
    def is_autoexcluido(self):
        """True si el usuario está actualmente auto-excluido."""
        if self.status != self.Status.SELF_EXCLUDED:
            return False
        if self.self_excluded_until is None:
            return True  # Exclusión indefinida
        return timezone.now() < self.self_excluded_until

    @property
    def puede_apostar(self):
        """True si el usuario puede realizar apuestas."""
        return self.status == self.Status.VERIFIED and not self.is_autoexcluido


# ── Registro de Idempotencia ──────────────────────────────────────────────────

class RegistroIdempotencia(models.Model):
    """
    Prevención de operaciones duplicadas.
    Almacena el hash de la request y la respuesta para claves de idempotencia.
    """

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="registros_idempotencia",
    )
    key = models.CharField(max_length=128)
    request_hash = models.CharField(max_length=64)  # SHA-256 del body
    response_status = models.SmallIntegerField()
    response_body = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "registro_idempotencia"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "key"], name="unique_idempotencia_user_key"
            )
        ]
        verbose_name = "Registro de Idempotencia"
        verbose_name_plural = "Registros de Idempotencia"

    def __str__(self):
        return f"[{self.user.username}] {self.key} → {self.response_status}"
