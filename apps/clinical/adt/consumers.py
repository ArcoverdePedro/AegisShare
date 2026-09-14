import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .events import ADT_BED_MAP_GROUP
from .permissions import can_access_location, can_view_bed_map


class AdtBedMapConsumer(AsyncWebsocketConsumer):
    """Sinaliza invalidação do mapa; o navegador refaz GET autorizado via HTMX."""

    async def connect(self):
        self.user = self.scope["user"]
        self.room_group_name = ADT_BED_MAP_GROUP

        if not self.user.is_authenticated:
            await self.close(code=4401)
            return
        if not await self.user_can_view_bed_map():
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def adt_event_handler(self, event):
        if not await self.user_can_view_bed_map():
            await self.close(code=4403)
            return

        location_id = event.get("location_id")
        if location_id and not await self.user_can_access_location(location_id):
            return

        payload = {
            key: value
            for key, value in event.items()
            if key
            in {
                "event_id",
                "event_type",
                "occurred_at",
                "encounter_id",
                "admission_id",
                "occupancy_id",
                "bed_id",
                "location_id",
                "state",
            }
        }
        payload["type"] = "adt_event"
        await self.send(text_data=json.dumps(payload))

    @database_sync_to_async
    def user_can_view_bed_map(self):
        return can_view_bed_map(self.user)

    @database_sync_to_async
    def user_can_access_location(self, location_id):
        from .models import Location

        location = Location.objects.filter(pk=location_id, active=True).first()
        return bool(location and can_access_location(self.user, location))
