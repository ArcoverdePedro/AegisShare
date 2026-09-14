import re
import uuid
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from auditlog.models import LogEntry
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.clinical.pep.models import Encounter, Patient, PatientAccessGrant

from ..events import PRESCRIPTION_EVENT_GROUP, PRESCRIPTION_EVENT_TYPES, emit_prescription_event
from ..models import Drug, MedicationRequest, StockMovement
from ..services import (
    add_medication_request_item,
    create_medication_request,
    submit_medication_request,
)
from ..stock_services import adjust_stock, create_lot, create_stock_item

User = get_user_model()

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


class _RecordingChannelLayer:
    def __init__(self):
        self.calls = []

    async def group_send(self, group, payload):
        self.calls.append((group, payload))


class PrescriptionEventTests(TestCase):
    def test_prescription_event_contains_only_operational_identifiers(self):
        layer = _RecordingChannelLayer()
        prescription_id = uuid.uuid4()
        encounter_id = uuid.uuid4()

        with (
            patch("apps.clinical.prescription.events.get_channel_layer", return_value=layer),
            patch(
                "apps.clinical.prescription.events.transaction.on_commit",
                side_effect=lambda callback: callback(),
            ),
        ):
            emit_prescription_event(
                event_type="prescription.created",
                prescription_id=prescription_id,
                encounter_id=encounter_id,
                status=MedicationRequest.Status.SUBMITTED,
            )

        self.assertEqual(len(layer.calls), 1)
        group, payload = layer.calls[0]
        self.assertEqual(group, PRESCRIPTION_EVENT_GROUP)
        self.assertEqual(payload["event_type"], "prescription.created")
        self.assertEqual(payload["prescription_id"], str(prescription_id))
        self.assertEqual(payload["encounter_id"], str(encounter_id))
        self.assertEqual(payload["status"], MedicationRequest.Status.SUBMITTED)
        self.assertIsNone(payload["safety_review_id"])
        forbidden = {
            "patient_id",
            "patient_name",
            "cpf",
            "instructions",
            "allergy",
            "reason",
        }
        self.assertFalse(forbidden.intersection(payload))

    def test_unknown_prescription_event_is_rejected(self):
        with self.assertRaises(ValueError):
            emit_prescription_event(
                event_type="prescription.unknown",
                prescription_id=uuid.uuid4(),
                encounter_id=uuid.uuid4(),
                status=MedicationRequest.Status.SUBMITTED,
            )

    def test_asyncapi_event_names_match_runtime_allowlist(self):
        contract_path = (
            Path(settings.BASE_DIR)
            / "specs"
            / "003-prescricao-farmacia"
            / "contracts"
            / "events.asyncapi.yaml"
        )
        body = contract_path.read_text(encoding="utf-8")
        documented_names = set(
            re.findall(r"^\s+name:\s+([a-z.]+)\s*$", body, flags=re.MULTILINE)
        )

        self.assertEqual(documented_names, PRESCRIPTION_EVENT_TYPES)


class PrescriptionSubmissionEventTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="rx-event-admin",
            password="test-password",
            nivel_permissao="ADM",
        )
        self.prescriber = User.objects.create_user(
            username="rx-event-prescriber",
            password="test-password",
            nivel_permissao="FUNC",
        )
        permission = Permission.objects.get(
            codename="prescribe_medication",
            content_type__app_label="prescription",
        )
        self.prescriber.user_permissions.add(permission)
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="RX-EVENT-PATIENT",
            full_name="Paciente Sintético Evento",
            birth_date=timezone.localdate() - timedelta(days=365 * 30),
            created_by=self.admin,
        )
        PatientAccessGrant.objects.create(
            patient=self.patient,
            user=self.prescriber,
            reason="Teste de evento",
            granted_by=self.admin,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            responsible_professional=self.prescriber,
            created_by=self.admin,
        )
        self.drug = Drug.objects.create(
            code="RX-EVENT-DRUG",
            name="Medicamento Sintético Evento",
            presentation="Apresentação sintética",
            dispense_unit="unidade",
        )

    def test_submission_schedules_created_event_without_phi(self):
        request = create_medication_request(
            encounter_id=self.encounter.pk,
            actor=self.prescriber,
        )
        add_medication_request_item(
            request_id=request.pk,
            actor=self.prescriber,
            drug_id=self.drug.pk,
            dose=Decimal("1"),
            dose_unit="unidade",
            route="via sintética",
            frequency="frequência sintética",
            sequence=1,
            instructions="texto clínico sintético que não deve ir ao evento",
        )

        with patch("apps.clinical.prescription.services.emit_prescription_event") as emit:
            submitted = submit_medication_request(
                request_id=request.pk,
                actor=self.prescriber,
            )

        emit.assert_called_once_with(
            event_type="prescription.created",
            prescription_id=submitted.pk,
            encounter_id=submitted.encounter_id,
            status=MedicationRequest.Status.SUBMITTED,
        )


@override_settings(STORAGES=TEST_STORAGES)
class PharmacyStockAuditTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="rx-stock-audit-admin",
            password="test-password",
            nivel_permissao="ADM",
        )
        self.viewer = User.objects.create_user(
            username="rx-stock-audit-viewer",
            password="test-password",
            nivel_permissao="FUNC",
        )
        view_permission = Permission.objects.get(
            codename="view_pharmacy_stock",
            content_type__app_label="prescription",
        )
        self.viewer.user_permissions.add(view_permission)
        self.drug = Drug.objects.create(
            code="RX-AUDIT-STOCK",
            name="Medicamento Sintético Auditoria",
            presentation="Apresentação sintética",
            dispense_unit="unidade",
        )
        self.stock = create_stock_item(
            actor=self.admin,
            drug_id=self.drug.pk,
            storage_location="Farmácia auditoria",
            minimum_level=Decimal("2"),
        )
        self.lot = create_lot(
            actor=self.admin,
            stock_item_id=self.stock.pk,
            lot_number="AUDIT-LOT-1",
            expires_on=timezone.localdate() + timedelta(days=60),
            initial_quantity=Decimal("5"),
        )

    def test_stock_page_audits_stock_and_lot_reads(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("prescription:pharmacy_stock"))

        self.assertEqual(response.status_code, 200)
        for instance in (self.stock, self.lot):
            content_type = ContentType.objects.get_for_model(instance.__class__)
            self.assertTrue(
                LogEntry.objects.filter(
                    content_type=content_type,
                    object_pk=str(instance.pk),
                    action=LogEntry.Action.ACCESS,
                    actor=self.viewer,
                ).exists()
            )

    def test_stock_adjustment_audit_excludes_free_text_reason(self):
        movement = adjust_stock(
            lot_id=self.lot.pk,
            actor=self.admin,
            quantity_delta=Decimal("-1"),
            reason="Justificativa livre que não deve ser copiada para auditlog genérico",
        )
        content_type = ContentType.objects.get_for_model(StockMovement)
        entry = LogEntry.objects.filter(
            content_type=content_type,
            object_pk=str(movement.pk),
            action=LogEntry.Action.CREATE,
        ).latest("timestamp")

        self.assertNotIn("reason", entry.changes or {})
