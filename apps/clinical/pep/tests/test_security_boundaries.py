from datetime import date, timedelta

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
class ClinicalSecurityBoundaryTests(TestCase):
    def setUp(self):
        self.admin = make_user("pep-boundary-admin", role="ADM")
        self.admin.is_superuser = True
        self.admin.is_staff = True
        self.admin.save(update_fields=["is_superuser", "is_staff"])
        self.owner = make_user("pep-boundary-owner", role="FUNC")
        self.other = make_user("pep-boundary-other", role="FUNC")
        self.client_user = make_user("pep-boundary-client", role="CLI")
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="BOUNDARY-MRN-001",
            full_name="Pessoa Sintética Boundary",
            birth_date=date(1990, 1, 10),
            created_by=self.owner,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            started_at=timezone.now() - timedelta(minutes=30),
            location="Unidade de teste",
            reason="Contexto sintético de autorização",
            responsible_professional=self.owner,
            created_by=self.owner,
        )
        self.evolution = ClinicalEvolution.objects.create(
            encounter=self.encounter,
            author=self.owner,
            content="Conteúdo sintético restrito usado apenas no teste.",
        )

    def test_expired_grant_denies_nested_clinical_resources(self):
        PatientAccessGrant.objects.create(
            patient=self.patient,
            user=self.other,
            reason="Acesso temporário expirado",
            granted_by=self.admin,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.client.force_login(self.other)

        encounter_response = self.client.get(
            reverse("pep:encounter_detail", args=[self.encounter.id])
        )
        evolution_response = self.client.get(
            reverse("pep:evolution_detail", args=[self.evolution.id])
        )
        amendment_response = self.client.post(
            reverse("pep:evolution_amendment_create", args=[self.evolution.id]),
            {
                "amendment_reason": "Tentativa fora do escopo",
                "content": "Este adendo não deve ser criado.",
            },
        )

        self.assertEqual(encounter_response.status_code, 404)
        self.assertEqual(evolution_response.status_code, 404)
        self.assertEqual(amendment_response.status_code, 404)
        self.assertNotContains(
            evolution_response,
            self.evolution.content,
            status_code=404,
        )
        self.assertEqual(ClinicalEvolution.objects.count(), 1)

    def test_client_role_cannot_create_patient(self):
        self.client.force_login(self.client_user)

        response = self.client.post(
            reverse("pep:patient_create"),
            {
                "identifier_type": Patient.IdentifierType.OTHER,
                "identifier": "BOUNDARY-CLIENT-001",
                "full_name": "Cadastro indevido",
                "birth_date": "1991-01-01",
                "sex": Patient.Sex.UNKNOWN,
                "phone": "",
                "email": "",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Patient.objects.filter(identifier="BOUNDARY-CLIENT-001").exists())

    def test_closed_encounter_blocks_new_evolution_and_amendment(self):
        self.encounter.status = Encounter.Status.CLOSED
        self.encounter.ended_at = timezone.now()
        self.encounter.save()
        self.client.force_login(self.owner)

        create_response = self.client.post(
            reverse("pep:evolution_create", args=[self.encounter.id]),
            {"content": "Novo registro indevido em encontro encerrado."},
        )
        amendment_response = self.client.post(
            reverse("pep:evolution_amendment_create", args=[self.evolution.id]),
            {
                "amendment_reason": "Tentativa após encerramento",
                "content": "Adendo indevido em encontro encerrado.",
            },
        )

        self.assertEqual(create_response.status_code, 403)
        self.assertEqual(amendment_response.status_code, 403)
        self.assertEqual(ClinicalEvolution.objects.count(), 1)
