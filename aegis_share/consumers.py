import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model

from .models import Conversation, Message

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = f"chat_{self.conversation_id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get("type")

        # 🔥 MENSAGEM DE TEXTO
        if message_type == "chat_message":
            content = data.get("message")
            sender = self.scope["user"]

            message = await self.save_message(sender.id, content)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message_event",
                    "message": content,
                    "sender_id": sender.id,
                    "sender_name": sender.username,
                    "created_at": message.created_at.isoformat(),
                },
            )

        # 🔥 INDICADOR DE DIGITAÇÃO
        if message_type == "typing":
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "typing_event",
                    "username": self.scope["user"].username,
                    "is_typing": data.get("is_typing"),
                },
            )

    async def chat_message_event(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "chat_message",
                    "message": event["message"],
                    "sender_id": event["sender_id"],
                    "sender_name": event["sender_name"],
                    "created_at": event["created_at"],
                }
            )
        )

    async def typing_event(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "typing",
                    "username": event["username"],
                    "is_typing": event["is_typing"],
                }
            )
        )

    @database_sync_to_async
    def save_message(self, sender_id, content):
        sender = User.objects.get(id=sender_id)
        conversation = Conversation.objects.get(id=self.conversation_id)
        return Message.objects.create(
            sender=sender, content=content, conversation=conversation
        )
