from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from auditlog.models import LogEntry
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.models import Encounter, Patient, PatientAccessGrant

from ..models import Drug, MedicationRequest, MedicationRequestItem
from ..services import (
    add_medication_request_item,
    create_medication_request,
    remove_medication_request_item,
    submit_medication_request,
)


class PrescriptionAuditActorTests(TestCase):
    def setUp(self):
        self.admin = make_user("rx-prescription-audit-admin", role="ADM")
        self.prescriber = make_user("rx-prescription-audit-actor", role="FUNC")
        permission = Permission.objects.get(
            codename="prescribe_medication",
            content_type__app_label="prescription",
        )
        self.prescriber.user_permissions.add(permission)
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="RX-PRESCRIPTION-AUDIT-PATIENT",
            full_name="Paciente Sintético Auditoria RX",
            birth_date=timezone.localdate() - timedelta(days=365 * 30),
            created_by=self.admin,
        )
        PatientAccessGrant.objects.create(
            patient=self.patient,
            user=self.prescriber,
            granted_by=self.admin,
            reason="Cobertura sintética de auditoria RX",
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            responsible_professional=self.prescriber,
            created_by=self.admin,
        )
        self.drug = Drug.objects.create(
            code="RX-PRESCRIPTION-AUDIT-DRUG",
            name="Medicamento Sintético Auditoria RX",
            presentation="Apresentação sintética",
            dispense_unit="unidade",
        )

    def assert_action_actor(self, instance, action):
        content_type = ContentType.objects.get_for_model(instance.__class__)
        entry = LogEntry.objects.filter(
            content_type=content_type,
            object_pk=str(instance.pk),
            action=action,
        ).latest("timestamp")
        self.assertEqual(entry.actor, self.prescriber)

    def _add_item(self, request, *, sequence):
        return add_medication_request_item(
            request_id=request.pk,
            actor=self.prescriber,
            drug_id=self.drug.pk,
            dose=Decimal("1"),
            dose_unit="unidade",
            route="via sintética",
            frequency="frequência sintética",
            sequence=sequence,
        )

    def test_prescription_service_writes_are_attributed_to_explicit_actor(self):
        request = create_medication_request(
            encounter_id=self.encounter.pk,
            actor=self.prescriber,
        )
        self.assert_action_actor(request, LogEntry.Action.CREATE)

        removed_item = self._add_item(request, sequence=1)
        self.assert_action_actor(removed_item, LogEntry.Action.CREATE)

        remove_medication_request_item(
            request_id=request.pk,
            item_id=removed_item.pk,
            actor=self.prescriber,
        )
        self.assert_action_actor(removed_item, LogEntry.Action.DELETE)

        submitted_item = self._add_item(request, sequence=1)
        self.assert_action_actor(submitted_item, LogEntry.Action.CREATE)

        with patch("apps.clinical.prescription.services.emit_prescription_event"):
            submitted = submit_medication_request(
                request_id=request.pk,
                actor=self.prescriber,
            )
        self.assertEqual(submitted.status, MedicationRequest.Status.SUBMITTED)
        self.assert_action_actor(submitted, LogEntry.Action.UPDATE)

        self.assertFalse(MedicationRequestItem.objects.filter(pk=removed_item.pk).exists())
