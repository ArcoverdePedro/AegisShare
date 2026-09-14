import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from apps.clinical.pep.models import Encounter, Patient, PatientAccessGrant

from ..models import Admission, Bed, BedOccupancy, Location, UserLocationAccess
from ..services import BedUnavailableError, admit_patient

User = get_user_model()


class AdmissionServiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="adt-service-admin",
            password="test-password",
            nivel_permissao="ADM",
        )
        self.employee = User.objects.create_user(
            username="adt-service-employee",
            password="test-password",
            nivel_permissao="FUNC",
        )
        admit_permission = Permission.objects.get(
            codename="admit_patient",
            content_type__app_label="adt",
        )
        self.employee.user_permissions.add(admit_permission)
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="ADT-SERVICE-PATIENT",
            full_name="Paciente Serviço ADT",
            birth_date=timezone.localdate() - timedelta(days=365 * 35),
            created_by=self.admin,
        )
        PatientAccessGrant.objects.create(
            patient=self.patient,
            user=self.employee,
            granted_by=self.admin,
            reason="Atuação na admissão",
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.INPATIENT,
            status=Encounter.Status.OPEN,
            started_at=timezone.now() - timedelta(hours=2),
            responsible_professional=self.employee,
            created_by=self.employee,
        )
        self.location = Location.objects.create(
            code="ADM-01",
            name="Unidade de Admissão",
            kind=Location.Kind.UNIT,
        )
        UserLocationAccess.objects.create(
            user=self.employee,
            location=self.location,
            granted_by=self.admin,
        )
        self.bed = Bed.objects.create(
            location=self.location,
            code="A-01",
            label="Leito A-01",
        )

    def _refresh_permission_cache(self):
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            if hasattr(self.employee, cache_name):
                delattr(self.employee, cache_name)

    def test_admission_creates_first_occupancy_atomically(self):
        self._refresh_permission_cache()
        operation_key = uuid.uuid4()
        admission = admit_patient(
            encounter_id=self.encounter.pk,
            bed_id=self.bed.pk,
            actor=self.employee,
            operation_key=operation_key,
        )
        occupancy = BedOccupancy.objects.get(admission=admission)
        self.assertEqual(admission.operation_key, operation_key)
        self.assertEqual(occupancy.bed_id, self.bed.pk)
        self.assertIsNone(occupancy.ended_at)

    def test_repeating_operation_key_returns_same_admission(self):
        self._refresh_permission_cache()
        operation_key = uuid.uuid4()
        first = admit_patient(
            encounter_id=self.encounter.pk,
            bed_id=self.bed.pk,
            actor=self.employee,
            operation_key=operation_key,
        )
        second = admit_patient(
            encounter_id=self.encounter.pk,
            bed_id=self.bed.pk,
            actor=self.employee,
            operation_key=operation_key,
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Admission.objects.count(), 1)
        self.assertEqual(BedOccupancy.objects.count(), 1)

    def test_employee_without_location_scope_is_denied(self):
        UserLocationAccess.objects.filter(user=self.employee).delete()
        self._refresh_permission_cache()
        with self.assertRaises(PermissionDenied):
            admit_patient(
                encounter_id=self.encounter.pk,
                bed_id=self.bed.pk,
                actor=self.employee,
                operation_key=uuid.uuid4(),
            )
        self.assertFalse(Admission.objects.exists())

    def test_blocked_bed_is_rejected_without_partial_admission(self):
        self.bed.operational_status = Bed.OperationalStatus.BLOCKED
        self.bed.save()
        self._refresh_permission_cache()
        with self.assertRaises(BedUnavailableError):
            admit_patient(
                encounter_id=self.encounter.pk,
                bed_id=self.bed.pk,
                actor=self.employee,
                operation_key=uuid.uuid4(),
            )
        self.assertFalse(Admission.objects.exists())
        self.assertFalse(BedOccupancy.objects.exists())
