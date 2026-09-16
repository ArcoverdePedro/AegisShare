import re
import uuid
from datetime import date, timedelta
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

from apps.clinical.pep.models import Encounter, Patient
from apps.clinical.prescription.models import (
    Drug,
    Lot,
    MedicationDispense,
    MedicationDispenseItem,
    MedicationRequest,
    MedicationRequestItem,
    StockItem,
)

from ..events import (
    NURSING_EVENT_GROUP,
    NURSING_EVENT_TYPES,
    emit_medication_administered_event,
    emit_vitals_recorded_event,
)
from ..models import MedicationAdministration, VitalSignsRecord
from ..services import administer_medication, record_vital_signs

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


class NursingEventContractTests(TestCase):
    def _capture(self, callback):
        layer = _RecordingChannelLayer()
        with (
            patch("apps.clinical.nursing.events.get_channel_layer", return_value=layer),
            patch(
                "apps.clinical.nursing.events.transaction.on_commit",
                side_effect=lambda fn: fn(),
            ),
        ):
            callback()
        self.assertEqual(len(layer.calls), 1)
        return layer.calls[0]

    def test_vitals_event_contains_only_contract_fields(self):
        record_id = uuid.uuid4()
        encounter_id = uuid.uuid4()
        replaces_id = uuid.uuid4()

        group, payload = self._capture(
            lambda: emit_vitals_recorded_event(
                record_id=record_id,
                encounter_id=encounter_id,
                origin=VitalSignsRecord.Origin.OFFLINE_SYNC,
                replaces_id=replaces_id,
            )
        )

        self.assertEqual(group, NURSING_EVENT_GROUP)
        self.assertEqual(
            set(payload),
            {
                "type",
                "event_id",
                "event_type",
                "occurred_at",
                "vital_signs_record_id",
                "encounter_id",
                "origin",
                "replaces_id",
            },
        )
        self.assertEqual(payload["event_type"], "nursing.vitals.recorded")
        self.assertEqual(payload["vital_signs_record_id"], str(record_id))
        self.assertEqual(payload["encounter_id"], str(encounter_id))
        self.assertEqual(payload["origin"], VitalSignsRecord.Origin.OFFLINE_SYNC)
        self.assertEqual(payload["replaces_id"], str(replaces_id))

    def test_medication_event_contains_only_contract_fields(self):
        administration_id = uuid.uuid4()
        dispense_item_id = uuid.uuid4()
        encounter_id = uuid.uuid4()

        group, payload = self._capture(
            lambda: emit_medication_administered_event(
                administration_id=administration_id,
                dispense_item_id=dispense_item_id,
                encounter_id=encounter_id,
            )
        )

        self.assertEqual(group, NURSING_EVENT_GROUP)
        self.assertEqual(
            set(payload),
            {
                "type",
                "event_id",
                "event_type",
                "occurred_at",
                "administration_id",
                "dispense_item_id",
                "encounter_id",
            },
        )
        self.assertEqual(payload["event_type"], "nursing.medication.administered")
        self.assertEqual(payload["administration_id"], str(administration_id))
        self.assertEqual(payload["dispense_item_id"], str(dispense_item_id))
        self.assertEqual(payload["encounter_id"], str(encounter_id))

    def test_asyncapi_event_names_match_runtime_allowlist(self):
        contract_path = (
            Path(settings.BASE_DIR)
            / "specs"
            / "004-enfermagem"
            / "contracts"
            / "events.asyncapi.yaml"
        )
        body = contract_path.read_text(encoding="utf-8")
        documented_names = set(
            re.findall(r"^\s+name:\s+([a-z.]+)\s*$", body, flags=re.MULTILINE)
        )

        self.assertEqual(documented_names, NURSING_EVENT_TYPES)


