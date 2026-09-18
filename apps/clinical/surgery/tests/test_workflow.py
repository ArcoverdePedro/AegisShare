import uuid
from datetime import date
from unittest.mock import patch

from auditlog.models import LogEntry
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, connection
from django.db.models.deletion import ProtectedError
from django.test import Client, RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.models import Encounter, Patient, PatientAccessGrant
from apps.clinical.pep.tests.test_views import TEST_STORAGES

from ..models import Procedure, SurgicalCase
from ..services import request_procedure


@override_settings(STORAGES=TEST_STORAGES, SECURE_SSL_REDIRECT=False)
class SurgeryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user("surgery-admin", role="ADM")
        cls.admin.is_superuser = True
        cls.admin.save(update_fields=["is_superuser"])
        cls.user = make_user("surgery-user", role="FUNC")
        cls.other = make_user("surgery-other", role="FUNC")
        cls.permissions = Permission.objects.filter(
            content_type__app_label="surgery", codename__in=["view_cases", "request_procedure"]
        )
        for user in (cls.user, cls.other):
            user.user_permissions.add(*cls.permissions)
        cls.patient = Patient.objects.create(
            identifier_type="OTHER",
            identifier="SURG-SYNTH",
            full_name="Paciente sintético SURG",
            birth_date=date(1990, 1, 1),
            created_by=cls.user,
        )
        cls.encounter = Encounter.objects.create(
            patient=cls.patient, responsible_professional=cls.user, created_by=cls.user
        )
        cls.procedure = Procedure.objects.create(code="SURG-PRIVATE", name="Procedimento sintético")
        cls.url = reverse("surgery:case_create", args=[cls.encounter.pk])
        cls.list_url = reverse("surgery:case_list")

    def setUp(self):
        self.client.force_login(self.user)

    def data(self, **changes):
        return {"procedure": self.procedure.pk, "operation_key": uuid.uuid4(), **changes}

    def order(self, **changes):
        return request_procedure(
            user=self.user,
            encounter_id=self.encounter.pk,
            procedure=self.procedure,
            operation_key=changes.get("operation_key", uuid.uuid4()),
        )

    def test_snapshot_retry_and_new_operation(self):
        data = self.data(
            requested_by=self.other.pk, procedure_name="FORGED", requested_at="1990-01-01"
        )
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        item = SurgicalCase.objects.get()
        original = item.requested_at
        self.assertEqual(item.requested_by, self.user)
        self.assertEqual(item.procedure_name, self.procedure.name)
        self.procedure.name, self.procedure.code, self.procedure.active = (
            "Changed",
            "Changed",
            False,
        )
        self.procedure.save()
        self.assertEqual(self.client.post(self.url, data).url, response.url)
        item.refresh_from_db()
        self.assertEqual(item.requested_at, original)
        self.assertEqual(item.procedure_name, "Procedimento sintético")
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 409)
        self.assertEqual(SurgicalCase.objects.count(), 1)
        self.procedure.active = True
        self.procedure.save()
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 302)
        self.assertEqual(SurgicalCase.objects.count(), 2)

    def test_conflicting_key_does_not_reveal_original(self):
        item = self.order()
        other_exam = Procedure.objects.create(code="OTHER", name="Other")
        response = self.client.post(
            self.url, self.data(operation_key=item.operation_key, procedure=other_exam.pk)
        )
        self.assertEqual(response.status_code, 409)
        self.assertNotContains(response, str(item.pk), status_code=409)
        self.assertEqual(SurgicalCase.objects.count(), 1)
        PatientAccessGrant.objects.create(
            patient=self.patient, user=self.other, granted_by=self.admin, reason="Sintético"
        )
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.post(self.url, self.data(operation_key=item.operation_key)).status_code, 409
        )

    def test_revocation_and_inactive_patient_hide_history(self):
        item = self.order()
        detail = reverse("surgery:case_detail", args=[item.pk])
        grant = PatientAccessGrant.objects.create(
            patient=self.patient, user=self.other, granted_by=self.admin, reason="Sintético"
        )
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        grant.delete()
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 404)
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertNotContains(self.client.get(self.list_url), self.patient.full_name)
        self.client.force_login(self.user)
        self.patient.active = False
        self.patient.save()
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 404)

    def test_closed_encounter_blocks_new_and_retry_but_preserves_read(self):
        item = self.order()
        Encounter.objects.filter(pk=self.encounter.pk).update(
            status=Encounter.Status.CLOSED, ended_at=timezone.now()
        )
        for data in (self.data(), self.data(operation_key=item.operation_key)):
            self.assertEqual(self.client.post(self.url, data).status_code, 409)
        self.assertEqual(
            self.client.get(reverse("surgery:case_detail", args=[item.pk])).status_code, 200
        )
        self.assertEqual(SurgicalCase.objects.count(), 1)

    def test_capabilities_and_internal_role_are_required(self):
        self.user.user_permissions.remove(*self.permissions)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        self.user.user_permissions.add(
            Permission.objects.get(content_type__app_label="surgery", codename="view_cases")
        )
        self.assertEqual(self.client.get(self.list_url).status_code, 200)
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 403)
        self.user.user_permissions.set(self.permissions.filter(codename="request_procedure"))
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 403)
        outsider = make_user("surgery-client", role="CLI")
        outsider.user_permissions.add(*self.permissions)
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        self.client.force_login(self.admin)
        self.admin.is_superuser = False
        self.admin.save(update_fields=["is_superuser"])
        self.assertEqual(self.client.get(self.list_url).status_code, 403)

    def test_invalid_form_preserves_key_and_active_get_choices(self):
        inactive = Procedure.objects.create(code="INACTIVE", name="Inactive", active=False)
        self.assertNotContains(self.client.get(self.url), inactive.name)
        key = uuid.uuid4()
        response = self.client.post(self.url, self.data(procedure=uuid.uuid4(), operation_key=key))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.context["form"]["operation_key"].value()), str(key))
        self.assertEqual(
            self.client.post(self.url, self.data(operation_key="bad")).status_code, 200
        )
        self.assertEqual(SurgicalCase.objects.count(), 0)

    def test_audit_failure_rolls_back_mutation_and_blocks_reads(self):
        self.client.get(self.url)  # inicializa o inventário de sessão antes do mock global
        with patch(
            "auditlog.models.LogEntry.objects.create",
            side_effect=IntegrityError("audit unavailable"),
        ):
            self.assertEqual(self.client.post(self.url, self.data()).status_code, 503)
        self.assertFalse(SurgicalCase.objects.exists())
        item = self.order()
        with patch(
            "apps.clinical.surgery.views.accessed.send",
            side_effect=DatabaseError("audit unavailable"),
        ):
            for url in (self.url, self.list_url, reverse("surgery:case_detail", args=[item.pk])):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 503)
                self.assertNotContains(response, self.patient.full_name, status_code=503)
        with patch(
            "apps.clinical.surgery.services.accessed.send",
            side_effect=DatabaseError("audit unavailable"),
        ):
            self.assertEqual(
                self.client.post(self.url, self.data(operation_key=item.operation_key)).status_code,
                503,
            )

    def test_append_only_protect_and_catalog_validation(self):
        item = self.order()
        with self.assertRaises(ValidationError):
            item.save()
        with self.assertRaises(ValidationError):
            item.delete()
        with self.assertRaises(ProtectedError):
            self.procedure.delete()
        with self.assertRaises(ValidationError):
            Procedure.objects.create(code="   ", name="Name")
        procedure = Procedure.objects.create(code=" trimmed ", name=" Name ")
        self.assertEqual((procedure.code, procedure.name), ("trimmed", "Name"))
        with self.assertRaises(ValidationError):
            Procedure.objects.create(code="trimmed", name="Duplicate")
        self.assertNotIn(SurgicalCase, admin.site._registry)
        catalog_admin = admin.site._registry[Procedure]
        request = RequestFactory().get("/")
        request.user = make_user("surgery-client-admin", role="CLI")
        request.user.is_superuser = True
        self.assertFalse(catalog_admin.has_change_permission(request))

    def test_audit_minimizes_content_and_records_actor(self):
        item = self.order()
        self.client.get(reverse("surgery:case_detail", args=[item.pk]))
        logs = LogEntry.objects.filter(content_type__app_label="surgery")
        serialized = str(list(logs.values("changes", "object_repr", "additional_data")))
        for marker in (self.patient.full_name, self.procedure.code, self.procedure.name):
            self.assertNotIn(marker, serialized)
        for action in (LogEntry.Action.CREATE, LogEntry.Action.ACCESS):
            self.assertTrue(
                logs.filter(object_pk=str(item.pk), action=action, actor=self.user).exists()
            )

    def test_pagination_audits_only_visible_records_without_n_plus_one(self):
        for _ in range(26):
            self.order()
        LogEntry.objects.filter(
            content_type__app_label="surgery", action=LogEntry.Action.ACCESS
        ).delete()
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.list_url)
        self.assertEqual(len(response.context["page_obj"]), 25)
        self.assertEqual(
            LogEntry.objects.filter(
                content_type__app_label="surgery", action=LogEntry.Action.ACCESS
            ).count(),
            25,
        )
        related = [
            q for q in queries if q["sql"].startswith("SELECT") and '"pep_patient"' in q["sql"]
        ]
        self.assertLessEqual(len(related), 2)
        self.assertEqual(len(self.client.get(self.list_url, {"page": 2}).context["page_obj"]), 1)

    def test_privacy_headers_cover_csrf_methods_missing_and_redirects(self):
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        responses = [
            self.client.get(self.url),
            self.client.put(self.url),
            csrf.post(self.url, self.data()),
            self.client.get(reverse("surgery:case_detail", args=[uuid.uuid4()])),
        ]
        self.client.logout()
        responses.append(self.client.get(self.list_url))
        self.assertEqual([r.status_code for r in responses], [200, 405, 403, 404, 302])
        for response in responses:
            self.assertEqual(response["Cache-Control"], "private, no-store")
            self.assertIn("Cookie", response["Vary"])
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")
