import json

from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone


# Campos que NUNCA queremos exponer al cliente (control interno de Channels).
_INTERNAL_FIELDS = {"type"}


def _build_payload(event):
    """
    Toma todos los campos del mensaje de Channels excepto los internos y los
    reempaqueta con el contrato RB-RT-03: `type`, `timestamp`, recurso.
    Forwardea cualquier campo adicional (home_score, minute, scorer, etc.)
    sin que el consumer tenga que conocerlos por nombre.
    """
    payload = {k: v for k, v in event.items() if k not in _INTERNAL_FIELDS}
    payload["type"] = event.get("action")
    payload.setdefault("timestamp", timezone.now().isoformat())
    payload.pop("action", None)
    return payload


class BettingConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer unidireccional (server → client) por evento.
    RB-RT-01: no implementa `receive`; las mutaciones van por HTTP REST.
    RB-RT-02: suscripción al grupo `event_<uuid>`.
    """

    async def connect(self):
        self.event_id = self.scope["url_route"]["kwargs"]["event_id"]
        self.group_name = f"event_{self.event_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def market_message(self, event):
        await self.send(text_data=json.dumps(_build_payload(event)))

    async def event_message(self, event):
        await self.send(text_data=json.dumps(_build_payload(event)))


class LobbyConsumer(AsyncWebsocketConsumer):
    """
    Canal "lobby" para la página de lista de eventos.
    Recibe los mismos mensajes que cada canal `event_<uuid>` pero a nivel global,
    así la lista refleja en vivo cambios de estado, marcador y odds sin recargar.
    """

    GROUP = "events_lobby"

    async def connect(self):
        await self.channel_layer.group_add(self.GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP, self.channel_name)

    async def market_message(self, event):
        await self.send(text_data=json.dumps(_build_payload(event)))

    async def event_message(self, event):
        await self.send(text_data=json.dumps(_build_payload(event)))
