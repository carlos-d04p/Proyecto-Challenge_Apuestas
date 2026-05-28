from django.urls import path
from django.views.generic import RedirectView
from apps.backoffice import views

app_name = "backoffice"

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("api/feed/", views.dashboard_feed, name="dashboard_feed"),
    path("usuario/<uuid:user_id>/", views.user_detail_view, name="user_detail"),
    path("eventos/", views.event_list_view, name="event_list"),
    path("evento/nuevo/", views.event_create_view, name="event_create"),
    path("evento/<uuid:event_id>/control/", views.event_control_view, name="event_control"),
    path("evento/<uuid:event_id>/settle/", views.event_settle_view, name="event_settle"),
    path("alerta/resolver/<int:alerta_id>/", views.resolver_alerta_view, name="resolver_alerta"),
    path("reporte-mincetur/", views.reporte_mincetur_view, name="reporte_mincetur"),
]
