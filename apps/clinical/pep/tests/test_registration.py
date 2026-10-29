from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from aegis_share.tests.helpers import make_user

from ..models import Patient, PatientAccessGrant
from .test_views import TEST_STORAGES


@override_settings(STORAGES=TEST_STORAGES)
class PatientRegistrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        admin = make_user("reg-admin", role="ADM")
        admin.is_superuser = True
        admin.save(update_fields=["is_superuser"])
        cls.owner = make_user("reg-owner", role="FUNC")
        cls.other = make_user("reg-other", role="FUNC")
        cls.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="MRN-9",
            full_name="Ana Souza",
            birth_date=date(1990, 1, 2),
            created_by=cls.owner,
        )
        PatientAccessGrant.objects.create(
            patient=cls.patient, user=cls.owner, reason="Cadastro", granted_by=cls.owner
        )

    def data(self, **changes):
        return {
            "identifier_type": "OTHER",
            "identifier": "MRN-10",
            "full_name": "ana  souza",
            "birth_date": "1990-01-02",
            "sex": "U",
            **changes,
        }

    def test_cns_checksum(self):
        valid = Patient(
            identifier_type="CNS",
            identifier="700 0000 0000 0005",
            full_name="X",
            birth_date=date(2000, 1, 1),
            created_by=self.owner,
        )
        valid.full_clean()
        self.assertEqual(valid.identifier, "700000000000005")
        valid.identifier = "700000000000006"
        with self.assertRaises(ValidationError):
            valid.full_clean()

    def test_homonym_is_flagged_and_never_merged(self):
        self.client.force_login(self.owner)
        url = reverse("pep:patient_create")

        response = self.client.post(url, self.data())
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "MRN-9", status_code=409)
        self.assertEqual(Patient.objects.count(), 1)

        response = self.client.post(url, self.data(confirm_new="on"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Patient.objects.filter(full_name__iexact="Ana Souza").count(), 2)

    def test_duplicate_outside_scope_only_reveals_count(self):
        self.client.force_login(self.other)

        response = self.client.post(reverse("pep:patient_create"), self.data())

        self.assertContains(response, "1 cadastro(s)", status_code=409)
        self.assertNotContains(response, "MRN-9", status_code=409)

    def test_contact_update_keeps_identity_and_shows_social_name(self):
        self.client.force_login(self.owner)
        url = reverse("pep:patient_update", args=[self.patient.pk])

        response = self.client.post(
            url,
            {"social_name": " Ana  Lis ", "state": "pe", "city": "Recife", "identifier": "HACK"},
        )

        self.assertRedirects(response, reverse("pep:patient_detail", args=[self.patient.pk]))
        self.patient.refresh_from_db()
        self.assertEqual((self.patient.social_name, self.patient.state), ("Ana Lis", "PE"))
        self.assertEqual(self.patient.identifier, "MRN-9")
        detail = self.client.get(response.url)
        self.assertContains(detail, "Nome de registro: Ana Souza")
        self.assertContains(self.client.get(reverse("pep:patient_list") + "?q=Lis"), "Ana Lis")

        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
