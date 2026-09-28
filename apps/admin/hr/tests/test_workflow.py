import uuid
from unittest.mock import patch

from auditlog.models import LogEntry as AuditLogEntry
from django.contrib import admin
from django.contrib.admin.models import LogEntry as AdminLogEntry
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, connection
from django.db.models.deletion import ProtectedError
from django.test import Client, RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.tests.test_views import TEST_STORAGES

from ..models import Employee


@override_settings(STORAGES=TEST_STORAGES, SECURE_SSL_REDIRECT=False)
class EmployeeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.system_admin = make_user("hr-system-admin", role="ADM")
        cls.system_admin.is_superuser = cls.system_admin.is_staff = True
        cls.system_admin.save(update_fields=["is_superuser", "is_staff"])
        cls.operator = make_user("hr-operator", role="FUNC")
        cls.operator.is_staff = True
        cls.operator.save(update_fields=["is_staff"])
        cls.employee_user = make_user("hr-person", role="FUNC")
        cls.employee_user.first_name = "Pessoa"
        cls.employee_user.last_name = "Sintética HR"
        cls.employee_user.save(update_fields=["first_name", "last_name"])
        cls.other_user = make_user("hr-other", role="FUNC")
        cls.permissions = Permission.objects.filter(
            content_type__app_label="hr",
            codename__in=["view_employee", "add_employee", "change_employee"],
        )
        cls.operator.user_permissions.add(*cls.permissions)
        cls.employee = Employee.objects.create(
            user=cls.employee_user,
            department="Setor sintético HR",
            job_title="Função sintética HR",
        )
        cls.list_url = reverse("hr:employee_list")
        cls.detail_url = reverse("hr:employee_detail", args=[cls.employee.pk])
        cls.add_url = reverse("admin:hr_employee_add")
        cls.change_url = reverse("admin:hr_employee_change", args=[cls.employee.pk])

    def setUp(self):
        self.client.force_login(self.operator)

    def test_model_validation_trim_unique_protect_and_no_delete(self):
        item = Employee.objects.create(
            user=self.other_user, department="  Unidade  ", job_title="  Analista  "
        )
        self.assertEqual((item.department, item.job_title), ("Unidade", "Analista"))
        for field in ("department", "job_title"):
            data = {"department": "Setor", "job_title": "Função", field: "   "}
            with self.subTest(field=field), self.assertRaises(ValidationError):
                Employee.objects.create(user=make_user(f"empty-{field}", role="FUNC"), **data)
        with self.assertRaises(ValidationError):
            Employee.objects.create(user=self.employee_user, department="Outro", job_title="Outra")
        with self.assertRaises(ValidationError):
            self.employee.delete()
        with self.assertRaises(ProtectedError):
            self.employee_user.delete()
        self.assertEqual(str(self.employee), f"Cadastro funcional {self.employee.pk}")

    def test_admin_create_uses_only_eligible_unlinked_users(self):
        inactive = make_user("hr-inactive", role="FUNC")
        inactive.is_active = False
        inactive.save(update_fields=["is_active"])
        client_user = make_user("hr-client", role="CLI")
        response = self.client.get(self.add_url)
        choices = response.context["adminform"].form.fields["user"].queryset
        self.assertIn(self.other_user, choices)
        for excluded in (self.employee_user, inactive, client_user):
            self.assertNotIn(excluded, choices)
        self.assertNotContains(response, self.employee_user.email)
        response = self.client.post(
            self.add_url,
            {
                "user": self.other_user.pk,
                "department": "  Suprimentos  ",
                "job_title": "  Assistente  ",
                "active": "on",
                "_save": "Salvar",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = Employee.objects.get(user=self.other_user)
        self.assertEqual((created.department, created.job_title), ("Suprimentos", "Assistente"))
        self.assertTrue(
            AdminLogEntry.objects.filter(object_id=str(created.pk), user=self.operator).exists()
        )

    def test_admin_edit_cannot_replace_user_or_delete(self):
        original_security = (
            self.employee_user.is_active,
            self.employee_user.nivel_permissao,
            self.employee_user.is_staff,
            self.employee_user.is_superuser,
            set(self.employee_user.user_permissions.values_list("pk", flat=True)),
        )
        response = self.client.post(
            self.change_url,
            {
                "user": self.other_user.pk,
                "department": "Novo setor",
                "job_title": "Nova função",
                "active": "",
                "_save": "Salvar",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.employee.refresh_from_db()
        self.employee_user.refresh_from_db()
        self.assertEqual(self.employee.user, self.employee_user)
        self.assertEqual(
            (self.employee.department, self.employee.job_title, self.employee.active),
            ("Novo setor", "Nova função", False),
        )
        self.assertEqual(
            original_security,
            (
                self.employee_user.is_active,
                self.employee_user.nivel_permissao,
                self.employee_user.is_staff,
                self.employee_user.is_superuser,
                set(self.employee_user.user_permissions.values_list("pk", flat=True)),
            ),
        )
        self.assertEqual(
            self.client.get(
                reverse("admin:hr_employee_delete", args=[self.employee.pk])
            ).status_code,
            403,
        )
        request = RequestFactory().get("/")
        request.user = self.operator
        self.assertNotIn("delete_selected", admin.site._registry[Employee].get_actions(request))

    def test_profile_status_is_independent_and_history_remains_visible(self):
        self.employee.active = False
        self.employee.save()
        self.employee_user.is_active = False
        self.employee_user.nivel_permissao = "CLI"
        self.employee_user.first_name = "Nome atual"
        self.employee_user.save(update_fields=["is_active", "nivel_permissao", "first_name"])
        response = self.client.get(self.detail_url)
        self.assertContains(response, "Nome atual Sintética HR")
        self.assertContains(response, "Cadastro: inativo")
        self.assertEqual(self.client.get(self.change_url).status_code, 200)

    def test_permissions_roles_and_revocation(self):
        viewer = make_user("hr-viewer", role="FUNC")
        viewer.user_permissions.add(self.permissions.get(codename="view_employee"))
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.list_url).status_code, 200)
        self.assertEqual(self.client.get(self.detail_url).status_code, 200)
        self.assertEqual(self.client.get(self.add_url).status_code, 302)
        viewer.user_permissions.clear()
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        client_user = make_user("hr-capable-client", role="CLI")
        client_user.user_permissions.add(self.permissions.get(codename="view_employee"))
        self.client.force_login(client_user)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        admin_user = make_user("hr-adm-no-cap", role="ADM")
        admin_user.is_staff = True
        admin_user.save(update_fields=["is_staff"])
        self.client.force_login(admin_user)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)

    def test_read_audit_failure_blocks_personal_content(self):
        with patch(
            "apps.admin.hr.views.accessed.send", side_effect=DatabaseError("audit unavailable")
        ):
            for url in (self.list_url, self.detail_url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 503)
                self.assertNotContains(response, self.employee_user.username, status_code=503)
                self.assertNotContains(response, self.employee.department, status_code=503)

    def test_admin_audit_failures_roll_back_create_and_update(self):
        self.client.get(self.add_url)  # inicializa o inventário de sessão antes do mock global
        with patch(
            "auditlog.models.LogEntry.objects.create",
            side_effect=IntegrityError("audit unavailable"),
        ):
            response = self.client.post(
                self.add_url,
                {
                    "user": self.other_user.pk,
                    "department": "Secret",
                    "job_title": "Private",
                    "active": "on",
                    "_save": "Salvar",
                },
            )
        self.assertEqual(response.status_code, 503)
        self.assertFalse(Employee.objects.filter(user=self.other_user).exists())
        with patch(
            "django.contrib.admin.models.LogEntry.save",
            side_effect=DatabaseError("log unavailable"),
        ):
            response = self.client.post(
                self.change_url,
                {
                    "department": "Changed",
                    "job_title": "Changed",
                    "active": "on",
                    "_save": "Salvar",
                },
            )
        self.assertEqual(response.status_code, 503)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.department, "Setor sintético HR")

    def test_pagination_audits_only_visible_records_without_n_plus_one(self):
        for index in range(26):
            Employee.objects.create(
                user=make_user(f"hr-page-{index}", role="FUNC"),
                department="Setor",
                job_title="Função",
            )
        AuditLogEntry.objects.filter(
            content_type__app_label="hr", action=AuditLogEntry.Action.ACCESS
        ).delete()
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.list_url)
        self.assertEqual(len(response.context["page_obj"]), 25)
        self.assertEqual(
            AuditLogEntry.objects.filter(
                content_type__app_label="hr", action=AuditLogEntry.Action.ACCESS
            ).count(),
            25,
        )
        joined = [
            q
            for q in queries
            if q["sql"].startswith("SELECT") and 'JOIN "aegis_share_customuser"' in q["sql"]
        ]
        self.assertEqual(len(joined), 1)
        self.assertEqual(len(self.client.get(self.list_url, {"page": 2}).context["page_obj"]), 2)

    def test_audit_minimizes_identity_and_functional_text(self):
        self.client.get(self.detail_url)
        logs = AuditLogEntry.objects.filter(content_type__app_label="hr")
        serialized = str(list(logs.values("changes", "object_repr", "additional_data")))
        for marker in (
            self.employee_user.username,
            self.employee_user.first_name,
            self.employee.department,
            self.employee.job_title,
        ):
            self.assertNotIn(marker, serialized)
        for action in (AuditLogEntry.Action.CREATE, AuditLogEntry.Action.ACCESS):
            self.assertTrue(logs.filter(object_pk=str(self.employee.pk), action=action).exists())

    def test_privacy_headers_csrf_methods_missing_and_redirects(self):
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.operator)
        responses = [
            self.client.get(self.list_url),
            self.client.post(self.list_url),
            self.client.get(reverse("hr:employee_detail", args=[uuid.uuid4()])),
            csrf.post(self.change_url, {"department": "X"}),
        ]
        self.client.logout()
        responses.append(self.client.get(self.list_url))
        self.assertEqual(
            [response.status_code for response in responses], [200, 405, 404, 403, 302]
        )
        for response in responses:
            self.assertEqual(response["Cache-Control"], "private, no-store")
            self.assertIn("Cookie", response["Vary"])
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")
