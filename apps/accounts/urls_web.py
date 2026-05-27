"""URLs web (HTML) para la app accounts."""
from django.urls import path
from . import views_web

app_name = "accounts_web"

urlpatterns = [
    path("registro/",  views_web.registro_view, name="registro"),
    path("login/",     views_web.login_view,    name="login"),
    path("logout/",    views_web.logout_view,   name="logout"),
    path("perfil/",    views_web.perfil_view,   name="perfil"),
    path('verify-email/<str:token>/', views_web.VerificarEmailView.as_view(), name='verify_email'),
]
