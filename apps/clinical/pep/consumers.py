import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .events import patient_group_name
from .permissions import accessible_patients


class PatientClinicalConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.patient_id = self.scope["url_route"]["kwargs"]["patient_id"]
        self.user = self.scope["user"]
        self.room_group_name = patient_group_name(self.patient_id)

        if not self.user.is_authenticated:
            await self.close(code=4401)
            return
        if not await self.user_can_access_patient():
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def clinical_event_handler(self, event):
        # O vínculo pode expirar ou ser revogado depois que o socket foi aberto.
        if not await self.user_can_access_patient():
            await self.close(code=4403)
            return

        await self.send(
            text_data=json.dumps(
                {
                    "type": "clinical_event",
                    "event": event["event"],
                    "patient_id": event["patient_id"],
                    "encounter_id": event.get("encounter_id"),
                    "object_id": event.get("object_id"),
                    "occurred_at": event["occurred_at"],
                }
            )
        )

    @database_sync_to_async
    def user_can_access_patient(self):
        return accessible_patients(self.user).filter(pk=self.patient_id).exists()
