import uuid
from datetime import timedelta
from unittest.mock import patch

from asgiref.sync import async_to_sync
from auditlog.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.clinical.pep.models import Encounter, Patient

from ..consumers import AdtBedMapConsumer
from ..events import ADT_BED_MAP_GROUP, emit_adt_event
from ..lifecycle import discharge_patient, transfer_patient
from ..models import Admission, Bed, BedOccupancy, Discharge, Location, UserLocationAccess
from ..services import admit_patient

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


@override_settings(STORAGES=TEST_STORAGES)
class AdtAuditReadTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="adt-audit-admin",
            password="test-password",
            nivel_permissao="ADM",
        )
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="ADT-AUDIT-PATIENT",
            full_name="Paciente Auditoria ADT",
            birth_date=timezone.localdate() - timedelta(days=365 * 32),
            created_by=self.admin,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.INPATIENT,
            status=Encounter.Status.OPEN,
            started_at=timezone.now() - timedelta(hours=2),
            responsible_professional=self.admin,
            created_by=self.admin,
        )
        self.location = Location.objects.create(
            code="ADT-AUDIT",
            name="Unidade Auditoria",
            kind=Location.Kind.WARD,
        )
        self.bed = Bed.objects.create(
            location=self.location,
            code="A-01",
            label="Leito A01",
        )
        self.admission = Admission.objects.create(
            encounter=self.encounter,
            admitted_at=timezone.now() - timedelta(hours=1),
            admitted_by=self.admin,
        )
        self.occupancy = BedOccupancy.objects.create(
            admission=self.admission,
            bed=self.bed,
            started_at=self.admission.admitted_at,
            started_by=self.admin,
        )
        self.client.force_login(self.admin)

    def assert_access_logged(self, instance):
        content_type = ContentType.objects.get_for_model(instance.__class__)
        self.assertTrue(
            LogEntry.objects.filter(
                content_type=content_type,
                object_pk=str(instance.pk),
                action=LogEntry.Action.ACCESS,
                actor=self.admin,
            ).exists()
        )

    def test_admission_list_audits_admission_and_identifiable_patient(self):
        response = self.client.get(reverse("adt:admission_list"))
        self.assertEqual(response.status_code, 200)
        self.assert_access_logged(self.admission)
        self.assert_access_logged(self.patient)

    def test_bed_map_audits_occupancy_and_identifiable_patient(self):
        response = self.client.get(reverse("adt:bed_map"))
        self.assertEqual(response.status_code, 200)
        self.assert_access_logged(self.occupancy)
        self.assert_access_logged(self.patient)
        self.assertEqual(response["Cache-Control"], "private, no-store, max-age=0")


