from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from aegis_share.tests.helpers import make_user

from ..models import Encounter, Patient, PatientAccessGrant


TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES)
class EncounterTests(TestCase):
    def setUp(self):
        self.admin = make_user("enc-admin", role="ADM")
        self.admin.is_superuser = True
        self.admin.is_staff = True
        self.admin.save(update_fields=["is_superuser", "is_staff"])
        self.owner = make_user("enc-owner", role="FUNC")
        self.other = make_user("enc-other", role="FUNC")
        self.client_user = make_user("enc-client", role="CLI")
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="ENC-MRN-001",
            full_name="Paciente Encontro",
            birth_date=date(1987, 2, 10),
            created_by=self.owner,
        )

    def make_encounter(self, **overrides):
        values = {
            "patient": self.patient,
            "encounter_type": Encounter.Type.CONSULTATION,
            "status": Encounter.Status.OPEN,
            "started_at": timezone.now() - timedelta(minutes=30),
            "location": "Ambulatório 1",
            "reason": "Avaliação clínica inicial",
            "responsible_professional": self.owner,
            "created_by": self.owner,
        }
        values.update(overrides)
        return Encounter.objects.create(**values)

    def test_closed_encounter_requires_end_time(self):
        with self.assertRaises(ValidationError):
            self.make_encounter(status=Encounter.Status.CLOSED)

    def test_end_time_cannot_precede_start(self):
        started_at = timezone.now()
        with self.assertRaises(ValidationError):
            self.make_encounter(
                status=Encounter.Status.CLOSED,
                started_at=started_at,
                ended_at=started_at - timedelta(minutes=1),
            )

    def test_employee_with_patient_access_can_create_encounter(self):
        self.client.force_login(self.owner)
        started_at = timezone.localtime().replace(second=0, microsecond=0)

        response = self.client.post(
            reverse("pep:encounter_create", args=[self.patient.id]),
            {
                "encounter_type": Encounter.Type.CONSULTATION,
                "started_at": started_at.strftime("%Y-%m-%dT%H:%M"),
                "location": "Consultório 2",
                "reason": "Retorno programado",
            },
        )

        self.assertEqual(response.status_code, 302)
        encounter = Encounter.objects.get(patient=self.patient)
        self.assertEqual(encounter.status, Encounter.Status.OPEN)
        self.assertEqual(encounter.responsible_professional, self.owner)
        self.assertEqual(encounter.created_by, self.owner)
        self.assertEqual(
            response.url,
            reverse("pep:encounter_detail", args=[encounter.id]),
        )

    def test_unrelated_employee_cannot_create_encounter(self):
        self.client.force_login(self.other)
        started_at = timezone.localtime().replace(second=0, microsecond=0)

        response = self.client.post(
            reverse("pep:encounter_create", args=[self.patient.id]),
            {
                "encounter_type": Encounter.Type.CONSULTATION,
                "started_at": started_at.strftime("%Y-%m-%dT%H:%M"),
                "location": "Consultório 2",
                "reason": "Tentativa fora de escopo",
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Encounter.objects.exists())

    def test_unrelated_employee_cannot_view_encounter(self):
        encounter = self.make_encounter()
        self.client.force_login(self.other)

        response = self.client.get(reverse("pep:encounter_detail", args=[encounter.id]))

        self.assertEqual(response.status_code, 404)
        self.assertNotContains(
            response,
            "Avaliação clínica inicial",
            status_code=404,
        )

    def test_granted_employee_can_list_and_view_encounter(self):
        encounter = self.make_encounter()
        PatientAccessGrant.objects.create(
            patient=self.patient,
            user=self.other,
            reason="Equipe assistencial",
            granted_by=self.admin,
        )
        self.client.force_login(self.other)

        list_response = self.client.get(
            reverse("pep:encounter_list", args=[self.patient.id])
        )
        detail_response = self.client.get(
            reverse("pep:encounter_detail", args=[encounter.id])
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "Consulta")
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Avaliação clínica inicial")

    def test_client_role_cannot_access_encounter(self):
        encounter = self.make_encounter()
        self.client.force_login(self.client_user)

        response = self.client.get(reverse("pep:encounter_detail", args=[encounter.id]))

        self.assertEqual(response.status_code, 404)

    def test_patient_record_shows_recent_encounters(self):
        encounter = self.make_encounter()
        self.client.force_login(self.owner)

        response = self.client.get(reverse("pep:patient_detail", args=[self.patient.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, encounter.get_encounter_type_display())
        self.assertContains(response, "Ambulatório 1")
