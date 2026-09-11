from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone


CLINICAL_EVENT_TYPES = {
    "encounter.created",
    "evolution.created",
    "evolution.amended",
}


def patient_group_name(patient_id) -> str:
    return f"clinical_patient_{patient_id}"


def emit_clinical_event(
    *,
    event: str,
    patient_id,
    encounter_id=None,
    object_id=None,
):
    if event not in CLINICAL_EVENT_TYPES:
        raise ValueError("Tipo de evento clínico não permitido.")

    payload = {
        "type": "clinical_event_handler",
        "event": event,
        "patient_id": str(patient_id),
        "encounter_id": str(encounter_id) if encounter_id else None,
        "object_id": str(object_id) if object_id else None,
        "occurred_at": timezone.now().isoformat(),
    }

    def _send():
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(patient_group_name(patient_id), payload)

    transaction.on_commit(_send)
