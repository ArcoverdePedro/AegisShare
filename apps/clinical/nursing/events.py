import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

NURSING_EVENT_GROUP = "clinical_nursing_events"
NURSING_CHANNEL_EVENT_TYPE = "nursing_event_handler"
NURSING_EVENT_TYPES = {
    "nursing.vitals.recorded",
    "nursing.medication.administered",
}


def _schedule_event(event):
    def _send():
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(NURSING_EVENT_GROUP, event)

    transaction.on_commit(_send)


def emit_vitals_recorded_event(*, record_id, encounter_id, origin, replaces_id=None):
    """Agenda evento técnico pós-commit sem copiar medidas ou PHI textual."""
    _schedule_event(
        {
            "type": NURSING_CHANNEL_EVENT_TYPE,
            "event_id": str(uuid.uuid4()),
            "event_type": "nursing.vitals.recorded",
            "occurred_at": timezone.now().isoformat(),
            "vital_signs_record_id": str(record_id),
            "encounter_id": str(encounter_id),
            "origin": str(origin),
            "replaces_id": str(replaces_id) if replaces_id else None,
        }
    )


def emit_medication_administered_event(*, administration_id, dispense_item_id, encounter_id):
    """Agenda evento técnico pós-commit sem dose, unidade ou medicamento textual."""
    _schedule_event(
        {
            "type": NURSING_CHANNEL_EVENT_TYPE,
            "event_id": str(uuid.uuid4()),
            "event_type": "nursing.medication.administered",
            "occurred_at": timezone.now().isoformat(),
            "administration_id": str(administration_id),
            "dispense_item_id": str(dispense_item_id),
            "encounter_id": str(encounter_id),
        }
    )
