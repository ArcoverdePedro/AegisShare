from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.models import Encounter, Patient, PatientAccessGrant

from ..models import Drug, MedicationRequest
from ..services import (
    PrescriptionItemError,
    PrescriptionStateError,
    add_medication_request_item,
    create_medication_request,
    remove_medication_request_item,
    submit_medication_request,
)


class PrescriptionLifecycleServiceTests(TestCase):
    def setUp(self):
        self.admin = make_user("rx-service-admin", role="ADM")
        self.prescriber = make_user("rx-service-prescriber", role="FUNC")
        self.other = make_user("rx-service-other", role="FUNC")
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="RX-SERVICE-PATIENT",
            full_name="Paciente Serviço RX",
            birth_date=timezone.localdate() - timedelta(days=365 * 30),
            created_by=self.admin,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            responsible_professional=self.prescriber,
            created_by=self.admin,
        )
        self.drug = Drug.objects.create(
            code="RX-SVC-001",
            name="Medicamento Sintético Serviço",
            presentation="Comprimido de teste",
            dispense_unit="unidade",
        )
        self._grant_patient(self.prescriber)
        self._grant_patient(self.other)
        self._grant_permission(self.prescriber, "prescribe_medication")
        self._grant_permission(self.other, "prescribe_medication")

    def _grant_permission(self, user, codename):
        permission = Permission.objects.get(
            codename=codename,
            content_type__app_label="prescription",
        )
        user.user_permissions.add(permission)
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            if hasattr(user, cache_name):
                delattr(user, cache_name)

    def _grant_patient(self, user):
        PatientAccessGrant.objects.create(
            patient=self.patient,
            user=user,
            granted_by=self.admin,
            reason="Cobertura assistencial sintética",
        )

    def _create_draft(self):
        return create_medication_request(
            encounter_id=self.encounter.pk,
            actor=self.prescriber,
        )

    def _add_item(self, request, *, sequence=1, drug=None):
        return add_medication_request_item(
            request_id=request.pk,
            actor=self.prescriber,
            drug_id=(drug or self.drug).pk,
            dose=Decimal("10"),
            dose_unit="mg",
            route="oral",
            frequency="1x ao dia",
            sequence=sequence,
        )

    def test_create_draft_requires_capability_and_pep_scope(self):
        outsider = make_user("rx-service-outsider", role="FUNC")
        self._grant_permission(outsider, "prescribe_medication")

        with self.assertRaises(PermissionDenied):
            create_medication_request(
                encounter_id=self.encounter.pk,
                actor=outsider,
            )

    def test_create_draft_rejects_closed_encounter(self):
        self.encounter.status = Encounter.Status.CLOSED
        self.encounter.ended_at = timezone.now()
        self.encounter.save()

        with self.assertRaises(PrescriptionStateError):
            self._create_draft()

    def test_only_author_can_mutate_draft(self):
        request = self._create_draft()

        with self.assertRaises(PermissionDenied):
            add_medication_request_item(
                request_id=request.pk,
                actor=self.other,
                drug_id=self.drug.pk,
                dose=Decimal("10"),
                dose_unit="mg",
                route="oral",
                frequency="1x ao dia",
                sequence=1,
            )

    def test_submit_requires_at_least_one_item(self):
        request = self._create_draft()

        with self.assertRaises(PrescriptionItemError):
            submit_medication_request(request_id=request.pk, actor=self.prescriber)

    def test_submit_freezes_item_mutation(self):
        request = self._create_draft()
        item = self._add_item(request)

        submitted = submit_medication_request(
            request_id=request.pk,
            actor=self.prescriber,
        )

        self.assertEqual(submitted.status, MedicationRequest.Status.SUBMITTED)
        self.assertIsNotNone(submitted.submitted_at)
        with self.assertRaises(PrescriptionStateError):
            remove_medication_request_item(
                request_id=request.pk,
                item_id=item.pk,
                actor=self.prescriber,
            )
        item.frequency = "2x ao dia"
        with self.assertRaises(ValidationError):
            item.save()

    def test_duplicate_drug_is_rejected_in_same_draft(self):
        request = self._create_draft()
        self._add_item(request)

        with self.assertRaises(PrescriptionItemError):
            self._add_item(request, sequence=2)

    @override_settings(RX_MAX_ITEMS_PER_REQUEST=1)
    def test_configurable_item_limit_is_enforced(self):
        request = self._create_draft()
        self._add_item(request)
        other_drug = Drug.objects.create(
            code="RX-SVC-002",
            name="Segundo Medicamento Sintético",
            presentation="Comprimido de teste",
            dispense_unit="unidade",
        )

        with self.assertRaises(PrescriptionItemError):
            self._add_item(request, sequence=2, drug=other_drug)

    def test_submitted_request_can_be_replaced_in_same_encounter(self):
        request = self._create_draft()
        self._add_item(request)
        submit_medication_request(request_id=request.pk, actor=self.prescriber)

        replacement = create_medication_request(
            encounter_id=self.encounter.pk,
            actor=self.prescriber,
            replaces_id=request.pk,
        )

        self.assertEqual(replacement.status, MedicationRequest.Status.DRAFT)
        self.assertEqual(replacement.replaces_id, request.pk)

    def test_draft_cannot_be_replaced(self):
        request = self._create_draft()

        with self.assertRaises(PrescriptionStateError):
            create_medication_request(
                encounter_id=self.encounter.pk,
                actor=self.prescriber,
                replaces_id=request.pk,
            )

    def test_same_request_cannot_receive_two_replacements(self):
        request = self._create_draft()
        self._add_item(request)
        submit_medication_request(request_id=request.pk, actor=self.prescriber)
        create_medication_request(
            encounter_id=self.encounter.pk,
            actor=self.prescriber,
            replaces_id=request.pk,
        )

        with self.assertRaises(PrescriptionStateError):
            create_medication_request(
                encounter_id=self.encounter.pk,
                actor=self.prescriber,
                replaces_id=request.pk,
            )
