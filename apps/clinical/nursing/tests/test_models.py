import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.clinical.pep.models import Encounter, Patient

from ..models import MedicationAdministration, VitalSignsRecord


class VitalSignsRecordModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="nurse-model",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="NUR-MODEL-1",
            full_name="Paciente Teste",
            birth_date=date(1990, 1, 1),
            created_by=self.user,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            responsible_professional=self.user,
            created_by=self.user,
        )

    def _record(self, **overrides):
        values = {
            "encounter": self.encounter,
            "recorded_by": self.user,
            "recorded_at": timezone.now(),
            "heart_rate_bpm": 72,
        }
        values.update(overrides)
        return VitalSignsRecord.objects.create(**values)

    def test_requires_at_least_one_measure(self):
        record = VitalSignsRecord(
            encounter=self.encounter,
            recorded_by=self.user,
            recorded_at=timezone.now(),
        )

        with self.assertRaises(ValidationError):
            record.full_clean()

    def test_rejects_invalid_numeric_domain(self):
        record = VitalSignsRecord(
            encounter=self.encounter,
            recorded_by=self.user,
            recorded_at=timezone.now(),
            oxygen_saturation_pct=Decimal("101"),
            weight_kg=Decimal("-1"),
        )

        with self.assertRaises(ValidationError) as exc:
            record.full_clean()

        self.assertIn("oxygen_saturation_pct", exc.exception.message_dict)
        self.assertIn("weight_kg", exc.exception.message_dict)

    def test_replacement_must_share_encounter(self):
        original = self._record()
        other_encounter = Encounter.objects.create(
            patient=self.patient,
            responsible_professional=self.user,
            created_by=self.user,
        )
        correction = VitalSignsRecord(
            encounter=other_encounter,
            recorded_by=self.user,
            recorded_at=timezone.now(),
            heart_rate_bpm=75,
            replaces=original,
        )

        with self.assertRaises(ValidationError) as exc:
            correction.full_clean()

        self.assertIn("replaces", exc.exception.message_dict)

    def test_confirmed_record_is_append_only(self):
        record = self._record()
        record.heart_rate_bpm = 80

        with self.assertRaisesMessage(ValidationError, "append-only"):
            record.save()

        with self.assertRaisesMessage(ValidationError, "não podem ser excluídos"):
            record.delete()

    def test_idempotency_key_is_unique(self):
        operation_key = uuid.uuid4()
        self._record(idempotency_key=operation_key)

        with self.assertRaises(ValidationError):
            self._record(idempotency_key=operation_key)


class MedicationAdministrationModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="nurse-admin-model",
            password="test-password",
            nivel_permissao="FUNC",
        )

    def test_requires_positive_dose_and_explicit_unit(self):
        administration = MedicationAdministration(
            dispense_item_id=uuid.uuid4(),
            administered_by=self.user,
            administered_at=timezone.now(),
            administered_dose=Decimal("0"),
            administered_dose_unit="",
        )

        with self.assertRaises(ValidationError) as exc:
            administration.clean()

        self.assertIn("administered_dose", exc.exception.message_dict)
        self.assertIn("administered_dose_unit", exc.exception.message_dict)

    def test_normalizes_explicit_unit_without_converting_it(self):
        administration = MedicationAdministration(
            dispense_item_id=uuid.uuid4(),
            administered_by=self.user,
            administered_at=timezone.now(),
            administered_dose=Decimal("1.5"),
            administered_dose_unit="  mg   por   mL ",
        )

        administration.clean()

        self.assertEqual(administration.administered_dose, Decimal("1.5"))
        self.assertEqual(administration.administered_dose_unit, "mg por mL")
