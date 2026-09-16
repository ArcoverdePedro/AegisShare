import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.db import transaction
from django.test import SimpleTestCase, TransactionTestCase

from ..events import (
    PRESCRIPTION_CHANNEL_EVENT_TYPE,
    PRESCRIPTION_EVENT_GROUP,
    emit_medication_dispensed_event,
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
        patch("apps.clinical.events.get_channel_layer", return_value=layer),
        patch(
            "apps.clinical.events.transaction.on_commit",
            side_effect=lambda commit_callback: commit_callback(),
        ),
    ):
        callback()

    if len(layer.calls) != 1:
        raise AssertionError(f"Esperado exatamente um evento, recebido: {len(layer.calls)}")
    return layer.calls[0]


def _event_emitters():
    return {
        "prescription.created": lambda: emit_prescription_event(
            event_type="prescription.created",
            prescription_id=uuid.uuid4(),
            encounter_id=uuid.uuid4(),
            status="SUBMITTED",
        ),
        "prescription.validated": lambda: emit_prescription_event(
            event_type="prescription.validated",
            prescription_id=uuid.uuid4(),
            encounter_id=uuid.uuid4(),
            status="VALIDATED",
            safety_review_id=uuid.uuid4(),
        ),
        "medication.dispensed": lambda: emit_medication_dispensed_event(
            dispense_id=uuid.uuid4(),
            prescription_id=uuid.uuid4(),
            encounter_id=uuid.uuid4(),
            item_count=2,
        ),
        "stock.low": lambda: emit_stock_low_event(
            stock_item_id=uuid.uuid4(),
            drug_id=uuid.uuid4(),
            storage_location="Farmácia sintética",
            quantity_available=Decimal("2.5"),
            minimum_level=Decimal("5"),
        ),
    }


class EventPayloadContractTests(SimpleTestCase):
    def assert_payload_matches_contract(self, payload, schema_name):
        self.assertEqual(payload["type"], PRESCRIPTION_CHANNEL_EVENT_TYPE)
        self.assertEqual(
            set(payload) - {"type"},
            _contract_payload_fields(schema_name),
        )

    def test_prescription_created_payload_matches_asyncapi_schema(self):
        group, payload = _emit_and_capture(
            lambda: emit_prescription_event(
                event_type="prescription.created",
                prescription_id=uuid.uuid4(),
                encounter_id=uuid.uuid4(),
                status="SUBMITTED",
            )
        )

        self.assertEqual(group, PRESCRIPTION_EVENT_GROUP)
        self.assert_payload_matches_contract(payload, "PrescriptionEventPayload")

    def test_prescription_validated_payload_matches_asyncapi_schema(self):
        group, payload = _emit_and_capture(
            lambda: emit_prescription_event(
                event_type="prescription.validated",
                prescription_id=uuid.uuid4(),
                encounter_id=uuid.uuid4(),
                status="VALIDATED",
                safety_review_id=uuid.uuid4(),
            )
        )

        self.assertEqual(group, PRESCRIPTION_EVENT_GROUP)
        self.assert_payload_matches_contract(payload, "PrescriptionEventPayload")
        self.assertIsNotNone(payload["safety_review_id"])

    def test_medication_dispensed_payload_matches_asyncapi_schema(self):
        group, payload = _emit_and_capture(
            lambda: emit_medication_dispensed_event(
                dispense_id=uuid.uuid4(),
                prescription_id=uuid.uuid4(),
                encounter_id=uuid.uuid4(),
                item_count=2,
            )
        )

        self.assertEqual(group, PRESCRIPTION_EVENT_GROUP)
        self.assert_payload_matches_contract(payload, "DispenseEventPayload")
        self.assertEqual(payload["item_count"], 2)

    def test_stock_low_payload_matches_asyncapi_schema(self):
        group, payload = _emit_and_capture(
            lambda: emit_stock_low_event(
                stock_item_id=uuid.uuid4(),
                drug_id=uuid.uuid4(),
                storage_location="Farmácia sintética",
                quantity_available=Decimal("2.5"),
                minimum_level=Decimal("5"),
            )
        )

        self.assertEqual(group, PRESCRIPTION_EVENT_GROUP)
        self.assert_payload_matches_contract(payload, "StockLowEventPayload")


class EventCommitSemanticsTests(TransactionTestCase):
    def test_events_are_sent_only_after_successful_commit(self):
        for event_name, emit in _event_emitters().items():
            with self.subTest(event=event_name):
                layer = _RecordingChannelLayer()
                with patch(
                    "apps.clinical.events.get_channel_layer",
                    return_value=layer,
                ):
                    with transaction.atomic():
                        emit()
                        self.assertEqual(layer.calls, [])

                    self.assertEqual(len(layer.calls), 1)
                    self.assertEqual(layer.calls[0][0], PRESCRIPTION_EVENT_GROUP)
                    self.assertEqual(layer.calls[0][1]["event_type"], event_name)

    def test_events_are_discarded_when_transaction_rolls_back(self):
        for event_name, emit in _event_emitters().items():
            with self.subTest(event=event_name):
                layer = _RecordingChannelLayer()
                with (
                    patch(
                        "apps.clinical.events.get_channel_layer",
                        return_value=layer,
                    ),
                    self.assertRaises(RuntimeError),
                    transaction.atomic(),
                ):
                    emit()
                    raise RuntimeError("rollback sintético")

                self.assertEqual(layer.calls, [])
