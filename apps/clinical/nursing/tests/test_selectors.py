from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.clinical.pep.models import Encounter, Patient

from ..models import VitalSignsRecord
from ..selectors import latest_weight_fact


class WeightFactSelectorTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.nurse = user_model.objects.create_user(
            username="nursing-weight-selector",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="NUR-WEIGHT-1",
            full_name="Paciente Peso Sintético",
            birth_date=date(1990, 1, 1),
            created_by=self.nurse,
        )
        self.first_encounter = Encounter.objects.create(
            patient=self.patient,
            started_at=timezone.now() - timedelta(days=3),
            responsible_professional=self.nurse,
            created_by=self.nurse,
        )
        self.second_encounter = Encounter.objects.create(
            patient=self.patient,
            started_at=timezone.now() - timedelta(hours=2),
            responsible_professional=self.nurse,
            created_by=self.nurse,
        )

    def _record(self, *, encounter=None, recorded_at=None, weight_kg=None, origin=None, **values):
        return VitalSignsRecord.objects.create(
            encounter=encounter or self.first_encounter,
            recorded_by=self.nurse,
            recorded_at=recorded_at or timezone.now() - timedelta(minutes=5),
            weight_kg=weight_kg,
            origin=origin or VitalSignsRecord.Origin.ONLINE,
            **values,
        )

    def test_requires_exactly_one_scope(self):
        with self.assertRaises(ValueError):
            latest_weight_fact()

        with self.assertRaises(ValueError):
            latest_weight_fact(encounter=self.first_encounter, patient=self.patient)

    def test_encounter_scope_returns_latest_weight_not_latest_unrelated_vitals(self):
        older_weight = self._record(
            recorded_at=timezone.now() - timedelta(minutes=20),
            weight_kg=Decimal("72.350"),
        )
        self._record(
            recorded_at=timezone.now() - timedelta(minutes=1),
            temperature_c=Decimal("36.70"),
        )

        fact = latest_weight_fact(encounter=self.first_encounter)

        self.assertEqual(fact["weight_kg"], Decimal("72.350"))
        self.assertEqual(fact["record_id"], older_weight.pk)
        self.assertEqual(fact["recorded_by_id"], self.nurse.pk)
        self.assertEqual(fact["encounter_id"], self.first_encounter.pk)
        self.assertEqual(fact["origin"], VitalSignsRecord.Origin.ONLINE)

    def test_patient_scope_returns_latest_weight_across_encounters(self):
        self._record(
            encounter=self.first_encounter,
            recorded_at=timezone.now() - timedelta(days=2),
            weight_kg=Decimal("70.000"),
        )
        latest = self._record(
            encounter=self.second_encounter,
            recorded_at=timezone.now() - timedelta(minutes=10),
            weight_kg=Decimal("71.125"),
            origin=VitalSignsRecord.Origin.OFFLINE_SYNC,
        )

        fact = latest_weight_fact(patient=self.patient)

        self.assertEqual(fact["weight_kg"], Decimal("71.125"))
        self.assertEqual(fact["record_id"], latest.pk)
        self.assertEqual(fact["recorded_at"], latest.recorded_at)
        self.assertEqual(fact["encounter_id"], self.second_encounter.pk)
        self.assertEqual(fact["origin"], VitalSignsRecord.Origin.OFFLINE_SYNC)

    def test_selector_does_not_apply_freshness_or_origin_policy(self):
        old_offline = self._record(
            recorded_at=timezone.now() - timedelta(days=120),
            weight_kg=Decimal("68.400"),
            origin=VitalSignsRecord.Origin.OFFLINE_SYNC,
        )

        fact = latest_weight_fact(encounter=self.first_encounter)

        self.assertEqual(fact["record_id"], old_offline.pk)
        self.assertEqual(fact["weight_kg"], Decimal("68.400"))
        self.assertEqual(fact["origin"], VitalSignsRecord.Origin.OFFLINE_SYNC)

    def test_returns_none_when_scope_has_no_weight_fact(self):
        self._record(temperature_c=Decimal("36.50"))

        self.assertIsNone(latest_weight_fact(encounter=self.first_encounter))
