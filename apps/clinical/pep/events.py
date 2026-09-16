from django.utils import timezone

from apps.clinical.events import send_after_commit

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

    send_after_commit(patient_group_name(patient_id), payload)