class NursingMutationAuditEventTests(TestCase):
    def setUp(self):
        self.nurse = User.objects.create_user(
            username="nursing-audit-service",
            password="test-password",
            nivel_permissao="FUNC",
        )
        for codename in ("record_vitals", "administer_medication"):
            permission = Permission.objects.get(
                content_type__app_label="nursing",
                codename=codename,
            )
            self.nurse.user_permissions.add(permission)

        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="NUR-AUDIT-SERVICE",
            full_name="Paciente Sintético Auditoria",
            birth_date=date(1990, 1, 1),
            created_by=self.nurse,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            status=Encounter.Status.OPEN,
            started_at=timezone.now() - timedelta(hours=1),
            responsible_professional=self.nurse,
            created_by=self.nurse,
        )
        self.drug = Drug.objects.create(
            code="NUR-AUDIT-DRUG",
            name="Medicamento Sintético Auditoria",
            presentation="Apresentação sintética",
            dispense_unit="unidade",
        )
        self.request = MedicationRequest.objects.create(
            encounter=self.encounter,
            authored_by=self.nurse,
        )
        self.request_item = MedicationRequestItem.objects.create(
            medication_request=self.request,
            drug=self.drug,
            dose=Decimal("10"),
            dose_unit="mg",
            route="oral",
            frequency="1x ao dia",
            sequence=1,
        )
        self.request.status = MedicationRequest.Status.VALIDATED
        self.request.submitted_at = timezone.now() - timedelta(minutes=30)
        self.request.validated_by = self.nurse
        self.request.validated_at = timezone.now() - timedelta(minutes=20)
        self.request.save()
        self.stock = StockItem.objects.create(
            drug=self.drug,
            storage_location="Farmácia auditoria enfermagem",
        )
        self.lot = Lot.objects.create(
            stock_item=self.stock,
            lot_number="NUR-AUDIT-LOT",
            expires_on=timezone.localdate() + timedelta(days=90),
            quantity_available=Decimal("10"),
        )
        self.dispense = MedicationDispense.objects.create(
            medication_request=self.request,
            dispensed_by=self.nurse,
            dispensed_at=timezone.now() - timedelta(minutes=10),
        )
        self.dispense_item = MedicationDispenseItem.objects.create(
            dispense=self.dispense,
            request_item=self.request_item,
            lot=self.lot,
            quantity=Decimal("2"),
        )

    def test_vitals_create_is_attributed_and_retry_emits_once(self):
        operation_key = uuid.uuid4()
        data = {
            "recorded_at": timezone.now().replace(microsecond=0) - timedelta(minutes=5),
            "heart_rate_bpm": 72,
        }

        with patch("apps.clinical.nursing.services.emit_vitals_recorded_event") as emit:
            first = record_vital_signs(
                encounter=self.encounter,
                actor=self.nurse,
                data=data,
                idempotency_key=operation_key,
            )
            second = record_vital_signs(
                encounter=self.encounter,
                actor=self.nurse,
                data=data,
                idempotency_key=operation_key,
            )

        self.assertEqual(first.pk, second.pk)
        emit.assert_called_once_with(
            record_id=first.pk,
            encounter_id=self.encounter.pk,
            origin=VitalSignsRecord.Origin.ONLINE,
            replaces_id=None,
        )
        entry = LogEntry.objects.get(
            content_type=ContentType.objects.get_for_model(VitalSignsRecord),
            object_pk=str(first.pk),
            action=LogEntry.Action.CREATE,
        )
        self.assertEqual(entry.actor, self.nurse)
        self.assertFalse(
            {
                "temperature_c",
                "heart_rate_bpm",
                "respiratory_rate_irpm",
                "systolic_bp_mmhg",
                "diastolic_bp_mmhg",
                "oxygen_saturation_pct",
                "weight_kg",
            }.intersection(entry.changes or {})
        )

    def test_administration_create_is_attributed_and_retry_emits_once(self):
        operation_key = uuid.uuid4()
        data = {
            "administered_at": timezone.now().replace(microsecond=0) - timedelta(minutes=2),
            "administered_dose": Decimal("7.5000"),
            "administered_dose_unit": "mL",
        }

        with patch(
            "apps.clinical.nursing.services.emit_medication_administered_event"
        ) as emit:
            first = administer_medication(
                dispense_item_id=self.dispense_item.pk,
                actor=self.nurse,
                data=data,
                operation_key=operation_key,
            )
            second = administer_medication(
                dispense_item_id=self.dispense_item.pk,
                actor=self.nurse,
                data=data,
                operation_key=operation_key,
            )

        self.assertEqual(first.pk, second.pk)
        emit.assert_called_once_with(
            administration_id=first.pk,
            dispense_item_id=self.dispense_item.pk,
            encounter_id=self.encounter.pk,
        )
        entry = LogEntry.objects.get(
            content_type=ContentType.objects.get_for_model(MedicationAdministration),
            object_pk=str(first.pk),
            action=LogEntry.Action.CREATE,
        )
        self.assertEqual(entry.actor, self.nurse)
        self.assertFalse(
            {"administered_dose", "administered_dose_unit"}.intersection(
                entry.changes or {}
            )
        )

    def test_service_actor_context_does_not_leak_to_later_write(self):
        record_vital_signs(
            encounter=self.encounter,
            actor=self.nurse,
            data={
                "recorded_at": timezone.now().replace(microsecond=0) - timedelta(minutes=5),
                "heart_rate_bpm": 72,
            },
        )
        later = VitalSignsRecord.objects.create(
            encounter=self.encounter,
            recorded_by=self.nurse,
            recorded_at=timezone.now().replace(microsecond=0) - timedelta(minutes=4),
            heart_rate_bpm=73,
        )

        entry = LogEntry.objects.get(
            content_type=ContentType.objects.get_for_model(VitalSignsRecord),
            object_pk=str(later.pk),
            action=LogEntry.Action.CREATE,
        )
        self.assertIsNone(entry.actor)


