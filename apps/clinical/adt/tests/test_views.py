import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.clinical.pep.models import Encounter, Patient, PatientAccessGrant

from ..models import Bed, BedOccupancy, Location, UserLocationAccess

User = get_user_model()

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES)
class AdtViewTests(TestCase):
    def setUp(self):
        # FirstAccessRedirectMiddleware considera a instalação configurada apenas
        # quando existe um superusuário. Este ator também serve como administrador
        # técnico dos dados de teste, enquanto as autorizações exercitadas abaixo
        # permanecem concentradas no usuário FUNC.
        self.admin = User.objects.create_superuser(
            username="adt-view-admin",
            password="test-password",
            nivel_permissao="ADM",
        )
        self.employee = User.objects.create_user(
            username="adt-view-employee",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="ADT-VIEW-PATIENT",
            full_name="Paciente Restrito ADT",
            birth_date=timezone.localdate() - timedelta(days=365 * 40),
            created_by=self.admin,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.INPATIENT,
            status=Encounter.Status.OPEN,
            started_at=timezone.now() - timedelta(hours=1),
            responsible_professional=self.admin,
            created_by=self.admin,
        )
        self.location = Location.objects.create(
            code="WARD-01",
            name="Setor 01",
            kind=Location.Kind.WARD,
        )
        self.bed = Bed.objects.create(
            location=self.location,
            code="01",
            label="Leito 01",
        )
        UserLocationAccess.objects.create(
            user=self.employee,
            location=self.location,
            granted_by=self.admin,
        )

    def _grant_permission(self, codename):
        permission = Permission.objects.get(
            codename=codename,
            content_type__app_label="adt",
        )
        self.employee.user_permissions.add(permission)
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            if hasattr(self.employee, cache_name):
                delattr(self.employee, cache_name)

    def test_bed_map_hides_patient_phi_without_pep_scope(self):
        self._grant_permission("view_bed_map")
        admission = self.encounter.adt_admission if hasattr(self.encounter, "adt_admission") else None
        if admission is None:
            from ..models import Admission

            admission = Admission.objects.create(
                encounter=self.encounter,
                admitted_at=timezone.now(),
                admitted_by=self.admin,
            )
        BedOccupancy.objects.create(
            admission=admission,
            bed=self.bed,
            started_at=admission.admitted_at,
            started_by=self.admin,
        )
        self.client.force_login(self.employee)
        response = self.client.get(reverse("adt:bed_map"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Identificação do ocupante restrita")
        self.assertNotContains(response, self.patient.full_name)
        self.assertNotContains(response, self.patient.identifier)
        self.assertEqual(response["Cache-Control"], "private, no-store, max-age=0")

    def test_bed_map_shows_name_after_pep_grant(self):
        self._grant_permission("view_bed_map")
        PatientAccessGrant.objects.create(
            patient=self.patient,
            user=self.employee,
            granted_by=self.admin,
            reason="Cuidado assistencial",
        )
        from ..models import Admission

        admission = Admission.objects.create(
            encounter=self.encounter,
            admitted_at=timezone.now(),
            admitted_by=self.admin,
        )
        BedOccupancy.objects.create(
            admission=admission,
            bed=self.bed,
            started_at=admission.admitted_at,
            started_by=self.admin,
        )
        self.client.force_login(self.employee)
        response = self.client.get(reverse("adt:bed_map"))
        self.assertContains(response, self.patient.full_name)

    def test_admission_post_creates_admission_and_occupancy(self):
        self._grant_permission("admit_patient")
        PatientAccessGrant.objects.create(
            patient=self.patient,
            user=self.employee,
            granted_by=self.admin,
            reason="Admissão",
        )
        self.client.force_login(self.employee)
        response = self.client.post(
            reverse("adt:admission_create"),
            {
                "encounter": str(self.encounter.pk),
                "bed": str(self.bed.pk),
                "admitted_at": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
                "operation_key": str(uuid.uuid4()),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            BedOccupancy.objects.filter(
                bed=self.bed,
                ended_at__isnull=True,
            ).exists()
        )

    def test_employee_without_bed_map_permission_gets_403(self):
        self.client.force_login(self.employee)
        response = self.client.get(reverse("adt:bed_map"))
        self.assertEqual(response.status_code, 403)
