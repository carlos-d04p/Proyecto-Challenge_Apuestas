from django.urls import path
from apps.realtime import consumers

websocket_urlpatterns = [
    # Ruta por evento individual: ws/realtime/match/<uuid>/
    path('ws/realtime/match/<uuid:event_id>/', consumers.BettingConsumer.as_asgi()),
    # Canal global (lista de eventos): ws/realtime/lobby/
    path('ws/realtime/lobby/', consumers.LobbyConsumer.as_asgi()),
]