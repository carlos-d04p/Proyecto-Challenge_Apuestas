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

from .models import PerfilKYC
from .validators import validar_dni_peruano, validar_mayoria_de_edad
from .serializers import RegistroSerializer, LimitesSerializer, AutoexclusionSerializer
from django.core.exceptions import ValidationError


def registro_view(request):
    """Página de registro de nuevo usuario."""
    if request.user.is_authenticated:
        return redirect("accounts_web:perfil")

    errores = {}
    datos = {}

    if request.method == "POST":
        datos = request.POST.dict()
        datos.pop("csrfmiddlewaretoken", None)

        serializer = RegistroSerializer(data=datos)
        if serializer.is_valid():
            user = serializer.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(
                request,
                "¡Cuenta creada exitosamente! Tu perfil está pendiente de verificación KYC."
            )
            return redirect("accounts_web:perfil")
        else:
            for campo, errores_campo in serializer.errors.items():
                errores[campo] = "; ".join(
                    str(e) for e in errores_campo
                )

    return render(request, "accounts/registro.html", {
        "errores": errores,
        "datos": datos,
    })


def login_view(request):
    """Página de login."""
    if request.user.is_authenticated:
        return redirect("accounts_web:perfil")

    error = None

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        if user and user.is_active:
            login(request, user)
            next_url = request.GET.get("next", "accounts_web:perfil")
            return redirect(next_url)
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