@override_settings(STORAGES=TEST_STORAGES)
class AdtEventTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="adt-event-admin",
            password="test-password",
            nivel_permissao="ADM",
        )
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="ADT-EVENT-PATIENT",
            full_name="Paciente Evento ADT",
            birth_date=timezone.localdate() - timedelta(days=365 * 40),
            created_by=self.admin,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.INPATIENT,
            status=Encounter.Status.OPEN,
            started_at=timezone.now() - timedelta(hours=3),
            responsible_professional=self.admin,
            created_by=self.admin,
        )
        self.location_a = Location.objects.create(
            code="ADT-EVENT-A",
            name="Unidade Evento A",
            kind=Location.Kind.WARD,
        )
        self.location_b = Location.objects.create(
            code="ADT-EVENT-B",
            name="Unidade Evento B",
            kind=Location.Kind.WARD,
        )
        self.bed_a = Bed.objects.create(
            location=self.location_a,
            code="A-01",
            label="Leito A01",
        )
        self.bed_b = Bed.objects.create(
            location=self.location_b,
            code="B-01",
            label="Leito B01",
        )

    def _create_admission(self):
        admitted_at = timezone.now() - timedelta(hours=2)
        admission = Admission.objects.create(
            encounter=self.encounter,
            admitted_at=admitted_at,
            admitted_by=self.admin,
        )
        occupancy = BedOccupancy.objects.create(
            admission=admission,
            bed=self.bed_a,
            started_at=admitted_at,
            started_by=self.admin,
        )
        return admission, occupancy

    def test_event_payload_contains_only_operational_identifiers(self):
        layer = _RecordingChannelLayer()
        with (
            patch("apps.clinical.adt.events.get_channel_layer", return_value=layer),
            patch(
                "apps.clinical.adt.events.transaction.on_commit",
                side_effect=lambda callback: callback(),
            ),
        ):
            emit_adt_event(
                event_type="bed.occupied",
                bed_id=self.bed_a.pk,
                location_id=self.location_a.pk,
                state="OCCUPIED",
            )

        self.assertEqual(len(layer.calls), 1)
        group, payload = layer.calls[0]
        self.assertEqual(group, ADT_BED_MAP_GROUP)
        self.assertEqual(payload["event_type"], "bed.occupied")
        self.assertEqual(
            set(payload),
            {
                "type",
                "event_id",
                "event_type",
                "occurred_at",
                "bed_id",
                "location_id",
                "state",
            },
        )
        for forbidden in ("patient_name", "identifier", "reason", "diagnosis", "notes"):
            self.assertNotIn(forbidden, payload)

    def test_unknown_event_is_rejected(self):
        with self.assertRaises(ValueError):
            emit_adt_event(event_type="adt.free_text")

    @patch("apps.clinical.adt.services.emit_adt_event")
    def test_admission_emits_encounter_and_bed_invalidation(self, emit):
        admission = admit_patient(
            encounter_id=self.encounter.pk,
            bed_id=self.bed_a.pk,
            actor=self.admin,
            operation_key=uuid.uuid4(),
        )
        self.assertEqual(admission.encounter_id, self.encounter.pk)
        self.assertEqual(
            [call.kwargs["event_type"] for call in emit.call_args_list],
            ["encounter.admitted", "bed.occupied"],
        )

    @patch("apps.clinical.adt.lifecycle.emit_adt_event")
    def test_transfer_emits_encounter_release_and_occupancy_events(self, emit):
        admission, _occupancy = self._create_admission()
        transfer_patient(
            admission_id=admission.pk,
            destination_bed_id=self.bed_b.pk,
            actor=self.admin,
            operation_key=uuid.uuid4(),
        )
        self.assertEqual(
            [call.kwargs["event_type"] for call in emit.call_args_list],
            ["encounter.transferred", "bed.released", "bed.occupied"],
        )

    @patch("apps.clinical.adt.lifecycle.emit_adt_event")
    def test_discharge_emits_encounter_and_release_events(self, emit):
        admission, _occupancy = self._create_admission()
        discharge_patient(
            admission_id=admission.pk,
            disposition=Discharge.Disposition.HOME,
            actor=self.admin,
            operation_key=uuid.uuid4(),
        )
        self.assertEqual(
            [call.kwargs["event_type"] for call in emit.call_args_list],
            ["encounter.discharged", "bed.released"],
        )


@override_settings(STORAGES=TEST_STORAGES)
class AdtConsumerAuthorizationTests(TransactionTestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="adt-socket-admin",
            password="test-password",
            nivel_permissao="ADM",
        )
        self.employee = User.objects.create_user(
            username="adt-socket-employee",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.location = Location.objects.create(
            code="ADT-SOCKET",
            name="Unidade Socket",
            kind=Location.Kind.WARD,
        )
        UserLocationAccess.objects.create(
            user=self.employee,
            location=self.location,
            granted_by=self.admin,
        )
        permission = Permission.objects.get(
            codename="view_bed_map",
            content_type__app_label="adt",
        )
        self.employee.user_permissions.add(permission)

    def consumer_for(self, user):
        consumer = AdtBedMapConsumer()
        consumer.user = user
        return consumer

    def test_employee_with_capability_can_open_bed_map_channel(self):
        consumer = self.consumer_for(self.employee)
        self.assertTrue(async_to_sync(consumer.user_can_view_bed_map)())
        self.assertTrue(
            async_to_sync(consumer.user_can_access_location)(self.location.pk)
        )

    def test_location_scope_is_revalidated_after_revocation(self):
        consumer = self.consumer_for(self.employee)
        self.assertTrue(
            async_to_sync(consumer.user_can_access_location)(self.location.pk)
        )
        UserLocationAccess.objects.filter(
            user=self.employee,
            location=self.location,
        ).delete()
        self.assertFalse(
            async_to_sync(consumer.user_can_access_location)(self.location.pk)
        )

    def test_client_role_cannot_open_bed_map_channel(self):
        client_user = User.objects.create_user(
            username="adt-socket-client",
            password="test-password",
            nivel_permissao="CLI",
        )
        consumer = self.consumer_for(client_user)
        self.assertFalse(async_to_sync(consumer.user_can_view_bed_map)())
