from datetime import date, timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from aegis_share.tests.helpers import make_user

from ..models import Patient, PatientAccessGrant


TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES)
class PatientViewTests(TestCase):
    def setUp(self):
        self.admin = make_user("pep-admin", role="ADM")
        self.admin.is_superuser = True
        self.admin.is_staff = True
        self.admin.save(update_fields=["is_superuser", "is_staff"])
        self.owner = make_user("pep-owner", role="FUNC")
        self.other = make_user("pep-other", role="FUNC")
        self.client_user = make_user("pep-client", role="CLI")
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="MRN-001",
            full_name="Maria da Silva",
            birth_date=date(1980, 4, 12),
            created_by=self.owner,
        )

    def test_admin_can_list_all_patients(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("pep:patient_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Maria da Silva")

    def test_employee_only_lists_patients_in_scope(self):
        self.client.force_login(self.other)

        response = self.client.get(reverse("pep:patient_list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Maria da Silva")

        PatientAccessGrant.objects.create(
            patient=self.patient,
            user=self.other,
            reason="Equipe assistencial",
            granted_by=self.admin,
        )
        response = self.client.get(reverse("pep:patient_list"))
        self.assertContains(response, "Maria da Silva")

    def test_expired_grant_does_not_expose_patient(self):
        PatientAccessGrant.objects.create(
            patient=self.patient,
            user=self.other,
            reason="Cobertura temporária",
            granted_by=self.admin,
            expires_at=timezone.now() - timedelta(minutes=5),
        )
        self.client.force_login(self.other)

        response = self.client.get(reverse("pep:patient_detail", args=[self.patient.id]))

        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "Maria da Silva", status_code=404)

    def test_client_role_is_denied_pep_listing(self):
        self.client.force_login(self.client_user)

        response = self.client.get(reverse("pep:patient_list"))

        self.assertEqual(response.status_code, 403)

    def test_employee_can_create_patient_and_receives_access_grant(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("pep:patient_create"),
            {
                "identifier_type": Patient.IdentifierType.OTHER,
                "identifier": "MRN-002",
                "full_name": "João de Souza",
                "birth_date": "1975-06-20",
                "sex": Patient.Sex.MALE,
                "phone": "",
                "email": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        created = Patient.objects.get(identifier="MRN-002")
        self.assertEqual(created.created_by, self.owner)
        self.assertTrue(
            PatientAccessGrant.objects.filter(patient=created, user=self.owner).exists()
        )

    def test_duplicate_identifier_returns_form_error(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("pep:patient_create"),
            {
                "identifier_type": Patient.IdentifierType.OTHER,
                "identifier": "MRN-001",
                "full_name": "Outra Pessoa",
                "birth_date": "1988-01-01",
                "sex": Patient.Sex.UNKNOWN,
                "phone": "",
                "email": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "já existe")
        self.assertEqual(Patient.objects.filter(identifier="MRN-001").count(), 1)
