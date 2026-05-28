import json
from channels.generic.websocket import AsyncWebsocketConsumer

class KYCConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if self.scope["user"].is_anonymous:
            await self.close()
            return

        self.group_name = f"kyc_{self.scope['user'].id}"
        
        # Join room group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        if not self.scope["user"].is_anonymous:
            # Leave room group
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    # Receive message from room group
    async def kyc_status_update(self, event):
        status = event["status"]
        message = event.get("message", "")

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            "status": status,
            "message": message
        }))
