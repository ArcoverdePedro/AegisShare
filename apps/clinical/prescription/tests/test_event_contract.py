import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase

from ..events import (
    PRESCRIPTION_CHANNEL_EVENT_TYPE,
    PRESCRIPTION_EVENT_GROUP,
    emit_prescription_event,
    emit_stock_low_event,
)


class _RecordingChannelLayer:
    def __init__(self):
        self.calls = []

    async def group_send(self, group, payload):
        self.calls.append((group, payload))


def _contract_body():
    path = (
        Path(settings.BASE_DIR)
        / "specs"
        / "003-prescricao-farmacia"
        / "contracts"
        / "events.asyncapi.yaml"
    )
    return path.read_text(encoding="utf-8")


def _schema_property_names(body, schema_name):
    lines = body.splitlines()
    header = f"    {schema_name}:"
    try:
        start = lines.index(header)
    except ValueError as exc:
        raise AssertionError(f"Schema AsyncAPI ausente: {schema_name}") from exc

    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.startswith("    ") and not line.startswith("      ") and line.strip().endswith(":"):
            end = index
            break

    properties = set()
    properties_indent = None
    for line in lines[start + 1 : end]:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if stripped == "properties:":
            properties_indent = indent
            continue
        if properties_indent is None or not stripped:
            continue
        if indent <= properties_indent:
            properties_indent = None
            continue
        if indent == properties_indent + 2 and stripped.endswith(":"):
            properties.add(stripped[:-1])

    return properties


def _contract_payload_fields(schema_name):
    body = _contract_body()
    return _schema_property_names(body, "BaseEvent") | _schema_property_names(body, schema_name)


def _emit_and_capture(callback):
    layer = _RecordingChannelLayer()
    with (
        patch("apps.clinical.prescription.events.get_channel_layer", return_value=layer),
        patch(
            "apps.clinical.prescription.events.transaction.on_commit",
            side_effect=lambda commit_callback: commit_callback(),
        ),
    ):
        callback()

    if len(layer.calls) != 1:
        raise AssertionError(f"Esperado exatamente um evento, recebido: {len(layer.calls)}")
    return layer.calls[0]


class EventPayloadContractTests(SimpleTestCase):
    def assert_payload_matches_contract(self, payload, schema_name):
        self.assertEqual(payload["type"], PRESCRIPTION_CHANNEL_EVENT_TYPE)
        self.assertEqual(
            set(payload) - {"type"},
            _contract_payload_fields(schema_name),
        )

    def test_prescription_created_payload_matches_asyncapi_schema(self):
        prescription_id = uuid.uuid4()
        encounter_id = uuid.uuid4()

        group, payload = _emit_and_capture(
            lambda: emit_prescription_event(
                event_type="prescription.created",
                prescription_id=prescription_id,
                encounter_id=encounter_id,
                status="SUBMITTED",
            )
        )

        self.assertEqual(group, PRESCRIPTION_EVENT_GROUP)
        self.assert_payload_matches_contract(payload, "PrescriptionEventPayload")

    def test_stock_low_payload_matches_asyncapi_schema(self):
        stock_item_id = uuid.uuid4()
        drug_id = uuid.uuid4()

        group, payload = _emit_and_capture(
            lambda: emit_stock_low_event(
                stock_item_id=stock_item_id,
                drug_id=drug_id,
                storage_location="Farmácia sintética",
                quantity_available=Decimal("2.5"),
                minimum_level=Decimal("5"),
            )
        )

        self.assertEqual(group, PRESCRIPTION_EVENT_GROUP)
        self.assert_payload_matches_contract(payload, "StockLowEventPayload")
