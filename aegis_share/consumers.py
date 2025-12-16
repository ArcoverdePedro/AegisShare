import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from .models import Conversation, Message


class ChatConsumer(AsyncWebsocketConsumer):
    """Consumer para mensagens de uma conversa específica"""

    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = f"chat_{self.conversation_id}"
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()
        await self.mark_messages_as_read()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        """Recebe mensagem do WebSocket"""
        data = json.loads(text_data)
        message_type = data.get("type")

        if message_type == "chat_message":
            content = data.get("content", "").strip()

            if not content:
                return

            message = await self.save_message(content)

            # Envia dados JSON em vez de HTML renderizado
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message_handler",
                    "message_id": str(message.id),
                    "sender_id": str(message.sender.id),
                    "sender_username": message.sender.username,
                    "content": message.content,
                    "created_at": message.created_at.strftime("%d/%m/%Y %H:%M"),
                },
            )

    async def chat_message_handler(self, event):
        """Handler para mensagens do grupo"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "new_message",
                    "message_id": event["message_id"],
                    "sender_id": event["sender_id"],
                    "sender_username": event["sender_username"],
                    "content": event["content"],
                    "created_at": event["created_at"],
                }
            )
        )

    @database_sync_to_async
    def save_message(self, content):
        """Salva a mensagem no banco de dados"""
        conversation = Conversation.objects.get(id=self.conversation_id)
        message = Message.objects.create(
            conversation=conversation, sender=self.user, content=content
        )
        conversation.updated_at = timezone.now()
        conversation.save(update_fields=["updated_at"])
        return message

    @database_sync_to_async
    def mark_messages_as_read(self):
        """Marca mensagens não lidas como lidas"""
        Conversation.objects.get(id=self.conversation_id).messages.filter(
            is_read=False
        ).exclude(sender=self.user).update(is_read=True)
