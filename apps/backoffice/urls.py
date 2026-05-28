from django.urls import path
from apps.backoffice import views

app_name = "backoffice"

urlpatterns = [
    path(
        "evento/<uuid:event_id>/control/",
        views.event_control_view,
        name="event_control",
    ),
]
