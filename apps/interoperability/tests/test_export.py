import hashlib
import json
import uuid
from datetime import date, timedelta
from unittest.mock import patch

from auditlog.models import LogEntry
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.models import Patient, PatientAccessGrant
from apps.clinical.pep.tests.test_views import TEST_STORAGES

from ..models import PatientExportReceipt


@override_settings(STORAGES=TEST_STORAGES, SECURE_SSL_REDIRECT=False)
class PatientExportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user("interop-admin", role="ADM")
        cls.admin.is_superuser = True
        cls.admin.save(update_fields=["is_superuser"])
        cls.owner = make_user("interop-owner", role="FUNC")
        cls.other = make_user("interop-other", role="FUNC")
        cls.permission = Permission.objects.get(
            content_type__app_label="interoperability", codename="export_patient"
        )
        cls.owner.user_permissions.add(cls.permission)
        cls.other.user_permissions.add(cls.permission)
        cls.patient = Patient.objects.create(
            identifier_type="OTHER",
            identifier="EXCLUDED-IDENTIFIER",
            full_name="Pessoa Sintética Exportação",
            birth_date=date(1980, 4, 12),
            sex="I",
            phone="EXCLUDED-PHONE",
            email="excluded@example.invalid",
            created_by=cls.owner,
        )
        cls.url = reverse("interoperability:patient_export")

    def setUp(self):
        self.client.force_login(self.owner)

    def export(self, **overrides):
        return self.client.post(
            self.url, {"patient": str(self.patient.pk), "confirm": "on", **overrides}
        )

    def assert_private(self, response):
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("Cookie", response["Vary"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_export_allowlist_utf8_and_audited_receipt(self):
        response = self.export()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/fhir+json")
        self.assert_private(response)
        self.assertEqual(
            json.loads(response.content),
            {
                "resourceType": "Patient",
                "id": str(self.patient.pk),
                "active": True,
                "name": [{"text": self.patient.full_name}],
                "birthDate": "1980-04-12",
            },
        )
        self.assertIn(self.patient.full_name.encode(), response.content)
        receipt = PatientExportReceipt.objects.get()
        self.assertEqual(receipt.content_sha256, hashlib.sha256(response.content).hexdigest())
        self.assertEqual(receipt.created_by, self.owner)
        self.assertEqual(receipt.patient, self.patient)
        self.assertEqual(receipt.contract_version, "patient-r4-v1")
        self.assertEqual(
            response["Content-Disposition"],
            f'attachment; filename="patient-export-{receipt.pk}.json"',
        )
        entry = LogEntry.objects.get_for_object(receipt).get(action=LogEntry.Action.CREATE)
        self.assertEqual(entry.actor, self.owner)
        self.assertEqual(
            LogEntry.objects.get_for_object(self.patient)
            .filter(action=LogEntry.Action.ACCESS, actor=self.owner)
            .count(),
            1,
        )
        logs = str(list(LogEntry.objects.get_for_object(receipt).values()))
        self.assertNotIn(self.patient.full_name, logs)
        self.assertNotIn(self.patient.identifier, logs)
        self.assertNotIn("1980-04-12", logs)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.identifier, "EXCLUDED-IDENTIFIER")

    def test_get_does_not_export_and_options_are_scoped(self):
        self.client.force_login(self.other)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.patient.full_name)
        self.assert_private(response)
        self.assertFalse(PatientExportReceipt.objects.exists())
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertContains(response, self.patient.full_name)
        self.assertContains(response, str(self.patient.pk))
        self.assertNotContains(response, self.patient.identifier)
        self.assertContains(response, 'href="' + self.url + '"')

    def test_anonymous_redirect_and_no_bearer_access(self):
        self.client.logout()
        response = self.client.post(self.url, HTTP_AUTHORIZATION="Bearer any-token")
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
        self.assert_private(response)
        self.assertFalse(PatientExportReceipt.objects.exists())

    def test_capability_required_even_for_admin_role(self):
        user = make_user("ordinary-admin", role="ADM")
        self.client.force_login(user)
        for method in (self.client.get, self.client.post):
            response = method(self.url)
            self.assertEqual(response.status_code, 403)
            self.assert_private(response)
        self.assertFalse(PatientExportReceipt.objects.exists())

    def test_client_role_denied_even_with_capability(self):
        user = make_user("interop-client", role="CLI")
        user.user_permissions.add(self.permission)
        self.client.force_login(user)
        self.assertEqual(self.export().status_code, 403)

    def test_superuser_uses_native_permission_rules(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.export()["Content-Type"], "application/fhir+json")

    def test_unknown_and_out_of_scope_have_same_errors(self):
        self.client.force_login(self.other)
        for value in (str(self.patient.pk), str(uuid.uuid4()), "invalid"):
            response = self.export(patient=value)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.context["form"].errors["patient"],
                ["Selecione um paciente disponível."],
            )
            self.assertNotContains(response, self.patient.full_name)
            self.assertNotIn("Content-Disposition", response)
            self.assert_private(response)
        self.assertFalse(PatientExportReceipt.objects.exists())

    def test_grant_revoked_or_expired_between_get_and_post(self):
        self.client.force_login(self.other)
        for revoke in (True, False):
            grant = PatientAccessGrant.objects.create(
                patient=self.patient,
                user=self.other,
                reason="Teste sintético",
                granted_by=self.admin,
            )
            self.assertContains(self.client.get(self.url), self.patient.full_name)
            if revoke:
                grant.delete()
            else:
                grant.expires_at = timezone.now() - timedelta(seconds=1)
                grant.save()
            response = self.export()
            self.assertNotIn("Content-Disposition", response)
            self.assertNotContains(response, self.patient.full_name)
        self.assertFalse(PatientExportReceipt.objects.exists())

    def test_permission_revoked_between_get_and_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.owner.user_permissions.remove(self.permission)
        self.assertEqual(self.export().status_code, 403)
        self.assertFalse(PatientExportReceipt.objects.exists())

    def test_inactive_patient_is_not_exported(self):
        self.patient.active = False
        self.patient.save()
        self.assertNotIn("Content-Disposition", self.export())
        self.assertFalse(PatientExportReceipt.objects.exists())

    def test_missing_confirmation_and_empty_post_are_bound_errors(self):
        response = self.export(confirm="")
        self.assertIn("confirm", response.context["form"].errors)
        response = self.client.post(self.url, {})
        self.assertTrue(response.context["form"].is_bound)
        self.assertIn("patient", response.context["form"].errors)
        self.assertFalse(PatientExportReceipt.objects.exists())

    def test_csrf_required_and_rejection_is_private(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        response = client.post(self.url, {"patient": self.patient.pk, "confirm": "on"})
        self.assertEqual(response.status_code, 403)
        self.assert_private(response)
        self.assertFalse(PatientExportReceipt.objects.exists())
        client.get(self.url)
        response = client.post(
            self.url,
            {
                "patient": self.patient.pk,
                "confirm": "on",
                "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
            },
        )
        self.assertEqual(response["Content-Type"], "application/fhir+json")

    def test_unsupported_methods(self):
        response = self.client.put(self.url)
        self.assertEqual(response.status_code, 405)
        self.assert_private(response)

    def test_access_audit_failure_rolls_back_receipt_and_create_audit(self):
        self.client.get(self.url)
        baseline = LogEntry.objects.count()
        with (
            patch("apps.interoperability.views.accessed.send", side_effect=DatabaseError),
            self.assertLogs("apps.interoperability.views", level="ERROR") as logs,
        ):
            response = self.export()
        self.assertEqual(response.status_code, 503)
        self.assert_private(response)
        self.assertNotIn("Content-Disposition", response)
        self.assertNotContains(response, self.patient.full_name, status_code=503)
        self.assertNotIn(self.patient.full_name, str(logs.output))
        self.assertFalse(PatientExportReceipt.objects.exists())
        self.assertEqual(LogEntry.objects.count(), baseline)

    def test_receipt_audit_failure_prevents_download(self):
        self.client.get(self.url)
        with patch.object(LogEntry.objects, "log_create", side_effect=DatabaseError):
            response = self.export()
        self.assertEqual(response.status_code, 503)
        self.assertFalse(PatientExportReceipt.objects.exists())

    def test_recheck_scope_before_serialization(self):
        with patch(
            "apps.interoperability.views.accessible_patients", return_value=Patient.objects.none()
        ):
            response = self.export()
        self.assertNotIn("Content-Disposition", response)
        self.assertIn("patient", response.context["form"].errors)
        self.assertFalse(PatientExportReceipt.objects.exists())

    def test_receipt_immutable_and_patient_protected(self):
        self.export()
        receipt = PatientExportReceipt.objects.get()
        with self.assertRaises(ValidationError):
            receipt.save()
        with self.assertRaises(ValidationError):
            receipt.delete()
        with self.assertRaises(ProtectedError):
            self.patient.delete()

    def test_repeat_export_records_each_generation(self):
        first = self.export()
        second = self.export()
        self.assertEqual(first.content, second.content)
        self.assertNotEqual(first["Content-Disposition"], second["Content-Disposition"])
        self.assertEqual(PatientExportReceipt.objects.count(), 2)
