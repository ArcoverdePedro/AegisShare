import uuid

from django.utils import timezone

from apps.clinical.events import send_after_commit

NURSING_EVENT_GROUP = "clinical_nursing_events"
NURSING_CHANNEL_EVENT_TYPE = "nursing_event_handler"
NURSING_EVENT_TYPES = {
    "nursing.vitals.recorded",
    "nursing.medication.administered",
}


def emit_vitals_recorded_event(*, record_id, encounter_id, origin, replaces_id=None):
    """Agenda evento técnico pós-commit sem copiar medidas ou PHI textual."""
    send_after_commit(
        NURSING_EVENT_GROUP,
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
    send_after_commit(
        NURSING_EVENT_GROUP,
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
