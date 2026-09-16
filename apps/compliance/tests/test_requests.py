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
from apps.clinical.pep.models import Patient, PatientAccessGrant
from apps.clinical.pep.tests.test_views import TEST_STORAGES
from apps.interoperability.models import PatientExportReceipt

from ..models import DataSubjectRequest, DataSubjectRequestEvent


@override_settings(STORAGES=TEST_STORAGES, SECURE_SSL_REDIRECT=False)
class RequestTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user("lgp-admin", role="ADM")
        cls.admin.is_superuser = True
        cls.admin.save(update_fields=["is_superuser"])
        cls.owner = make_user("lgp-owner", role="FUNC")
        cls.other = make_user("lgp-other", role="FUNC")
        cls.permissions = Permission.objects.filter(
            content_type__app_label="compliance",
            codename__in=["view_requests", "register_request", "process_request"],
        )
        for user in (cls.owner, cls.other):
            user.user_permissions.add(*cls.permissions)
        cls.patient = Patient.objects.create(
            identifier_type="OTHER",
            identifier="LGP-ID-PRIVATE",
            full_name="Pessoa Sintética LGPD",
            birth_date=date(1990, 1, 15),
            created_by=cls.owner,
        )
        cls.item = DataSubjectRequest.objects.create(
            patient=cls.patient,
            category="ACCESS",
            summary="Resumo privado sintético",
            created_by=cls.owner,
        )
        DataSubjectRequestEvent.objects.create(
            request=cls.item, to_status="RECEIVED", actor=cls.owner
        )
        cls.list_url = reverse("compliance:request_list")
        cls.create_url = reverse("compliance:request_create")
        cls.detail_url = reverse("compliance:request_detail", args=[cls.item.pk])
        cls.transition_url = reverse("compliance:request_transition", args=[cls.item.pk])

    def setUp(self):
        self.client.force_login(self.owner)

    def create(self, **overrides):
        return self.client.post(
            self.create_url,
            {
                "patient": self.patient.pk,
                "category": "ACCESS",
                "summary": "Novo pedido sintético",
                **overrides,
            },
        )

    def transition(self, expected="RECEIVED", target="IN_REVIEW", note=""):
        return self.client.post(
            self.transition_url,
            {
                "expected_status": expected,
                "target_status": target,
                "note": note,
            },
        )

    def assert_private(self, response):
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertIn("Cookie", response["Vary"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_creation_ignores_client_status_and_actor_and_is_audited(self):
        response = self.create(status="CLOSED", created_by=self.other.pk)
        self.assertEqual(response.status_code, 302)
        self.assert_private(response)
        item = DataSubjectRequest.objects.exclude(pk=self.item.pk).get()
        self.assertEqual(item.status, "RECEIVED")
        self.assertEqual(item.created_by, self.owner)
        event = item.events.get()
        self.assertEqual((event.from_status, event.to_status, event.note), ("", "RECEIVED", ""))
        for instance in (item, event):
            entry = LogEntry.objects.get_for_object(instance).get(action=LogEntry.Action.CREATE)
            self.assertEqual(entry.actor, self.owner)
            self.assertNotIn(item.summary, str(entry.changes))

    def test_complete_flow_preserves_history_without_patient_mutation_or_export(self):
        before = Patient.objects.values().get(pk=self.patient.pk)
        self.assertEqual(self.transition().status_code, 302)
        self.assertEqual(
            self.transition("IN_REVIEW", "CLOSED", "Atendimento documentado").status_code, 302
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, "CLOSED")
        self.assertEqual(
            list(self.item.events.values_list("to_status", flat=True)),
            ["RECEIVED", "IN_REVIEW", "CLOSED"],
        )
        self.assertEqual(Patient.objects.values().get(pk=self.patient.pk), before)
        self.assertFalse(PatientExportReceipt.objects.exists())
        self.assertFalse(PatientAccessGrant.objects.exists())
        response = self.client.get(self.detail_url)
        self.assertContains(response, "Encerrada administrativamente")
        self.assertNotContains(response, f'href="{self.transition_url}"')

    def test_get_does_not_mutate_state_or_events(self):
        for url in (self.list_url, self.create_url, self.detail_url, self.transition_url):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assert_private(response)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, "RECEIVED")
        self.assertEqual(self.item.events.count(), 1)

    def test_summary_category_and_patient_validation(self):
        for fields in (
            {"summary": "   "},
            {"summary": "x" * 2001},
            {"category": "INVALID"},
            {"patient": uuid.uuid4()},
        ):
            response = self.create(**fields)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
        self.assertEqual(DataSubjectRequest.objects.count(), 1)

    def test_close_requires_note_and_trims_it(self):
        self.transition()
        response = self.transition("IN_REVIEW", "CLOSED", "  ")
        self.assertContains(response, "Registre uma nota de atendimento")
        self.assertEqual(self.item.events.count(), 2)
        self.transition("IN_REVIEW", "CLOSED", "  Nota preservada  ")
        self.assertEqual(self.item.events.get(to_status="CLOSED").note, "Nota preservada")

    def test_invalid_transition_and_replay_are_conflicts(self):
        self.assertEqual(
            self.transition(target="CLOSED", note="Não pular análise").status_code, 409
        )
        self.transition(note="Primeira nota")
        response = self.transition(note="Tentativa de sobrescrita")
        self.assertEqual(response.status_code, 409)
        self.assert_private(response)
        self.assertEqual(self.item.events.get(to_status="IN_REVIEW").note, "Primeira nota")
        self.assertEqual(self.item.events.count(), 2)
        # Destino válido para o estado atual, mas formulário baseado em estado antigo.
        self.assertEqual(self.transition("RECEIVED", "CLOSED", "Nota").status_code, 409)

    def test_closed_request_cannot_reopen(self):
        self.transition()
        self.transition("IN_REVIEW", "CLOSED", "Nota")
        self.assertRedirects(self.client.get(self.transition_url), self.detail_url)
        self.assertEqual(self.transition("CLOSED", "IN_REVIEW").status_code, 409)
        self.assertEqual(self.item.events.count(), 3)

    def test_capabilities_are_independent_and_require_view(self):
        self.owner.user_permissions.clear()
        for name in ("register_request", "process_request"):
            self.owner.user_permissions.add(self.permissions.get(codename=name))
        self.assertEqual(self.create().status_code, 403)
        self.assertEqual(self.transition().status_code, 403)
        self.owner.user_permissions.set([self.permissions.get(codename="view_requests")])
        self.assertEqual(self.client.get(self.detail_url).status_code, 200)
        self.assertEqual(self.create().status_code, 403)
        self.assertEqual(self.transition().status_code, 403)

    def test_client_role_denied_even_with_capabilities(self):
        user = make_user("lgp-client")
        user.user_permissions.add(*self.permissions)
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)

    def test_objects_out_of_scope_are_not_disclosed(self):
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(self.list_url), self.patient.full_name)
        for response in (
            self.client.get(self.detail_url),
            self.client.get(self.transition_url),
            self.transition(),
        ):
            self.assertEqual(response.status_code, 404)
            self.assert_private(response)
            self.assertNotContains(response, self.item.summary, status_code=404)
        self.assertContains(self.create(), "Selecione um paciente disponível.")

    def test_revoked_or_expired_grant_between_get_and_post(self):
        self.client.force_login(self.other)
        for revoke in (True, False):
            grant = PatientAccessGrant.objects.create(
                patient=self.patient, user=self.other, reason="Teste", granted_by=self.admin
            )
            self.assertEqual(self.client.get(self.transition_url).status_code, 200)
            if revoke:
                grant.delete()
            else:
                grant.expires_at = timezone.now() - timedelta(seconds=1)
                grant.save()
            self.assertEqual(self.transition().status_code, 404)
        self.assertEqual(self.item.events.count(), 1)

    def test_permission_revoked_between_get_and_post(self):
        self.client.get(self.transition_url)
        self.owner.user_permissions.remove(self.permissions.get(codename="process_request"))
        self.assertEqual(self.transition().status_code, 403)
        self.assertEqual(self.item.events.count(), 1)

    def test_inactive_patient_not_available(self):
        self.patient.active = False
        self.patient.save()
        self.assertEqual(self.client.get(self.detail_url).status_code, 404)
        self.assertContains(self.create(), "Selecione um paciente disponível.")

    def test_csrf_login_and_methods(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        for url in (self.create_url, self.transition_url):
            response = client.post(url, {})
            self.assertEqual(response.status_code, 403)
            self.assert_private(response)
        self.assertEqual(self.client.put(self.transition_url).status_code, 405)
        self.assertEqual(self.client.post(self.list_url).status_code, 405)
        self.client.logout()
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 302)
        self.assert_private(response)

    def test_creation_event_failure_rolls_back_request_and_audit(self):
        self.client.get(self.create_url)
        baseline = LogEntry.objects.count()
        with patch.object(DataSubjectRequestEvent.objects, "create", side_effect=DatabaseError):
            response = self.create()
        self.assertEqual(response.status_code, 503)
        self.assert_private(response)
        self.assertEqual(DataSubjectRequest.objects.count(), 1)
        self.assertEqual(LogEntry.objects.count(), baseline)

    def test_transition_audit_failure_rolls_back_state_and_event(self):
        self.client.get(self.transition_url)
        baseline = LogEntry.objects.count()
        original = LogEntry.objects.log_create

        def fail_event(instance, **kwargs):
            if isinstance(instance, DataSubjectRequestEvent):
                raise DatabaseError("synthetic-secret-must-not-be-logged")
            return original(instance, **kwargs)

        with (
            patch.object(LogEntry.objects, "log_create", side_effect=fail_event),
            self.assertLogs("apps.compliance.views", level="ERROR") as logs,
        ):
            response = self.transition(note="Private note")
        self.assertEqual(response.status_code, 503)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, "RECEIVED")
        self.assertEqual(self.item.events.count(), 1)
        self.assertEqual(LogEntry.objects.count(), baseline)
        self.assertNotIn("Private note", str(logs.output))
        self.assertNotIn("synthetic-secret", str(logs.output))

    def test_notes_are_escaped_and_excluded_from_audit(self):
        marker = '<script>alert("LGP-PRIVATE-NOTE")</script>'
        self.transition(note=marker)
        response = self.client.get(self.detail_url)
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, marker)
        event = self.item.events.get(to_status="IN_REVIEW")
        self.assertNotIn(
            "LGP-PRIVATE-NOTE", str(list(LogEntry.objects.get_for_object(event).values()))
        )
        self.assertTrue(
            LogEntry.objects.get_for_object(self.item)
            .filter(action=LogEntry.Action.ACCESS, actor=self.owner)
            .exists()
        )

    def test_events_and_original_request_cannot_be_edited_or_deleted(self):
        event = self.item.events.get()
        for operation in (event.save, event.delete, self.item.save, self.item.delete):
            with self.assertRaises(ValidationError):
                operation()

    def test_filter_pagination_and_only_visible_access_audit(self):
        for i in range(25):
            DataSubjectRequest.objects.create(
                patient=self.patient, created_by=self.owner, category="OTHER", summary=f"Pedido {i}"
            )
        baseline = LogEntry.objects.filter(action=LogEntry.Action.ACCESS).count()
        response = self.client.get(self.list_url)
        self.assertEqual(len(response.context["page_obj"]), 25)
        self.assertEqual(
            LogEntry.objects.filter(action=LogEntry.Action.ACCESS).count() - baseline, 25
        )
        self.assertEqual(len(self.client.get(self.list_url, {"page": 2}).context["page_obj"]), 1)
        response = self.client.get(self.list_url, {"status": "INVALID"})
        self.assertEqual(len(response.context["page_obj"]), 0)
        self.assertTrue(response.context["filter_form"].errors)

    def test_patient_and_actor_selects_do_not_grow_with_list_size(self):
        self.client.get(self.list_url)
        with CaptureQueriesContext(connection) as first:
            self.client.get(self.list_url)
        for i in range(8):
            DataSubjectRequest.objects.create(
                patient=self.patient,
                created_by=self.owner,
                category="ACCESS",
                summary=f"Pedido {i}",
            )
        with CaptureQueriesContext(connection) as many:
            self.client.get(self.list_url)

        def selects(queries):
            return sum(q["sql"].lstrip().upper().startswith("SELECT") for q in queries)

        self.assertEqual(selects(first), selects(many))