@override_settings(STORAGES=TEST_STORAGES)
class NursingReadAuditTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(
            username="nursing-audit-viewer",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.other = User.objects.create_user(
            username="nursing-audit-other",
            password="test-password",
            nivel_permissao="FUNC",
        )
        for codename in ("view_nursing", "administer_medication"):
            permission = Permission.objects.get(
                content_type__app_label="nursing",
                codename=codename,
            )
            self.viewer.user_permissions.add(permission)

        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="NUR-AUDIT-VIEW",
            full_name="Paciente Sintético Leitura",
            birth_date=date(1988, 2, 2),
            created_by=self.viewer,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            status=Encounter.Status.OPEN,
            started_at=timezone.now() - timedelta(hours=1),
            responsible_professional=self.viewer,
            created_by=self.viewer,
        )
        self.vital = VitalSignsRecord.objects.create(
            encounter=self.encounter,
            recorded_by=self.viewer,
            recorded_at=timezone.now() - timedelta(minutes=20),
            heart_rate_bpm=70,
        )
        self.drug = Drug.objects.create(
            code="NUR-AUDIT-VIEW-DRUG",
            name="Medicamento Sintético Leitura",
            presentation="Apresentação sintética",
            dispense_unit="unidade",
        )
        request = MedicationRequest.objects.create(
            encounter=self.encounter,
            authored_by=self.viewer,
        )
        request_item = MedicationRequestItem.objects.create(
            medication_request=request,
            drug=self.drug,
            dose=Decimal("1"),
            dose_unit="mg",
            route="oral",
            frequency="1x ao dia",
            sequence=1,
        )
        request.status = MedicationRequest.Status.VALIDATED
        request.submitted_at = timezone.now() - timedelta(minutes=15)
        request.validated_by = self.viewer
        request.validated_at = timezone.now() - timedelta(minutes=14)
        request.save()
        stock = StockItem.objects.create(
            drug=self.drug,
            storage_location="Farmácia leitura enfermagem",
        )
        lot = Lot.objects.create(
            stock_item=stock,
            lot_number="NUR-AUDIT-VIEW-LOT",
            expires_on=timezone.localdate() + timedelta(days=60),
            quantity_available=Decimal("5"),
        )
        dispense = MedicationDispense.objects.create(
            medication_request=request,
            dispensed_by=self.viewer,
            dispensed_at=timezone.now() - timedelta(minutes=10),
        )
        self.dispense_item = MedicationDispenseItem.objects.create(
            dispense=dispense,
            request_item=request_item,
            lot=lot,
            quantity=Decimal("1"),
        )
        self.client.force_login(self.viewer)

    def _has_access(self, instance):
        return LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(instance.__class__),
            object_pk=str(instance.pk),
            action=LogEntry.Action.ACCESS,
            actor=self.viewer,
        ).exists()

    def test_encounter_page_audits_rendered_encounter_and_vital(self):
        response = self.client.get(
            reverse("nursing:encounter", kwargs={"pk": self.encounter.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self._has_access(self.encounter))
        self.assertTrue(self._has_access(self.vital))

    def test_medication_list_audits_rendered_encounter_and_dispense_item(self):
        response = self.client.get(
            reverse("nursing:medication_list", kwargs={"encounter_id": self.encounter.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self._has_access(self.encounter))
        self.assertTrue(self._has_access(self.dispense_item))

    def test_worklist_audits_only_current_page(self):
        for index in range(25):
            Encounter.objects.create(
                patient=self.patient,
                status=Encounter.Status.OPEN,
                started_at=timezone.now() - timedelta(minutes=index + 2),
                responsible_professional=self.viewer,
                created_by=self.viewer,
            )

        response = self.client.get(reverse("nursing:worklist"))

        self.assertEqual(response.status_code, 200)
        rendered_ids = {str(item.pk) for item in response.context["encounters"]}
        entries = LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(Encounter),
            action=LogEntry.Action.ACCESS,
            actor=self.viewer,
        )
        self.assertEqual(set(entries.values_list("object_pk", flat=True)), rendered_ids)
        self.assertEqual(len(rendered_ids), 25)

    def test_out_of_scope_denial_does_not_audit_or_echo_patient(self):
        outside_patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="NUR-AUDIT-OUTSIDE",
            full_name="Paciente Não Autorizado",
            birth_date=date(1992, 3, 3),
            created_by=self.other,
        )
        outside_encounter = Encounter.objects.create(
            patient=outside_patient,
            status=Encounter.Status.OPEN,
            responsible_professional=self.other,
            created_by=self.other,
        )

        response = self.client.get(
            reverse("nursing:encounter", kwargs={"pk": outside_encounter.pk})
        )

        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, outside_patient.full_name, status_code=404)
        self.assertFalse(self._has_access(outside_encounter))
