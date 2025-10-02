import json
from channels.generic.websocket import AsyncWebsocketConsumer


class Notificador(AsyncWebsocketConsumer):
    async def connect(self):
        # adiciona todos no mesmo grupo
        await self.channel_layer.group_add("notifications_staff", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("notifications_staff", self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # ecoa a mensagem recebida de volta ao grupo
        await self.channel_layer.group_send(
            "notifications_staff",
            {
                "type": "notify",
                "message": text_data,
            },
        )

    async def notify(self, event):
        await self.send(text_data=json.dumps({"message": event["message"]}))
