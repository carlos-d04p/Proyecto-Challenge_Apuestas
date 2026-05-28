from django.urls import path
from apps.realtime import consumers

websocket_urlpatterns = [
    # Ruta: ws/realtime/match/<id_del_evento>/
    path('ws/realtime/match/<int:event_id>/', consumers.BettingConsumer.as_asgi()),
]