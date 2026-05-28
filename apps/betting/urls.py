from django.urls import path
from . import views_web

app_name = "betting"

urlpatterns = [
    path("mis-apuestas/", views_web.mis_apuestas, name="mis_apuestas"),
    path("apostar/", views_web.colocar_apuesta, name="colocar_apuesta"),
    path("cashout/<uuid:bet_id>/", views_web.ejecutar_cashout, name="ejecutar_cashout"),
]