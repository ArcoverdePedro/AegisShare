import uuid
from datetime import date, timedelta
from unittest.mock import patch

from auditlog.models import LogEntry
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.models import Encounter, Patient, PatientAccessGrant
from apps.clinical.pep.tests.test_views import TEST_STORAGES

from ..models import LabTest, ServiceRequest, Specimen
from ..services import collect_specimen, order_test


@override_settings(STORAGES=TEST_STORAGES, SECURE_SSL_REDIRECT=False)
class LisTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user("lis-admin", role="ADM")
        cls.admin.is_superuser = True
        cls.admin.save(update_fields=["is_superuser"])
        cls.user = make_user("lis-user", role="FUNC")
        cls.other = make_user("lis-other", role="FUNC")
        cls.permissions = Permission.objects.filter(content_type__app_label="lis")
        cls.user.user_permissions.add(*cls.permissions)
        cls.other.user_permissions.add(*cls.permissions)
        cls.patient = Patient.objects.create(
            identifier_type="OTHER",
            identifier="LIS-SYNTH",
            full_name="Paciente sintético LIS",
            birth_date=date(1990, 1, 1),
            created_by=cls.user,
        )
        cls.encounter = Encounter.objects.create(
            patient=cls.patient,
            encounter_type="CONSULTATION",
            started_at=timezone.now(),
            responsible_professional=cls.user,
            created_by=cls.user,
        )
        cls.test = LabTest.objects.create(
            code="TEST-SYNTH", name="Exame sintético", specimen_type="Material sintético"
        )
        cls.url = reverse("lis:order_create", args=[cls.encounter.pk])

    def setUp(self):
        self.client.force_login(self.user)

    def order(self):
        return order_test(
            user=self.user,
            encounter_id=self.encounter.pk,
            lab_test=self.test,
            operation_key=uuid.uuid4(),
        )

    def specimen_data(self, **changes):
        return {
            "operation_key": uuid.uuid4(),
            "accession_code": "SAMPLE-PRIVATE",
            "collected_at": timezone.now().isoformat(),
            "confirmed": True,
            **changes,
        }

    def test_order_and_collection_preserve_snapshot_actor_and_history(self):
        key = uuid.uuid4()
        data = {"lab_test": self.test.pk, "operation_key": key, "requested_by": self.other.pk}
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        order = ServiceRequest.objects.get()
        self.assertEqual(order.requested_by, self.user)
        self.test.name = "Nome alterado"
        self.test.active = False
        self.test.save()
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.assertEqual(ServiceRequest.objects.count(), 1)
        self.assertEqual(order.test_name, "Exame sintético")
        url = reverse("lis:specimen_create", args=[order.pk])
        payload = self.specimen_data()
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        self.assertEqual(Specimen.objects.count(), 1)
        response = self.client.get(reverse("lis:order_detail", args=[order.pk]))
        self.assertContains(response, "Coleta registrada")
        for item in (order, Specimen.objects.get()):
            with self.assertRaises(ValidationError):
                item.save()
            with self.assertRaises(ValidationError):
                item.delete()

    def test_foreign_patient_and_revoked_grant_are_hidden(self):
        item = self.order()
        self.client.force_login(self.other)
        for url in (
            self.url,
            reverse("lis:order_detail", args=[item.pk]),
            reverse("lis:specimen_create", args=[item.pk]),
        ):
            self.assertEqual(self.client.get(url).status_code, 404)
        grant = PatientAccessGrant.objects.create(
            patient=self.patient, user=self.other, granted_by=self.admin, reason="Teste"
        )
        self.assertEqual(self.client.get(self.url).status_code, 200)
        grant.delete()
        self.assertEqual(
            self.client.post(
                self.url, {"lab_test": self.test.pk, "operation_key": uuid.uuid4()}
            ).status_code,
            404,
        )
        self.assertEqual(ServiceRequest.objects.count(), 1)

    def test_capabilities_and_internal_role_are_required(self):
        self.user.user_permissions.remove(
            Permission.objects.get(content_type__app_label="lis", codename="order_test")
        )
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.user.user_permissions.add(*self.permissions)
        self.user.nivel_permissao = "CLI"
        self.user.save(update_fields=["nivel_permissao"])
        self.assertEqual(self.client.get(reverse("lis:order_list")).status_code, 403)

    def test_closed_encounter_prevents_order_and_collection(self):
        item = self.order()
        payload = self.specimen_data()
        Encounter.objects.filter(pk=self.encounter.pk).update(status="CLOSED")
        self.assertEqual(
            self.client.post(
                self.url, {"lab_test": self.test.pk, "operation_key": uuid.uuid4()}
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.post(reverse("lis:specimen_create", args=[item.pk]), payload).status_code,
            409,
        )
        self.assertFalse(Specimen.objects.exists())

    def test_inactive_test_cannot_create_new_order(self):
        self.test.active = False
        self.test.save()
        self.assertNotContains(self.client.get(self.url), self.test.name)
        self.assertEqual(
            self.client.post(
                self.url, {"lab_test": self.test.pk, "operation_key": uuid.uuid4()}
            ).status_code,
            409,
        )
        self.assertFalse(ServiceRequest.objects.exists())

    def test_conflicting_key_or_collection_does_not_overwrite(self):
        item = self.order()
        other_test = LabTest.objects.create(code="OTHER", name="Outro", specimen_type="Outro")
        self.assertEqual(
            self.client.post(
                self.url, {"lab_test": other_test.pk, "operation_key": item.operation_key}
            ).status_code,
            409,
        )
        url = reverse("lis:specimen_create", args=[item.pk])
        payload = self.specimen_data()
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        self.assertEqual(
            self.client.post(url, {**payload, "accession_code": "CHANGED"}).status_code, 409
        )
        self.assertEqual(
            self.client.post(url, {**payload, "operation_key": uuid.uuid4()}).status_code, 409
        )
        self.assertEqual(Specimen.objects.get().accession_code, "SAMPLE-PRIVATE")

    def test_invalid_time_and_missing_confirmation_do_not_write(self):
        item = self.order()
        url = reverse("lis:specimen_create", args=[item.pk])
        for change in (
            {"confirmed": ""},
            {"collected_at": timezone.now() + timedelta(days=1)},
            {"collected_at": item.requested_at - timedelta(seconds=1)},
            {"accession_code": "   "},
        ):
            self.assertEqual(self.client.post(url, self.specimen_data(**change)).status_code, 200)
        self.assertFalse(Specimen.objects.exists())

    def test_sample_code_is_unique_and_error_does_not_identify_other_order(self):
        first, second = self.order(), self.order()
        payload = self.specimen_data()
        self.client.post(reverse("lis:specimen_create", args=[first.pk]), payload)
        response = self.client.post(
            reverse("lis:specimen_create", args=[second.pk]),
            {**payload, "operation_key": uuid.uuid4()},
        )
        self.assertEqual(response.status_code, 409)
        self.assertNotContains(response, str(first.pk), status_code=409)
        self.assertEqual(Specimen.objects.count(), 1)

    def test_audit_failure_rolls_back_order_and_specimen(self):
        self.client.get(self.url)
        with patch(
            "auditlog.models.LogEntry.objects.log_create", side_effect=DatabaseError("private")
        ):
            response = self.client.post(
                self.url, {"lab_test": self.test.pk, "operation_key": uuid.uuid4()}
            )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b"private", response.content)
        self.assertFalse(ServiceRequest.objects.exists())
        item = self.order()
        with patch(
            "auditlog.models.LogEntry.objects.log_create", side_effect=DatabaseError("private")
        ):
            response = self.client.post(
                reverse("lis:specimen_create", args=[item.pk]), self.specimen_data()
            )
        self.assertEqual(response.status_code, 503)
        self.assertFalse(Specimen.objects.exists())

    def test_audit_omits_sensitive_text_and_records_reads(self):
        item = self.order()
        collect_specimen(user=self.user, order=item, **self.specimen_data())
        self.client.get(reverse("lis:order_detail", args=[item.pk]))
        logs = LogEntry.objects.filter(content_type__app_label="lis")
        data = str(list(logs.values("changes", "object_repr", "additional_data")))
        for private in (
            "SAMPLE-PRIVATE",
            self.test.name,
            self.test.code,
            self.test.specimen_type,
            self.patient.full_name,
        ):
            self.assertNotIn(private, data)
        self.assertTrue(
            logs.filter(
                action=LogEntry.Action.ACCESS, actor=self.user, object_pk=str(item.pk)
            ).exists()
        )

    def test_headers_include_denial_csrf_and_invalid_methods(self):
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        responses = [self.client.get(self.url), self.client.put(self.url), csrf.post(self.url, {})]
        self.client.logout()
        responses.append(self.client.get(self.url))
        for response in responses:
            self.assertEqual(response["Cache-Control"], "private, no-store")
            self.assertIn("Cookie", response["Vary"])
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_pagination_filters_and_bounded_related_queries(self):
        items = [self.order() for _ in range(26)]
        url = reverse("lis:order_list")
        LogEntry.objects.filter(
            content_type__app_label="lis", action=LogEntry.Action.ACCESS
        ).delete()
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        self.assertEqual(len(response.context["page_obj"]), 25)
        self.assertEqual(
            LogEntry.objects.filter(
                content_type__app_label="lis", action=LogEntry.Action.ACCESS
            ).count(),
            25,
        )
        related = [
            q for q in queries if q["sql"].startswith("SELECT") and '"pep_patient"' in q["sql"]
        ]
        self.assertLessEqual(len(related), 2)
        self.assertEqual(len(self.client.get(url, {"page": 2}).context["page_obj"]), 1)
        self.assertEqual(len(self.client.get(url, {"status": "invalid"}).context["page_obj"]), 0)
        self.assertEqual(len(self.client.get(url, {"status": "collected"}).context["page_obj"]), 0)
        self.assertEqual(len(items), 26)
