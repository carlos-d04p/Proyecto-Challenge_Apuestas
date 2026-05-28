import json
from channels.generic.websocket import AsyncWebsocketConsumer

class BettingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # 1. Obtener el ID del evento desde la URL (ej. ws/realtime/match/5/)
        self.event_id = self.scope['url_route']['kwargs']['event_id']
        
        # 2. Crear un nombre de grupo único para este evento
        self.group_name = f"event_{self.event_id}"

        # 3. Unir este WebSocket al grupo
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        # 4. Aceptar la conexión
        await self.accept()

    async def disconnect(self, close_code):
        # Salir del grupo cuando el usuario cierre la pestaña
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # --- MÉTODO PARA RECIBIR EVENTOS DEL BACKEND ---
    # Este método será llamado por Django mediante Signals
    async def market_message(self, event):
        # Extraer datos del evento enviado por el backend
        action = event.get('action')
        market_id = event.get('market_id')
        message = event.get('message', '')
        odds = event.get('odds', '')

        # Enviar esos datos al frontend (Javascript) vía WebSocket
        payload = {
            'action': action,
            'market_id': market_id,
        }
        
        if message:
            payload['message'] = message
        if odds:
            payload['odds'] = odds

        await self.send(text_data=json.dumps(payload))