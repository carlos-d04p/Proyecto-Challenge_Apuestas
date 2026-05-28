"""
Vistas web (HTML) para la app accounts.

- registro_view: Formulario de registro de usuario
- login_view:    Formulario de login
- perfil_view:   Panel de perfil con KYC, límites y autoexclusión
"""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views import View

from .models import PerfilKYC, CustomUser
from .validators import validar_dni_peruano, validar_mayoria_de_edad
from .serializers import RegistroSerializer, LimitesSerializer, AutoexclusionSerializer
from .utils import verificar_token_email, check_and_increment_login_fails, reset_login_fails
from .tasks import verificar_kyc_async
from django.core.exceptions import ValidationError


def registro_view(request):
    """Página de registro de nuevo usuario."""
    if request.user.is_authenticated:
        return redirect("markets:event_list")

    errores = {}
    datos = {}

    if request.method == "POST":
        datos = request.POST.dict()
        datos.pop("csrfmiddlewaretoken", None)

        serializer = RegistroSerializer(data=datos, context={"request": request})
        if serializer.is_valid():
            user = serializer.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(
                request,
                "¡Cuenta creada exitosamente! Tu perfil está pendiente de verificación KYC."
            )
            return redirect("markets:event_list")
        else:
            for campo, errores_campo in serializer.errors.items():
                errores[campo] = "; ".join(
                    str(e) for e in errores_campo
                )

    return render(request, "accounts/registro.html", {
        "errores": errores,
        "datos": datos,
    })


def _post_login_redirect(user):
    """A dónde mandar al usuario tras autenticarse."""
    if user.is_staff:
        return "/backoffice/"
    return "markets:event_list"


def login_view(request):
    """Página de login."""
    if request.user.is_authenticated:
        return redirect(_post_login_redirect(request.user))

    error = None

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        
        # Check if already blocked
        try:
            user_obj = CustomUser.objects.get(username=username)
            if hasattr(user_obj, 'perfil_kyc') and user_obj.perfil_kyc.status == PerfilKYC.Status.BLOCKED:
                return render(request, "accounts/login.html", {
                    "error": "Tu cuenta está bloqueada temporalmente por seguridad. Contacta al soporte."
                })
        except CustomUser.DoesNotExist:
            pass
            
        user = authenticate(request, username=username, password=password)

        if user and user.is_active:
            reset_login_fails(username)
            login(request, user)
            next_url = request.GET.get("next") or _post_login_redirect(user)
            return redirect(next_url)
        else:
            bloqueado = check_and_increment_login_fails(username)
            if bloqueado:
                error = "Has excedido el número de intentos fallidos. Tu cuenta ha sido BLOQUEADA."
            else:
                error = "Usuario o contraseña incorrectos."

    return render(request, "accounts/login.html", {"error": error})


def logout_view(request):
    """Cerrar sesión."""
    logout(request)
    return redirect("accounts_web:login")


@login_required(login_url="/accounts/login/")
def perfil_view(request):
    """Panel de perfil: estado KYC, límites, autoexclusión."""
    # Los usuarios staff no son clientes finales — su lugar es el backoffice.
    if request.user.is_staff:
        return redirect("/backoffice/")
    try:
        perfil = request.user.perfil_kyc
    except PerfilKYC.DoesNotExist:
        perfil = None

    mensaje = None
    errores = {}

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "limites" and perfil:
            datos_limites = {}
            for campo in ["daily_deposit_limit", "weekly_deposit_limit", "monthly_deposit_limit"]:
                val = request.POST.get(campo, "").strip()
                if val:
                    datos_limites[campo] = val

            serializer = LimitesSerializer(
                data=datos_limites, context={"perfil": perfil}
            )
            if serializer.is_valid():
                serializer.save(perfil=perfil)
                mensaje = "✅ Límites actualizados correctamente."
            else:
                for campo, errs in serializer.errors.items():
                    errores[campo] = "; ".join(str(e) for e in errs)

        elif action == "autoexclusion" and perfil:
            duracion = request.POST.get("duracion_dias", "")
            try:
                duracion = int(duracion)
            except ValueError:
                errores["autoexclusion"] = "Duración inválida."
            else:
                serializer = AutoexclusionSerializer(
                    data={"duracion_dias": duracion}, context={"perfil": perfil}
                )
                if serializer.is_valid():
                    serializer.save(perfil=perfil)
                    logout(request)
                    return redirect("accounts_web:login")
                else:
                    for campo, errs in serializer.errors.items():
                        errores[campo] = "; ".join(str(e) for e in errs)

    return render(request, "accounts/perfil.html", {
        "perfil": perfil,
        "mensaje": mensaje,
        "errores": errores,
        "COOLDOWN_HORAS": 24,
    })

class VerificarEmailView(View):
    def get(self, request, token):
        user_id = verificar_token_email(token)
        if not user_id:
            messages.error(request, "El enlace de verificación es inválido o ha expirado.")
            return redirect('accounts_web:login')
        
        try:
            user = CustomUser.objects.get(id=user_id)
            if user.is_email_verified:
                messages.info(request, "Tu email ya estaba verificado.")
            else:
                user.is_email_verified = True
                user.save()
                messages.success(request, "¡Tu email ha sido verificado! Ahora estamos procesando tu KYC...")
                # Ahora que el email está verificado, disparamos el KYC
                verificar_kyc_async.delay(user.id)
                
            return redirect('accounts_web:login')
        except CustomUser.DoesNotExist:
            messages.error(request, "Usuario no encontrado.")
            return redirect('accounts_web:login')
