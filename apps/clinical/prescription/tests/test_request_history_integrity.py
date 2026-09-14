from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase
from django.utils import timezone

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.models import Encounter, Patient

from ..models import MedicationRequest


class MedicationRequestHistoryIntegrityTests(TestCase):
    def setUp(self):
        self.actor = make_user("rx-request-history-admin", role="ADM")
        self.actor.is_superuser = True
        self.actor.is_staff = True
        self.actor.save(update_fields=["is_superuser", "is_staff"])

        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="RX-REQUEST-HISTORY-PATIENT",
            full_name="Pessoa Sintética Histórico de Prescrição",
            birth_date=timezone.localdate() - timedelta(days=365 * 30),
            created_by=self.actor,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            started_at=timezone.now() - timedelta(hours=1),
            responsible_professional=self.actor,
            created_by=self.actor,
        )

    def _request(self):
        return MedicationRequest.objects.create(
            encounter=self.encounter,
            authored_by=self.actor,
        )

    def _submit(self, request):
        request.status = MedicationRequest.Status.SUBMITTED
        request.submitted_at = timezone.now()
        request.save(update_fields=["status", "submitted_at", "updated_at"])
        return request

    def _assert_delete_rejected(self, callback):
        with self.assertRaises(ValidationError), transaction.atomic():
            callback()

    def test_draft_request_can_be_deleted(self):
        request = self._request()
        request_id = request.pk

        request.delete()

        self.assertFalse(MedicationRequest.objects.filter(pk=request_id).exists())

    def test_submitted_request_instance_delete_is_rejected(self):
        request = self._submit(self._request())
        request_id = request.pk

        self._assert_delete_rejected(request.delete)

        self.assertTrue(MedicationRequest.objects.filter(pk=request_id).exists())

    def test_submitted_request_bulk_delete_is_rejected(self):
        request = self._submit(self._request())
        queryset = MedicationRequest.objects.filter(pk=request.pk)

        self._assert_delete_rejected(queryset.delete)

        self.assertTrue(MedicationRequest.objects.filter(pk=request.pk).exists())

    def test_stale_draft_instance_cannot_delete_persisted_submitted_request(self):
        request = self._submit(self._request())
        request_id = request.pk
        request.status = MedicationRequest.Status.DRAFT
        request.submitted_at = None

        self._assert_delete_rejected(request.delete)

        persisted = MedicationRequest.objects.get(pk=request_id)
        self.assertEqual(persisted.status, MedicationRequest.Status.SUBMITTED)
