import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.clinical.pep.models import Encounter, Patient, PatientAccessGrant

from ..models import Admission, Bed, BedOccupancy, Discharge, Location, Transfer, UserLocationAccess

User = get_user_model()

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES)
class AdtLifecycleViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="adt-lifecycle-view-admin",
            password="test-password",
            nivel_permissao="ADM",
        )
        self.employee = User.objects.create_user(
            username="adt-lifecycle-view-employee",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="ADT-LIFECYCLE-VIEW",
            full_name="Paciente View Lifecycle",
            birth_date=timezone.localdate() - timedelta(days=365 * 30),
            created_by=self.admin,
        )
        PatientAccessGrant.objects.create(
            patient=self.patient,
            user=self.employee,
            granted_by=self.admin,
            reason="Operação ADT",
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.INPATIENT,
            status=Encounter.Status.OPEN,
            started_at=timezone.now() - timedelta(hours=3),
            responsible_professional=self.admin,
            created_by=self.admin,
        )
        self.location = Location.objects.create(code="VIEW-A", name="View A")
        self.destination_location = Location.objects.create(code="VIEW-B", name="View B")
        self.source_bed = Bed.objects.create(
            location=self.location,
            code="01",
            label="Leito 01",
        )
        self.destination_bed = Bed.objects.create(
            location=self.destination_location,
            code="02",
            label="Leito 02",
        )
        for location in (self.location, self.destination_location):
            UserLocationAccess.objects.create(
                user=self.employee,
                location=location,
                granted_by=self.admin,
            )
        admitted_at = timezone.now() - timedelta(hours=2)
        self.admission = Admission.objects.create(
            encounter=self.encounter,
            admitted_at=admitted_at,
            admitted_by=self.admin,
        )
        BedOccupancy.objects.create(
            admission=self.admission,
            bed=self.source_bed,
            started_at=admitted_at,
            started_by=self.admin,
        )
        self.client.force_login(self.employee)

    def _grant(self, codename):
        permission = Permission.objects.get(
            codename=codename,
            content_type__app_label="adt",
        )
        self.employee.user_permissions.add(permission)
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            if hasattr(self.employee, cache_name):
                delattr(self.employee, cache_name)

    def test_transfer_post_moves_patient_to_destination(self):
        self._grant("transfer_patient")
        response = self.client.post(
            reverse("adt:transfer_create"),
            {
                "admission": str(self.admission.pk),
                "destination_bed": str(self.destination_bed.pk),
                "transferred_at": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
                "reason": "Mudança de setor",
                "operation_key": str(uuid.uuid4()),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Transfer.objects.count(), 1)
        active = BedOccupancy.objects.get(
            admission=self.admission,
            ended_at__isnull=True,
        )
        self.assertEqual(active.bed, self.destination_bed)

    def test_discharge_post_releases_bed_and_closes_encounter(self):
        self._grant("discharge_patient")
        response = self.client.post(
            reverse("adt:discharge_create"),
            {
                "admission": str(self.admission.pk),
                "discharged_at": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
                "disposition": Discharge.Disposition.HOME,
                "reason": "Alta para domicílio",
                "operation_key": str(uuid.uuid4()),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Discharge.objects.count(), 1)
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.status, Encounter.Status.CLOSED)
        self.assertFalse(
            BedOccupancy.objects.filter(
                admission=self.admission,
                ended_at__isnull=True,
            ).exists()
        )
