import uuid

from django.utils import timezone

from apps.clinical.events import send_after_commit

PRESCRIPTION_EVENT_GROUP = "clinical_prescription_events"
PRESCRIPTION_CHANNEL_EVENT_TYPE = "prescription_event_handler"
PRESCRIPTION_EVENT_TYPES = {
    "prescription.created",
    "prescription.validated",
    "medication.dispensed",
    "stock.low",
}
PRESCRIPTION_STATUSES = {"DRAFT", "SUBMITTED", "VALIDATED", "CANCELLED"}


def emit_prescription_event(
    *,
    event_type,
    prescription_id,
    encounter_id,
    status,
    safety_review_id=None,
):
    """Agenda evento técnico de prescrição pós-commit usando apenas identificadores."""
    if event_type not in {"prescription.created", "prescription.validated"}:
        raise ValueError("Tipo de evento de prescrição não permitido.")
    if status not in PRESCRIPTION_STATUSES:
        raise ValueError("Estado de prescrição inválido para evento interno.")

    send_after_commit(
        PRESCRIPTION_EVENT_GROUP,
        {
            "type": PRESCRIPTION_CHANNEL_EVENT_TYPE,
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "occurred_at": timezone.now().isoformat(),
            "prescription_id": str(prescription_id),
            "encounter_id": str(encounter_id),
            "status": status,
            "safety_review_id": str(safety_review_id) if safety_review_id else None,
        }
    )


def emit_medication_dispensed_event(
    *,
    dispense_id,
    prescription_id,
    encounter_id,
    item_count,
):
    """Agenda evento técnico de dispensação pós-commit sem conteúdo clínico textual."""
    if item_count < 1:
        raise ValueError("Evento de dispensação exige ao menos um item.")
    send_after_commit(
        PRESCRIPTION_EVENT_GROUP,
        {
            "type": PRESCRIPTION_CHANNEL_EVENT_TYPE,
            "event_id": str(uuid.uuid4()),
            "event_type": "medication.dispensed",
            "occurred_at": timezone.now().isoformat(),
            "dispense_id": str(dispense_id),
            "prescription_id": str(prescription_id),
            "encounter_id": str(encounter_id),
            "item_count": int(item_count),
        }
    )


def emit_stock_low_event(
    *,
    stock_item_id,
    drug_id,
    storage_location,
    quantity_available,
    minimum_level,
):
    """Agenda alerta técnico pós-commit sem dados de paciente ou conteúdo clínico."""
    send_after_commit(
        PRESCRIPTION_EVENT_GROUP,
        {
            "type": PRESCRIPTION_CHANNEL_EVENT_TYPE,
            "event_id": str(uuid.uuid4()),
            "event_type": "stock.low",
            "occurred_at": timezone.now().isoformat(),
            "stock_item_id": str(stock_item_id),
            "drug_id": str(drug_id),
            "storage_location": storage_location,
            "quantity_available": float(quantity_available),
            "minimum_level": float(minimum_level),
        }
    )
