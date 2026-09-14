import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

ADT_EVENT_TYPES = {
    "encounter.admitted",
    "encounter.transferred",
    "encounter.discharged",
    "bed.occupied",
    "bed.released",
    "bed.status_changed",
}
BED_EVENT_TYPES = {"bed.occupied", "bed.released", "bed.status_changed"}
BED_STATES = {"AVAILABLE", "OCCUPIED", "BLOCKED", "OUT_OF_SERVICE"}
ADT_BED_MAP_GROUP = "clinical_adt_bed_map"


def emit_adt_event(
    *,
    event_type,
    encounter_id=None,
    admission_id=None,
    occupancy_id=None,
    bed_id=None,
    location_id=None,
    state=None,
):
    """Agenda evento ADT pós-commit com payload técnico e sem PHI textual."""

    if event_type not in ADT_EVENT_TYPES:
        raise ValueError("Tipo de evento ADT não permitido.")

    event = {
        "type": "adt_event_handler",
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "occurred_at": timezone.now().isoformat(),
    }

    if event_type in BED_EVENT_TYPES:
        if not bed_id or not location_id or state not in BED_STATES:
            raise ValueError("Evento de leito exige leito, localização e estado válidos.")
        event.update(
            {
                "bed_id": str(bed_id),
                "location_id": str(location_id),
                "state": state,
            }
        )
    else:
        if not encounter_id or not admission_id:
            raise ValueError("Evento de encontro exige encontro e admissão.")
        event.update(
            {
                "encounter_id": str(encounter_id),
                "admission_id": str(admission_id),
                "occupancy_id": str(occupancy_id) if occupancy_id else None,
                "bed_id": str(bed_id) if bed_id else None,
                "location_id": str(location_id) if location_id else None,
            }
        )

    def _send():
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(ADT_BED_MAP_GROUP, event)

    transaction.on_commit(_send)
