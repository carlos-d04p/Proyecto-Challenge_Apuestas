"""
URLs de la API REST para la app accounts.
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AutoexclusionView,
    LimitesView,
    LoginView,
    PerfilView,
    RegistroView,
    VerificarKYCView,
)

app_name = "accounts"

urlpatterns = [
    # Registro y autenticación
    path("registro/",        RegistroView.as_view(),    name="registro"),
    path("login/",           LoginView.as_view(),       name="login"),
    path("token/refresh/",   TokenRefreshView.as_view(), name="token_refresh"),

    # Perfil y KYC
    path("perfil/",          PerfilView.as_view(),      name="perfil"),
    path("kyc/verificar/",   VerificarKYCView.as_view(), name="kyc_verificar"),

    # Controles de juego responsable
    path("limites/",         LimitesView.as_view(),     name="limites"),
    path("autoexclusion/",   AutoexclusionView.as_view(), name="autoexclusion"),
]
