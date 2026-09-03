import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from .models import Conversation, Message, Notification


class ChatConsumer(AsyncWebsocketConsumer):
    MAX_MESSAGE_LENGTH = 4000

    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = f"chat_{self.conversation_id}"
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close(code=4401)
            return
        if not await self.user_belongs_to_conversation():
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        await self.mark_messages_as_read()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (TypeError, json.JSONDecodeError):
            return

        if data.get("type") != "chat_message":
            return
        content = str(data.get("content", "")).strip()
        if not content or len(content) > self.MAX_MESSAGE_LENGTH:
            return

        message = await self.save_message(content)
        if not message:
            await self.close(code=4403)
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message_handler",
                "message_id": str(message["id"]),
                "sender_id": str(self.user.id),
                "sender_username": self.user.username,
                "content": content,
                "created_at": message["created_at"],
            },
        )

    async def chat_message_handler(self, event):
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
    def user_belongs_to_conversation(self):
        return Conversation.objects.filter(
            id=self.conversation_id,
            participants=self.user,
        ).exists()

    @database_sync_to_async
    def save_message(self, content):
        conversation = (
            Conversation.objects.filter(id=self.conversation_id, participants=self.user)
            .prefetch_related("participants")
            .first()
        )
        if not conversation:
            return None

        message = Message.objects.create(
            conversation=conversation,
            sender=self.user,
            content=content,
        )
        Conversation.objects.filter(id=conversation.id).update(updated_at=timezone.now())

        recipients = conversation.participants.exclude(id=self.user.id)
        Notification.objects.bulk_create(
            [
                Notification(
                    user=recipient,
                    kind="CHAT",
                    title=f"Nova mensagem de {self.user.username}",
                    body=content[:180],
                    link=f"/chat/{conversation.id}/",
                )
                for recipient in recipients
            ]
        )
        return {
            "id": message.id,
            "created_at": message.created_at.strftime("%d/%m/%Y %H:%M"),
        }

    @database_sync_to_async
    def mark_messages_as_read(self):
        Conversation.objects.filter(
            id=self.conversation_id,
            participants=self.user,
        ).first().messages.filter(is_read=False).exclude(sender=self.user).update(is_read=True)
