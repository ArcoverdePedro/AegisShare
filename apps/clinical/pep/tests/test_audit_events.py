from datetime import date
from unittest.mock import patch

from asgiref.sync import async_to_sync
from auditlog.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from aegis_share.tests.helpers import make_user

from ..consumers import PatientClinicalConsumer
from ..events import emit_clinical_event, patient_group_name
from ..models import ClinicalEvolution, Encounter, Patient, PatientAccessGrant


TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES)
class ClinicalReadAuditTests(TestCase):
    def setUp(self):
        self.user = make_user("pep-audit-user", role="FUNC")
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="AUDIT-MRN-001",
            full_name="Paciente Auditoria",
            birth_date=date(1982, 3, 8),
            created_by=self.user,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            started_at=timezone.now(),
            responsible_professional=self.user,
            created_by=self.user,
        )
        self.evolution = ClinicalEvolution.objects.create(
            encounter=self.encounter,
            author=self.user,
            content="Registro clínico protegido para teste de auditoria.",
        )
        self.client.force_login(self.user)

    def assert_access_logged(self, instance):
        content_type = ContentType.objects.get_for_model(instance.__class__)
        self.assertTrue(
            LogEntry.objects.filter(
                content_type=content_type,
                object_pk=str(instance.pk),
                action=LogEntry.Action.ACCESS,
                actor=self.user,
            ).exists()
        )

    def test_patient_detail_read_is_audited(self):
        response = self.client.get(reverse("pep:patient_detail", args=[self.patient.id]))

        self.assertEqual(response.status_code, 200)
        self.assert_access_logged(self.patient)

    def test_encounter_detail_read_is_audited(self):
        response = self.client.get(
            reverse("pep:encounter_detail", args=[self.encounter.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assert_access_logged(self.encounter)

    def test_evolution_detail_read_is_audited(self):
        response = self.client.get(
            reverse("pep:evolution_detail", args=[self.evolution.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assert_access_logged(self.evolution)

    def test_amendment_form_read_audits_original_evolution(self):
        response = self.client.get(
            reverse("pep:evolution_amendment_create", args=[self.evolution.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assert_access_logged(self.evolution)


class _RecordingChannelLayer:
    def __init__(self):
        self.calls = []

    async def group_send(self, group, payload):
        self.calls.append((group, payload))


class ClinicalEventServiceTests(TestCase):
    def test_event_payload_contains_only_non_clinical_identifiers(self):
        layer = _RecordingChannelLayer()

        with (
            patch("apps.clinical.pep.events.get_channel_layer", return_value=layer),
            patch(
                "apps.clinical.pep.events.transaction.on_commit",
                side_effect=lambda callback: callback(),
            ),
        ):
            emit_clinical_event(
                event="evolution.created",
                patient_id="11111111-1111-1111-1111-111111111111",
                encounter_id="22222222-2222-2222-2222-222222222222",
                object_id="33333333-3333-3333-3333-333333333333",
            )

        self.assertEqual(len(layer.calls), 1)
        group, payload = layer.calls[0]
        self.assertEqual(
            group,
            "clinical_patient_11111111-1111-1111-1111-111111111111",
        )
        self.assertEqual(payload["event"], "evolution.created")
        self.assertEqual(
            set(payload),
            {
                "type",
                "event",
                "patient_id",
                "encounter_id",
                "object_id",
                "occurred_at",
            },
        )
        for forbidden in ("content", "reason", "patient_name", "author", "diagnosis"):
            self.assertNotIn(forbidden, payload)

    def test_unknown_clinical_event_is_rejected(self):
        with self.assertRaises(ValueError):
            emit_clinical_event(
                event="clinical.free_text",
                patient_id="11111111-1111-1111-1111-111111111111",
            )

    def test_patient_group_name_is_deterministic(self):
        patient_id = "11111111-1111-1111-1111-111111111111"
        self.assertEqual(
            patient_group_name(patient_id),
            f"clinical_patient_{patient_id}",
        )


class ClinicalConsumerAuthorizationTests(TransactionTestCase):
    def setUp(self):
        self.owner = make_user("pep-socket-owner", role="FUNC")
        self.other = make_user("pep-socket-other", role="FUNC")
        self.admin = make_user("pep-socket-admin", role="ADM")
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="SOCKET-MRN-001",
            full_name="Paciente Socket",
            birth_date=date(1991, 8, 17),
            created_by=self.owner,
        )

    def consumer_for(self, user):
        consumer = PatientClinicalConsumer()
        consumer.user = user
        consumer.patient_id = self.patient.id
        return consumer

    def test_owner_is_authorized_for_patient_channel(self):
        consumer = self.consumer_for(self.owner)
        self.assertTrue(async_to_sync(consumer.user_can_access_patient)())

    def test_unrelated_employee_is_denied(self):
        consumer = self.consumer_for(self.other)
        self.assertFalse(async_to_sync(consumer.user_can_access_patient)())

    def test_access_is_revalidated_after_grant_revocation(self):
        PatientAccessGrant.objects.create(
            patient=self.patient,
            user=self.other,
            reason="Equipe assistencial temporária",
            granted_by=self.admin,
        )
        consumer = self.consumer_for(self.other)
        self.assertTrue(async_to_sync(consumer.user_can_access_patient)())

        PatientAccessGrant.objects.filter(patient=self.patient, user=self.other).delete()

        self.assertFalse(async_to_sync(consumer.user_can_access_patient)())
