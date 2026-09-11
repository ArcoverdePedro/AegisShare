from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from aegis_share.tests.helpers import make_user

from ..models import Patient, PatientAccessGrant


class PatientModelTests(TestCase):
    def setUp(self):
        self.user = make_user("pep-model-user", role="FUNC")

    def test_cpf_is_normalized_and_validated(self):
        patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.CPF,
            identifier="529.982.247-25",
            full_name="Paciente Teste",
            birth_date=date(1990, 1, 1),
            sex=Patient.Sex.UNKNOWN,
            created_by=self.user,
        )

        self.assertEqual(patient.identifier, "52998224725")

    def test_invalid_cpf_is_rejected(self):
        patient = Patient(
            identifier_type=Patient.IdentifierType.CPF,
            identifier="111.111.111-11",
            full_name="Paciente Inválido",
            birth_date=date(1990, 1, 1),
            created_by=self.user,
        )

        with self.assertRaises(ValidationError):
            patient.save()

    def test_future_birth_date_is_rejected(self):
        patient = Patient(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="HOSP-100",
            full_name="Paciente Futuro",
            birth_date=timezone.localdate() + timedelta(days=1),
            created_by=self.user,
        )

        with self.assertRaises(ValidationError):
            patient.save()

    def test_expired_access_grant_is_inactive(self):
        patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="HOSP-101",
            full_name="Paciente Acesso",
            birth_date=date(1985, 5, 1),
            created_by=self.user,
        )
        other = make_user("pep-grant-user", role="FUNC")
        grant = PatientAccessGrant.objects.create(
            patient=patient,
            user=other,
            reason="Cobertura assistencial",
            granted_by=self.user,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        self.assertFalse(grant.is_active)
