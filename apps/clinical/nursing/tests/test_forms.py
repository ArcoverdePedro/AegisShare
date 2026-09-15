from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.clinical.pep.models import Encounter, Patient

from ..forms import VitalSignsRecordForm


class VitalSignsRecordFormTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="nursing-form-user",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="NUR-FORM-1",
            full_name="Paciente Formulário",
            birth_date=date(1991, 4, 12),
            created_by=self.user,
        )
        self.started_at = timezone.now() - timedelta(hours=1)
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            started_at=self.started_at,
            responsible_professional=self.user,
            created_by=self.user,
        )

    def _recorded_at(self, value):
        return timezone.localtime(value).strftime("%Y-%m-%dT%H:%M:%S")

    def test_accepts_at_least_one_structured_measure(self):
        form = VitalSignsRecordForm(
            data={
                "recorded_at": self._recorded_at(timezone.now() - timedelta(minutes=1)),
                "heart_rate_bpm": "72",
            },
            encounter=self.encounter,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_requires_at_least_one_measure(self):
        form = VitalSignsRecordForm(
            data={
                "recorded_at": self._recorded_at(timezone.now() - timedelta(minutes=1)),
            },
            encounter=self.encounter,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Informe ao menos uma medida clínica.", form.non_field_errors())

    def test_rejects_future_recorded_at(self):
        form = VitalSignsRecordForm(
            data={
                "recorded_at": self._recorded_at(timezone.now() + timedelta(minutes=5)),
                "temperature_c": "36.50",
            },
            encounter=self.encounter,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("recorded_at", form.errors)

    def test_rejects_measure_before_encounter_start(self):
        form = VitalSignsRecordForm(
            data={
                "recorded_at": self._recorded_at(self.started_at - timedelta(seconds=1)),
                "weight_kg": "70.000",
            },
            encounter=self.encounter,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("recorded_at", form.errors)
