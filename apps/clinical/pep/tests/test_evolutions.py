from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from aegis_share.tests.helpers import make_user

from ..models import ClinicalEvolution, Encounter, Patient, PatientAccessGrant


TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES)
class ClinicalEvolutionTests(TestCase):
    def setUp(self):
        self.admin = make_user("evo-admin", role="ADM")
        self.admin.is_superuser = True
        self.admin.is_staff = True
        self.admin.save(update_fields=["is_superuser", "is_staff"])
        self.owner = make_user("evo-owner", role="FUNC")
        self.other = make_user("evo-other", role="FUNC")
        self.client_user = make_user("evo-client", role="CLI")
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="EVO-MRN-001",
            full_name="Paciente Evolução",
            birth_date=date(1989, 7, 4),
            created_by=self.owner,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            started_at=timezone.now() - timedelta(minutes=20),
            location="Ambulatório",
            reason="Acompanhamento",
            responsible_professional=self.owner,
            created_by=self.owner,
        )

    def make_evolution(self, **overrides):
        values = {
            "encounter": self.encounter,
            "author": self.owner,
            "content": "Paciente avaliado, estável e orientado.",
        }
        values.update(overrides)
        return ClinicalEvolution.objects.create(**values)

    def test_saved_evolution_cannot_be_changed(self):
        evolution = self.make_evolution()
        original_content = evolution.content
        evolution.content = "Tentativa de alteração do registro original."

        with self.assertRaises(ValidationError):
            evolution.save()

        evolution.refresh_from_db()
        self.assertEqual(evolution.content, original_content)

    def test_saved_evolution_cannot_be_deleted(self):
        evolution = self.make_evolution()

        with self.assertRaises(ValidationError):
            evolution.delete()

        self.assertTrue(ClinicalEvolution.objects.filter(pk=evolution.pk).exists())

    def test_evolution_requires_open_encounter(self):
        self.encounter.status = Encounter.Status.CLOSED
        self.encounter.ended_at = timezone.now()
        self.encounter.save()

        with self.assertRaises(ValidationError):
            self.make_evolution()

    def test_employee_with_patient_access_can_create_evolution(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("pep:evolution_create", args=[self.encounter.id]),
            {"content": "Evolução registrada pelo profissional responsável."},
        )

        self.assertEqual(response.status_code, 302)
        evolution = ClinicalEvolution.objects.get(encounter=self.encounter)
        self.assertEqual(evolution.author, self.owner)
        self.assertEqual(
            response.url,
            reverse("pep:evolution_detail", args=[evolution.id]),
        )

    def test_unrelated_employee_cannot_create_or_view_evolution(self):
        evolution = self.make_evolution()
        self.client.force_login(self.other)

        create_response = self.client.post(
            reverse("pep:evolution_create", args=[self.encounter.id]),
            {"content": "Tentativa fora do escopo."},
        )
        detail_response = self.client.get(
            reverse("pep:evolution_detail", args=[evolution.id])
        )

        self.assertEqual(create_response.status_code, 404)
        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(ClinicalEvolution.objects.count(), 1)

    def test_granted_employee_can_create_evolution(self):
        PatientAccessGrant.objects.create(
            patient=self.patient,
            user=self.other,
            reason="Equipe assistencial",
            granted_by=self.admin,
        )
        self.client.force_login(self.other)

        response = self.client.post(
            reverse("pep:evolution_create", args=[self.encounter.id]),
            {"content": "Registro feito por membro autorizado da equipe."},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ClinicalEvolution.objects.filter(
                encounter=self.encounter,
                author=self.other,
            ).exists()
        )

    def test_client_role_cannot_view_evolution(self):
        evolution = self.make_evolution()
        self.client.force_login(self.client_user)

        response = self.client.get(reverse("pep:evolution_detail", args=[evolution.id]))

        self.assertEqual(response.status_code, 404)

    def test_amendment_creates_new_record_and_preserves_original(self):
        original = self.make_evolution()
        original_content = original.content
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("pep:evolution_amendment_create", args=[original.id]),
            {
                "amendment_reason": "Complementação de informação clínica",
                "content": "Adendo: paciente também relatou melhora da dor.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ClinicalEvolution.objects.count(), 2)
        amendment = ClinicalEvolution.objects.exclude(pk=original.pk).get()
        self.assertEqual(amendment.amendment_of, original)
        self.assertEqual(amendment.author, self.owner)
        original.refresh_from_db()
        self.assertEqual(original.content, original_content)

    def test_amendment_requires_reason(self):
        original = self.make_evolution()

        with self.assertRaises(ValidationError):
            ClinicalEvolution.objects.create(
                encounter=self.encounter,
                author=self.owner,
                amendment_of=original,
                content="Adendo sem justificativa.",
            )

    def test_amendment_cannot_reference_another_encounter(self):
        original = self.make_evolution()
        another_encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            started_at=timezone.now(),
            responsible_professional=self.owner,
            created_by=self.owner,
        )

        with self.assertRaises(ValidationError):
            ClinicalEvolution.objects.create(
                encounter=another_encounter,
                author=self.owner,
                amendment_of=original,
                amendment_reason="Correção",
                content="Adendo incorretamente associado a outro encontro.",
            )

    def test_encounter_detail_shows_evolution_history(self):
        evolution = self.make_evolution()
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("pep:encounter_detail", args=[self.encounter.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, evolution.content)
        self.assertContains(response, "Nova evolução")
