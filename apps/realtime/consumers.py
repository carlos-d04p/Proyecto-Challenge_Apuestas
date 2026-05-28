import json
from datetime import datetime, timezone

from channels.generic.websocket import AsyncWebsocketConsumer


class BettingConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer unidireccional (server → client).
    RB-RT-01: No implementa receive(); las mutaciones van por HTTP REST.
    RB-RT-02: Suscripción por grupo específico del evento.
    """

    async def connect(self):
        self.event_id = self.scope['url_route']['kwargs']['event_id']
        self.group_name = f"event_{self.event_id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # --- Mensajes a nivel de MERCADO (cuotas y suspensión de market) ---
    async def market_message(self, event):
        """
        RB-RT-03: Payload JSON con timestamp, type, y resource ID.
        Acciones: ODDS_UPDATE, MARKET_SUSPEND
        """
        payload = {
            'type': event.get('action'),
            'timestamp': event.get('timestamp', datetime.now(timezone.utc).isoformat()),
            'market_id': event.get('market_id'),
        }
        # Campos opcionales según la acción
        if 'message' in event:
            payload['message'] = event['message']
        if 'odds' in event:
            payload['odds'] = event['odds']
        if 'selection_id' in event:
            payload['selection_id'] = event['selection_id']

        await self.send(text_data=json.dumps(payload))

    # --- Mensajes a nivel de EVENTO (suspensión, finalización, cancelación) ---
    async def event_message(self, event):
        """
        RB-RT-04: Broadcast inmediato al cambiar estado del evento.
        Acciones: EVENT_SUSPENDED, EVENT_FINISHED, EVENT_CANCELLED, EVENT_LIVE
        """
        payload = {
            'type': event.get('action'),
            'timestamp': event.get('timestamp', datetime.now(timezone.utc).isoformat()),
            'event_id': event.get('event_id'),
            'message': event.get('message', ''),
        }
        await self.send(text_data=json.dumps(payload))