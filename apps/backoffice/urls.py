from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = "backoffice"

urlpatterns = [
    path("", RedirectView.as_view(url="dashboard/", permanent=True)),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("alerta/resolver/<int:alerta_id>/", views.resolver_alerta_view, name="resolver_alerta"),
    path("reporte-mincetur/", views.reporte_mincetur_view, name="reporte_mincetur"),
]

