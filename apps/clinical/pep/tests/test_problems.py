from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import Patient, ProblemListEntry
from . import test_registration
from .test_views import TEST_STORAGES


@override_settings(STORAGES=TEST_STORAGES)
class ProblemListTests(TestCase):
    setUpTestData = classmethod(test_registration.PatientRegistrationTests.setUpTestData.__func__)

    def test_revision_keeps_previous_version_and_code_needs_provenance(self):
        self.client.force_login(self.owner)
        url = reverse("pep:problem_list", args=[self.patient.pk])

        response = self.client.post(
            url, {"description": "Hipertensão", "status": "ACTIVE", "code": "I10"}
        )
        self.assertEqual(response.status_code, 200)  # código sem sistema/versão
        self.client.post(url, {"description": "Hipertensão", "status": "ACTIVE"})
        first = ProblemListEntry.objects.get()

        self.client.post(
            url, {"revisar": first.pk, "description": "Hipertensão", "status": "RESOLVED"}
        )
        self.assertEqual(ProblemListEntry.objects.count(), 1)  # revisão exige motivo
        self.client.post(
            url,
            {
                "revisar": first.pk,
                "description": "Hipertensão",
                "status": "RESOLVED",
                "reason": "Controle",
            },
        )
        current = ProblemListEntry.objects.get(superseded_by__isnull=True)
        self.assertEqual((current.supersedes, current.status), (first, "RESOLVED"))
        response = self.client.get(url)
        self.assertContains(response, "Versões anteriores (1)")
        with self.assertRaises(ValidationError):
            first.delete()

    def test_out_of_scope_and_client_cannot_access(self):
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.get(reverse("pep:problem_list", args=[self.patient.pk])).status_code, 404
        )
        stranger = Patient.objects.create(
            identifier_type="OTHER",
            identifier="P-X",
            full_name="Outro",
            birth_date="1990-01-01",
            created_by=self.other,
        )
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.get(reverse("pep:problem_list", args=[stranger.pk])).status_code, 404
        )
