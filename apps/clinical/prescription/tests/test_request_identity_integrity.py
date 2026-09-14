from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.utils import timezone

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.models import Encounter, Patient

from ..models import MedicationRequest


class RequestIdentityFixtureMixin:
    def setUp(self):
        super().setUp()
        self.author = make_user("rx-request-history-author", role="ADM")
        self.other_author = make_user("rx-request-history-other", role="ADM")
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="RX-REQUEST-HISTORY-PATIENT",
            full_name="Paciente Sintético Histórico",
            birth_date=timezone.localdate() - timedelta(days=365 * 30),
            created_by=self.author,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            responsible_professional=self.author,
            created_by=self.author,
        )
        self.other_encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            responsible_professional=self.other_author,
            created_by=self.author,
        )
        self.submitted_at = timezone.now()
        self.submitted_request = MedicationRequest.objects.create(
            encounter=self.encounter,
            authored_by=self.author,
            status=MedicationRequest.Status.SUBMITTED,
            submitted_at=self.submitted_at,
        )
        self.draft_request = MedicationRequest.objects.create(
            encounter=self.encounter,
            authored_by=self.author,
        )


class RequestIdentityApplicationIntegrityTests(RequestIdentityFixtureMixin, TestCase):
    def test_submitted_request_author_cannot_be_rewritten_through_save(self):
        self.submitted_request.authored_by = self.other_author

        with self.assertRaises(ValidationError):
            self.submitted_request.save()

        self.submitted_request.refresh_from_db()
        self.assertEqual(self.submitted_request.authored_by_id, self.author.pk)

    def test_submitted_timestamp_cannot_be_rewritten_through_save(self):
        self.submitted_request.submitted_at = self.submitted_at + timedelta(minutes=5)

        with self.assertRaises(ValidationError):
            self.submitted_request.save()

        self.submitted_request.refresh_from_db()
        self.assertEqual(self.submitted_request.submitted_at, self.submitted_at)

    def test_identity_cannot_change_while_leaving_draft(self):
        self.draft_request.encounter = self.other_encounter
        self.draft_request.status = MedicationRequest.Status.SUBMITTED
        self.draft_request.submitted_at = timezone.now()

        with self.assertRaises(ValidationError):
            self.draft_request.save()

        self.draft_request.refresh_from_db()
        self.assertEqual(self.draft_request.status, MedicationRequest.Status.DRAFT)
        self.assertEqual(self.draft_request.encounter_id, self.encounter.pk)

    def test_draft_identity_remains_editable_before_submission(self):
        self.draft_request.encounter = self.other_encounter
        self.draft_request.authored_by = self.other_author
        self.draft_request.save()
        self.draft_request.refresh_from_db()

        self.assertEqual(self.draft_request.encounter_id, self.other_encounter.pk)
        self.assertEqual(self.draft_request.authored_by_id, self.other_author.pk)


class RequestIdentityPostgreSQLIntegrityTests(RequestIdentityFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        if connection.vendor != "postgresql":
            self.skipTest("Os guards desta suíte são específicos do PostgreSQL.")

    def test_bulk_update_cannot_rewrite_submitted_author(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            MedicationRequest.objects.filter(pk=self.submitted_request.pk).update(
                authored_by=self.other_author
            )

        self.submitted_request.refresh_from_db()
        self.assertEqual(self.submitted_request.authored_by_id, self.author.pk)

    def test_raw_sql_cannot_rewrite_submitted_timestamp(self):
        table = connection.ops.quote_name(MedicationRequest._meta.db_table)
        rewritten_at = self.submitted_at + timedelta(minutes=10)

        with self.assertRaises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {table} SET submitted_at = %s WHERE id = %s",
                [rewritten_at, self.submitted_request.pk],
            )

        self.submitted_request.refresh_from_db()
        self.assertEqual(self.submitted_request.submitted_at, self.submitted_at)

    def test_bulk_transition_cannot_rewrite_identity_while_leaving_draft(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            MedicationRequest.objects.filter(pk=self.draft_request.pk).update(
                encounter=self.other_encounter,
                status=MedicationRequest.Status.SUBMITTED,
                submitted_at=timezone.now(),
            )

        self.draft_request.refresh_from_db()
        self.assertEqual(self.draft_request.status, MedicationRequest.Status.DRAFT)
        self.assertEqual(self.draft_request.encounter_id, self.encounter.pk)

    def test_draft_identity_bulk_update_remains_allowed(self):
        updated = MedicationRequest.objects.filter(pk=self.draft_request.pk).update(
            encounter=self.other_encounter,
            authored_by=self.other_author,
        )

        self.assertEqual(updated, 1)
        self.draft_request.refresh_from_db()
        self.assertEqual(self.draft_request.encounter_id, self.other_encounter.pk)
        self.assertEqual(self.draft_request.authored_by_id, self.other_author.pk)
