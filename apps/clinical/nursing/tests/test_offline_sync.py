import json
import uuid
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.clinical.pep.models import Encounter, Patient, PatientAccessGrant
from apps.pwa.session import hash_session_key

from ..models import VitalSignsRecord

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES)
class VitalSignsOfflineSyncTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.bootstrap_admin = user_model.objects.create_superuser(
            username="nursing-offline-bootstrap-admin",
            email="nursing-offline-bootstrap@example.invalid",
            password="StrongPass!2026",
        )
        self.nurse = user_model.objects.create_user(
            username="nursing-offline-user",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.other_employee = user_model.objects.create_user(
            username="nursing-offline-other",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.record_permission = Permission.objects.get(
            content_type__app_label="nursing",
            codename="record_vitals",
        )
        self.nurse.user_permissions.add(self.record_permission)
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="NUR-OFFLINE-1",
            full_name="Paciente Offline Sintético",
            birth_date=date(1990, 1, 1),
            created_by=self.nurse,
        )
        self.started_at = timezone.now() - timedelta(hours=1)
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            started_at=self.started_at,
            responsible_professional=self.nurse,
            created_by=self.nurse,
        )
        self.client.force_login(self.nurse)

    def _recorded_at(self, value=None):
        value = value or timezone.now() - timedelta(minutes=2)
        return timezone.localtime(value).strftime("%Y-%m-%dT%H:%M:%S")

    def _fingerprint(self, client=None):
        client = client or self.client
        return hash_session_key(client.session.session_key)

    def _body(self, *, key=None, encounter=None, fingerprint=None, **measurements):
        return {
            "idempotency_key": str(key or uuid.uuid4()),
            "operation_type": "nursing.vitals.record",
            "user_session_fingerprint": fingerprint or self._fingerprint(),
            "payload": {
                "encounter_id": str((encounter or self.encounter).pk),
                "recorded_at": self._recorded_at(),
                "replaces_id": None,
                "measurements": measurements or {"temperature_c": "36.50"},
            },
        }

    def _post(self, body, *, client=None):
        client = client or self.client
        return client.post(
            reverse("nursing:vitals_sync"),
            data=json.dumps(body),
            content_type="application/json",
        )

    def test_same_envelope_twice_creates_one_offline_record(self):
        key = uuid.uuid4()
        body = self._body(key=key, temperature_c="36.50", heart_rate_bpm="72")

        first = self._post(body)
        second = self._post(body)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["record_id"], second.json()["record_id"])
        self.assertEqual(VitalSignsRecord.objects.count(), 1)
        record = VitalSignsRecord.objects.get()
        self.assertEqual(record.idempotency_key, key)
        self.assertEqual(record.origin, VitalSignsRecord.Origin.OFFLINE_SYNC)
        self.assertEqual(record.recorded_by, self.nurse)

    def test_same_key_with_incompatible_payload_is_safe_conflict(self):
        key = uuid.uuid4()
        original = self._body(key=key, temperature_c="36.50")
        conflict = json.loads(json.dumps(original))
        conflict["payload"]["measurements"]["temperature_c"] = "37.00"

        self.assertEqual(self._post(original).status_code, 200)
        response = self._post(conflict)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json(),
            {"status": "conflict", "reason": "idempotency_conflict"},
        )
        self.assertEqual(VitalSignsRecord.objects.count(), 1)
        self.assertEqual(str(VitalSignsRecord.objects.get().temperature_c), "36.50")

    def test_closed_encounter_becomes_conflict_without_insert(self):
        ended_at = timezone.now() - timedelta(minutes=5)
        self.encounter.status = Encounter.Status.CLOSED
        self.encounter.ended_at = ended_at
        self.encounter.save()
        body = self._body(encounter=self.encounter)
        body["payload"]["recorded_at"] = self._recorded_at(
            ended_at - timedelta(minutes=1)
        )

        response = self._post(body)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json(),
            {"status": "conflict", "reason": "encounter_unavailable"},
        )
        self.assertFalse(VitalSignsRecord.objects.exists())

    def test_lost_pep_scope_becomes_conflict_without_disclosing_patient(self):
        patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="NUR-OFFLINE-OUTSIDE",
            full_name="Paciente Offline Fora do Escopo",
            birth_date=date(1991, 2, 2),
            created_by=self.other_employee,
        )
        encounter = Encounter.objects.create(
            patient=patient,
            started_at=self.started_at,
            responsible_professional=self.other_employee,
            created_by=self.other_employee,
        )
        grant = PatientAccessGrant.objects.create(
            patient=patient,
            user=self.nurse,
            reason="Teste de sincronização offline",
            granted_by=self.other_employee,
        )
        body = self._body(encounter=encounter)
        grant.delete()

        response = self._post(body)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json(),
            {"status": "conflict", "reason": "encounter_unavailable"},
        )
        self.assertNotContains(response, patient.full_name, status_code=409)
        self.assertFalse(VitalSignsRecord.objects.exists())

    def test_session_change_becomes_conflict_without_insert(self):
        body = self._body(fingerprint="0" * 64)

        response = self._post(body)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json(),
            {"status": "conflict", "reason": "session_changed"},
        )
        self.assertFalse(VitalSignsRecord.objects.exists())

    def test_permission_loss_blocks_sync(self):
        body = self._body()
        self.nurse.user_permissions.remove(self.record_permission)

        response = self._post(body)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"status": "conflict", "reason": "permission_denied"},
        )
        self.assertFalse(VitalSignsRecord.objects.exists())

    def test_missing_replacement_becomes_conflict_without_insert(self):
        body = self._body()
        body["payload"]["replaces_id"] = str(uuid.uuid4())

        response = self._post(body)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json(),
            {"status": "conflict", "reason": "replacement_unavailable"},
        )
        self.assertFalse(VitalSignsRecord.objects.exists())

    def test_sync_requires_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.nurse)
        body = self._body(fingerprint=self._fingerprint(csrf_client))

        response = self._post(body, client=csrf_client)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(VitalSignsRecord.objects.exists())
