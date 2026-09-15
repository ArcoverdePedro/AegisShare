import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from apps.clinical.pep.models import Encounter, Patient, PatientAccessGrant

from ..models import VitalSignsRecord
from ..services import VitalSignsIdempotencyConflictError, record_vital_signs


class VitalSignsIdempotencyServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.nurse = user_model.objects.create_user(
            username="nursing-idempotency-user",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.other_nurse = user_model.objects.create_user(
            username="nursing-idempotency-other",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.record_permission = Permission.objects.get(
            content_type__app_label="nursing",
            codename="record_vitals",
        )
        self.nurse.user_permissions.add(self.record_permission)
        self.other_nurse.user_permissions.add(self.record_permission)

        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="NUR-IDEMP-1",
            full_name="Paciente Idempotência",
            birth_date=date(1984, 6, 1),
            created_by=self.nurse,
        )
        PatientAccessGrant.objects.create(
            patient=self.patient,
            user=self.other_nurse,
            reason="Teste de colisão idempotente entre atores",
            granted_by=self.nurse,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            started_at=timezone.now() - timedelta(hours=1),
            responsible_professional=self.nurse,
            created_by=self.nurse,
        )
        self.recorded_at = timezone.now().replace(microsecond=0) - timedelta(minutes=1)
        self.data = {
            "recorded_at": self.recorded_at,
            "temperature_c": Decimal("36.50"),
            "heart_rate_bpm": 72,
            "respiratory_rate_irpm": None,
            "systolic_bp_mmhg": None,
            "diastolic_bp_mmhg": None,
            "oxygen_saturation_pct": Decimal("98.00"),
            "weight_kg": Decimal("70.125"),
        }

    def test_retry_with_same_key_and_payload_returns_existing_record(self):
        key = uuid.uuid4()

        first = record_vital_signs(
            encounter=self.encounter,
            actor=self.nurse,
            data=self.data,
            idempotency_key=key,
        )
        second = record_vital_signs(
            encounter=self.encounter,
            actor=self.nurse,
            data=self.data,
            idempotency_key=key,
        )

        self.assertEqual(second.pk, first.pk)
        self.assertEqual(VitalSignsRecord.objects.count(), 1)

    def test_same_key_with_different_payload_is_safe_conflict(self):
        key = uuid.uuid4()
        record_vital_signs(
            encounter=self.encounter,
            actor=self.nurse,
            data=self.data,
            idempotency_key=key,
        )
        changed_data = {**self.data, "heart_rate_bpm": 73}

        with self.assertRaises(VitalSignsIdempotencyConflictError):
            record_vital_signs(
                encounter=self.encounter,
                actor=self.nurse,
                data=changed_data,
                idempotency_key=key,
            )

        self.assertEqual(VitalSignsRecord.objects.count(), 1)
        self.assertEqual(VitalSignsRecord.objects.get().heart_rate_bpm, 72)

    def test_same_key_with_different_actor_is_safe_conflict(self):
        key = uuid.uuid4()
        record_vital_signs(
            encounter=self.encounter,
            actor=self.nurse,
            data=self.data,
            idempotency_key=key,
        )

        with self.assertRaises(VitalSignsIdempotencyConflictError):
            record_vital_signs(
                encounter=self.encounter,
                actor=self.other_nurse,
                data=self.data,
                idempotency_key=key,
            )

        self.assertEqual(VitalSignsRecord.objects.count(), 1)

    def test_same_key_with_different_origin_is_safe_conflict(self):
        key = uuid.uuid4()
        record_vital_signs(
            encounter=self.encounter,
            actor=self.nurse,
            data=self.data,
            idempotency_key=key,
            origin=VitalSignsRecord.Origin.OFFLINE_SYNC,
        )

        with self.assertRaises(VitalSignsIdempotencyConflictError):
            record_vital_signs(
                encounter=self.encounter,
                actor=self.nurse,
                data=self.data,
                idempotency_key=key,
                origin=VitalSignsRecord.Origin.ONLINE,
            )

        self.assertEqual(VitalSignsRecord.objects.count(), 1)

    def test_retry_revalidates_permission_before_acknowledging_existing_record(self):
        key = uuid.uuid4()
        record_vital_signs(
            encounter=self.encounter,
            actor=self.nurse,
            data=self.data,
            idempotency_key=key,
        )
        self.nurse.user_permissions.remove(self.record_permission)
        actor = get_user_model().objects.get(pk=self.nurse.pk)

        with self.assertRaises(PermissionDenied):
            record_vital_signs(
                encounter=self.encounter,
                actor=actor,
                data=self.data,
                idempotency_key=key,
            )

        self.assertEqual(VitalSignsRecord.objects.count(), 1)

    def test_invalid_idempotency_key_is_rejected_without_insert(self):
        with self.assertRaises(VitalSignsIdempotencyConflictError):
            record_vital_signs(
                encounter=self.encounter,
                actor=self.nurse,
                data=self.data,
                idempotency_key="not-a-uuid",
            )

        self.assertFalse(VitalSignsRecord.objects.exists())
