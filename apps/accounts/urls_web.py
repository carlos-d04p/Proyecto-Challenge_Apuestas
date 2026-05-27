"""URLs web (HTML) para la app accounts."""
from django.urls import path
from .views_web import registro_view, login_view, logout_view, perfil_view

app_name = "accounts_web"

urlpatterns = [
    path("registro/",  registro_view, name="registro"),
    path("login/",     login_view,    name="login"),
    path("logout/",    logout_view,   name="logout"),
    path("perfil/",    perfil_view,   name="perfil"),
]
