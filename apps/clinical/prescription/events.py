import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

PRESCRIPTION_EVENT_GROUP = "clinical_prescription_events"
PRESCRIPTION_EVENT_TYPES = {
    "stock.low",
}


def emit_stock_low_event(
    *,
    stock_item_id,
    drug_id,
    storage_location,
    quantity_available,
    minimum_level,
):
    """Agenda alerta técnico pós-commit sem dados de paciente ou conteúdo clínico."""
    event = {
        "type": "prescription_event_handler",
        "event_id": str(uuid.uuid4()),
        "event_type": "stock.low",
        "occurred_at": timezone.now().isoformat(),
        "stock_item_id": str(stock_item_id),
        "drug_id": str(drug_id),
        "storage_location": storage_location,
        "quantity_available": str(quantity_available),
        "minimum_level": str(minimum_level),
    }

    def _send():
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(PRESCRIPTION_EVENT_GROUP, event)

    transaction.on_commit(_send)
