import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.clinical.pep.models import Encounter, Patient, PatientAccessGrant

from ..lifecycle import DischargeStateError, transfer_patient, discharge_patient
from ..models import (
    Admission,
    Bed,
    BedOccupancy,
    Discharge,
    Location,
    Transfer,
    UserLocationAccess,
)
from ..services import BedUnavailableError

User = get_user_model()

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES)
class AdtLifecycleTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="adt-lifecycle-admin",
            password="test-password",
            nivel_permissao="ADM",
        )
        self.employee = User.objects.create_user(
            username="adt-lifecycle-employee",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="ADT-LIFECYCLE-PATIENT",
            full_name="Paciente Lifecycle ADT",
            birth_date=timezone.localdate() - timedelta(days=365 * 35),
            created_by=self.admin,
        )
        PatientAccessGrant.objects.create(
            patient=self.patient,
            user=self.employee,
            granted_by=self.admin,
            reason="Assistência ADT",
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.INPATIENT,
            status=Encounter.Status.OPEN,
            started_at=timezone.now() - timedelta(hours=4),
            responsible_professional=self.admin,
            created_by=self.admin,
        )
        self.location = Location.objects.create(
            code="ADT-A",
            name="Unidade A",
            kind=Location.Kind.WARD,
        )
        self.other_location = Location.objects.create(
            code="ADT-B",
            name="Unidade B",
            kind=Location.Kind.WARD,
        )
        self.denied_location = Location.objects.create(
            code="ADT-C",
            name="Unidade C",
            kind=Location.Kind.WARD,
        )
        self.source_bed = Bed.objects.create(
            location=self.location,
            code="A-01",
            label="Leito A01",
        )
        self.destination_bed = Bed.objects.create(
            location=self.other_location,
            code="B-01",
            label="Leito B01",
        )
        self.denied_bed = Bed.objects.create(
            location=self.denied_location,
            code="C-01",
            label="Leito C01",
        )
        for location in (self.location, self.other_location):
            UserLocationAccess.objects.create(
                user=self.employee,
                location=location,
                granted_by=self.admin,
            )
        admitted_at = timezone.now() - timedelta(hours=3)
        self.admission = Admission.objects.create(
            encounter=self.encounter,
            admitted_at=admitted_at,
            admitted_by=self.admin,
        )
        self.occupancy = BedOccupancy.objects.create(
            admission=self.admission,
            bed=self.source_bed,
            started_at=admitted_at,
            started_by=self.admin,
        )

    def _grant(self, codename):
        permission = Permission.objects.get(
            codename=codename,
            content_type__app_label="adt",
        )
        self.employee.user_permissions.add(permission)
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            if hasattr(self.employee, cache_name):
                delattr(self.employee, cache_name)

    def test_transfer_closes_source_and_opens_destination_atomically(self):
        self._grant("transfer_patient")
        when = timezone.now()
        transfer = transfer_patient(
            admission_id=self.admission.pk,
            destination_bed_id=self.destination_bed.pk,
            actor=self.employee,
            operation_key=uuid.uuid4(),
            transferred_at=when,
            reason="Mudança assistencial",
        )
        self.occupancy.refresh_from_db()
        self.assertEqual(self.occupancy.end_reason, BedOccupancy.EndReason.TRANSFER)
        self.assertEqual(self.occupancy.ended_at, when)
        active = BedOccupancy.objects.get(
            admission=self.admission,
            ended_at__isnull=True,
        )
        self.assertEqual(active.bed, self.destination_bed)
        self.assertEqual(transfer.source_occupancy, self.occupancy)
        self.assertEqual(transfer.destination_occupancy, active)

    def test_transfer_is_idempotent_for_same_operation_key(self):
        self._grant("transfer_patient")
        operation_key = uuid.uuid4()
        first = transfer_patient(
            admission_id=self.admission.pk,
            destination_bed_id=self.destination_bed.pk,
            actor=self.employee,
            operation_key=operation_key,
        )
        second = transfer_patient(
            admission_id=self.admission.pk,
            destination_bed_id=self.destination_bed.pk,
            actor=self.employee,
            operation_key=operation_key,
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Transfer.objects.count(), 1)
        self.assertEqual(self.admission.occupancies.count(), 2)

    def test_unavailable_destination_rolls_back_source_occupancy(self):
        self._grant("transfer_patient")
        self.destination_bed.operational_status = Bed.OperationalStatus.BLOCKED
        self.destination_bed.save()
        with self.assertRaises(BedUnavailableError):
            transfer_patient(
                admission_id=self.admission.pk,
                destination_bed_id=self.destination_bed.pk,
                actor=self.employee,
                operation_key=uuid.uuid4(),
            )
        self.occupancy.refresh_from_db()
        self.assertIsNone(self.occupancy.ended_at)
        self.assertEqual(Transfer.objects.count(), 0)

    def test_transfer_requires_destination_location_scope(self):
        self._grant("transfer_patient")
        with self.assertRaises(PermissionDenied):
            transfer_patient(
                admission_id=self.admission.pk,
                destination_bed_id=self.denied_bed.pk,
                actor=self.employee,
                operation_key=uuid.uuid4(),
            )
        self.occupancy.refresh_from_db()
        self.assertIsNone(self.occupancy.ended_at)

    def test_discharge_closes_occupancy_and_encounter_atomically(self):
        self._grant("discharge_patient")
        when = timezone.now()
        discharge = discharge_patient(
            admission_id=self.admission.pk,
            disposition=Discharge.Disposition.HOME,
            actor=self.employee,
            operation_key=uuid.uuid4(),
            discharged_at=when,
            reason="Alta assistencial",
        )
        self.occupancy.refresh_from_db()
        self.encounter.refresh_from_db()
        self.assertEqual(self.occupancy.end_reason, BedOccupancy.EndReason.DISCHARGE)
        self.assertEqual(self.occupancy.ended_at, when)
        self.assertEqual(self.encounter.status, Encounter.Status.CLOSED)
        self.assertEqual(self.encounter.ended_at, when)
        self.assertEqual(discharge.final_occupancy, self.occupancy)
        self.assertFalse(
            BedOccupancy.objects.filter(
                admission=self.admission,
                ended_at__isnull=True,
            ).exists()
        )

    def test_discharge_is_idempotent_for_same_operation_key(self):
        self._grant("discharge_patient")
        operation_key = uuid.uuid4()
        first = discharge_patient(
            admission_id=self.admission.pk,
            disposition=Discharge.Disposition.HOME,
            actor=self.employee,
            operation_key=operation_key,
        )
        second = discharge_patient(
            admission_id=self.admission.pk,
            disposition=Discharge.Disposition.HOME,
            actor=self.employee,
            operation_key=operation_key,
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Discharge.objects.count(), 1)

    def test_discharge_requires_explicit_permission(self):
        with self.assertRaises(PermissionDenied):
            discharge_patient(
                admission_id=self.admission.pk,
                disposition=Discharge.Disposition.HOME,
                actor=self.employee,
                operation_key=uuid.uuid4(),
            )
        self.occupancy.refresh_from_db()
        self.assertIsNone(self.occupancy.ended_at)

    def test_discharge_rejects_time_before_current_occupancy(self):
        self._grant("discharge_patient")
        with self.assertRaises(DischargeStateError):
            discharge_patient(
                admission_id=self.admission.pk,
                disposition=Discharge.Disposition.HOME,
                actor=self.employee,
                operation_key=uuid.uuid4(),
                discharged_at=self.occupancy.started_at - timedelta(minutes=1),
            )

    def test_transfer_and_discharge_records_are_append_only(self):
        self._grant("transfer_patient")
        transfer = transfer_patient(
            admission_id=self.admission.pk,
            destination_bed_id=self.destination_bed.pk,
            actor=self.employee,
            operation_key=uuid.uuid4(),
        )
        transfer.reason = "Tentativa de edição"
        with self.assertRaises(ValidationError):
            transfer.save()
        with self.assertRaises(ValidationError):
            transfer.delete()

        self._grant("discharge_patient")
        discharge = discharge_patient(
            admission_id=self.admission.pk,
            disposition=Discharge.Disposition.HOME,
            actor=self.employee,
            operation_key=uuid.uuid4(),
        )
        discharge.reason = "Tentativa de edição"
        with self.assertRaises(ValidationError):
            discharge.save()
        with self.assertRaises(ValidationError):
            discharge.delete()

    def test_transfer_and_discharge_views_apply_capabilities(self):
        self.client.force_login(self.employee)
        self.assertEqual(self.client.get(reverse("adt:transfer_create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("adt:discharge_create")).status_code, 403)

        self._grant("transfer_patient")
        self.assertEqual(self.client.get(reverse("adt:transfer_create")).status_code, 200)
        self._grant("discharge_patient")
        self.assertEqual(self.client.get(reverse("adt:discharge_create")).status_code, 200)
