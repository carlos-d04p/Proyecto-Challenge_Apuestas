"""
Serializers para la app accounts.

- RegistroSerializer:     validación completa de registro (DNI + edad)
- LoginSerializer:        login con username + password
- PerfilKYCSerializer:    datos de perfil y estado KYC
- LimitesSerializer:      actualización de límites con cooldown de 24h
- AutoexclusionSerializer: configuración de autoexclusión
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import CustomUser, PerfilKYC
from .validators import validar_dni_peruano, validar_mayoria_de_edad
from .tasks import verificar_kyc_async, enviar_email_verificacion_async
from .utils import generar_token_email, check_and_increment_login_fails, reset_login_fails


# ── Registro ──────────────────────────────────────────────────────────────────

class RegistroSerializer(serializers.Serializer):
    """
    Serializer para el registro de nuevos usuarios.
    Valida mayoría de edad (≥18) y DNI peruano con dígito verificador.
    Crea CustomUser + PerfilKYC en estado PENDING.
    """

    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(min_length=8, write_only=True)
    password_confirm = serializers.CharField(write_only=True)
    birth_date = serializers.DateField()
    dni = serializers.CharField(max_length=8, min_length=8)
    dni_verificador = serializers.CharField(max_length=1, min_length=1, write_only=True)

    def validate_username(self, value):
        if CustomUser.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "Este nombre de usuario ya está en uso."
            )
        return value

    def validate_dni(self, value):
        if PerfilKYC.objects.filter(dni=value).exists():
            raise serializers.ValidationError(
                "Este DNI ya está registrado en el sistema."
            )
        return value

    def validate_birth_date(self, value):
        try:
            validar_mayoria_de_edad(value)
        except Exception as e:
            raise serializers.ValidationError(str(e))
        return value

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("password_confirm"):
            raise serializers.ValidationError(
                {"password_confirm": "Las contraseñas no coinciden."}
            )
        
        # Validar algoritmo del DNI
        dni = attrs.get("dni")
        verificador = attrs.get("dni_verificador")
        if dni and verificador:
            try:
                validar_dni_peruano(dni, verificador)
            except Exception as e:
                raise serializers.ValidationError({"dni": str(e)})

        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        validated_data.pop("dni_verificador", None)
        password = validated_data.pop("password")
        birth_date = validated_data.pop("birth_date")
        dni = validated_data.pop("dni")

        user = CustomUser.objects.create_user(password=password, **validated_data)
        PerfilKYC.objects.create(
            user=user,
            dni=dni,
            birth_date=birth_date,
            status=PerfilKYC.Status.PENDING,
        )
        
        # Generar token de email
        token = generar_token_email(user.id)
        request = self.context.get("request")
        if request:
            base_url = request.build_absolute_uri('/')[:-1]
        else:
            base_url = "http://127.0.0.1:8000"

        # 🚀 Encolar la tarea asíncrona de envío de email
        enviar_email_verificacion_async.delay(user.id, token, base_url)
        
        return user


# ── Login ─────────────────────────────────────────────────────────────────────

class LoginSerializer(serializers.Serializer):
    """
    Serializer para login. Devuelve tokens JWT (access + refresh).
    """

    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        username = attrs["username"]
        # Check if user is already blocked
        try:
            user_obj = CustomUser.objects.get(username=username)
            if hasattr(user_obj, 'perfil_kyc') and user_obj.perfil_kyc.status == PerfilKYC.Status.BLOCKED:
                raise serializers.ValidationError(
                    "Tu cuenta está bloqueada temporalmente por seguridad. Contacta al soporte."
                )
        except CustomUser.DoesNotExist:
            pass
            
        user = authenticate(
            username=username,
            password=attrs["password"],
        )
        if not user:
            bloqueado = check_and_increment_login_fails(username)
            if bloqueado:
                raise serializers.ValidationError(
                    "Has excedido el número de intentos fallidos. Tu cuenta ha sido BLOQUEADA."
                )
            raise serializers.ValidationError(
                "Credenciales incorrectas. Verifica tu usuario y contraseña."
            )
        if not user.is_active:
            raise serializers.ValidationError(
                "Tu cuenta está inactiva. Contacta al soporte."
            )
            
        reset_login_fails(username)
        attrs["user"] = user
        return attrs

    def get_tokens(self, user):
        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }


# ── Perfil KYC ────────────────────────────────────────────────────────────────

class PerfilKYCSerializer(serializers.ModelSerializer):
    """Serializer de solo lectura para el perfil KYC del usuario."""

    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    date_joined = serializers.DateTimeField(source="user.date_joined", read_only=True)
    is_autoexcluido = serializers.BooleanField(read_only=True)
    puede_apostar = serializers.BooleanField(read_only=True)

    class Meta:
        model = PerfilKYC
        fields = [
            "username", "email", "date_joined",
            "dni", "birth_date", "status",
            "verified_at", "self_excluded_until",
            "daily_deposit_limit", "weekly_deposit_limit", "monthly_deposit_limit",
            "limits_last_raised_at",
            "is_autoexcluido", "puede_apostar",
        ]


# ── Límites de depósito ───────────────────────────────────────────────────────

COOLDOWN_HORAS = 24


class LimitesSerializer(serializers.Serializer):
    """
    Serializer para actualizar límites de depósito.

    Reglas:
      - Bajar límite → efecto inmediato.
      - Subir límite → requiere 24h desde la última subida (limits_last_raised_at).
    """

    daily_deposit_limit = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, allow_null=True
    )
    weekly_deposit_limit = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, allow_null=True
    )
    monthly_deposit_limit = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, allow_null=True
    )

    def validate(self, attrs):
        perfil = self.context["perfil"]
        now = timezone.now()

        campos = ["daily_deposit_limit", "weekly_deposit_limit", "monthly_deposit_limit"]
        sube_algun_limite = False

        for campo in campos:
            nuevo = attrs.get(campo)
            if nuevo is None:
                continue
            actual = getattr(perfil, campo)

            # Verificar si está subiendo el límite
            if actual is None or nuevo > actual:
                sube_algun_limite = True

        if sube_algun_limite:
            last_raised = perfil.limits_last_raised_at
            if last_raised:
                tiempo_transcurrido = now - last_raised
                if tiempo_transcurrido < timedelta(hours=COOLDOWN_HORAS):
                    horas_restantes = COOLDOWN_HORAS - (tiempo_transcurrido.total_seconds() / 3600)
                    raise serializers.ValidationError(
                        f"Para subir un límite debes esperar {horas_restantes:.1f} horas más "
                        f"desde la última modificación (cooldown de 24h)."
                    )

        return attrs

    def save(self, perfil: PerfilKYC):
        campos = ["daily_deposit_limit", "weekly_deposit_limit", "monthly_deposit_limit"]
        sube_algun_limite = False

        for campo in campos:
            nuevo = self.validated_data.get(campo)
            if nuevo is None:
                continue
            actual = getattr(perfil, campo)

            if actual is None or nuevo > actual:
                sube_algun_limite = True

            setattr(perfil, campo, nuevo)

        if sube_algun_limite:
            perfil.limits_last_raised_at = timezone.now()

        perfil.save()
        return perfil


# ── Autoexclusión ─────────────────────────────────────────────────────────────

DURACIONES_VALIDAS = {
    7: "7 días",
    30: "30 días",
    90: "90 días",
    0: "Indefinida",
}


class AutoexclusionSerializer(serializers.Serializer):
    """
    Serializer para activar la autoexclusión.

    Duraciones válidas: 7, 30, 90 días o 0 (indefinida).
    El usuario NO puede revertirla antes del tiempo establecido.
    """

    duracion_dias = serializers.IntegerField(
        help_text="Duración en días: 7, 30, 90 o 0 (indefinida)."
    )

    def validate_duracion_dias(self, value):
        if value not in DURACIONES_VALIDAS:
            raise serializers.ValidationError(
                f"Duración inválida. Opciones: {list(DURACIONES_VALIDAS.keys())} "
                f"(0 = indefinida)."
            )
        return value

    def validate(self, attrs):
        perfil = self.context["perfil"]
        if perfil.status == PerfilKYC.Status.BLOCKED:
            raise serializers.ValidationError(
                "Tu cuenta está bloqueada. No puedes gestionar la autoexclusión."
            )
        return attrs

    def save(self, perfil: PerfilKYC):
        duracion = self.validated_data["duracion_dias"]
        perfil.status = PerfilKYC.Status.SELF_EXCLUDED

        if duracion == 0:
            perfil.self_excluded_until = None  # Indefinida
        else:
            perfil.self_excluded_until = timezone.now() + timedelta(days=duracion)

        perfil.save()
        return perfil
