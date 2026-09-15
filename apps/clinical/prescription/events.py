import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

PRESCRIPTION_EVENT_GROUP = "clinical_prescription_events"
PRESCRIPTION_CHANNEL_EVENT_TYPE = "prescription_event_handler"
PRESCRIPTION_EVENT_TYPES = {
    "prescription.created",
    "prescription.validated",
    "medication.dispensed",
    "stock.low",
}
PRESCRIPTION_STATUSES = {"DRAFT", "SUBMITTED", "VALIDATED", "CANCELLED"}


def _schedule_event(event):
    def _send():
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(PRESCRIPTION_EVENT_GROUP, event)

    transaction.on_commit(_send)


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

    _schedule_event(
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


def emit_stock_low_event(
    *,
    stock_item_id,
    drug_id,
    storage_location,
    quantity_available,
    minimum_level,
):
    """Agenda alerta técnico pós-commit sem dados de paciente ou conteúdo clínico."""
    _schedule_event(
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
