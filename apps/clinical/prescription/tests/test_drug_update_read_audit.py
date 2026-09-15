from auditlog.models import LogEntry
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse

from aegis_share.tests.helpers import make_user

from ..models import Drug

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES)
class DrugUpdateReadAuditTests(TestCase):
    def setUp(self):
        self.admin = make_user("rx-update-read-audit-admin", role="ADM")
        self.admin.is_superuser = True
        self.admin.is_staff = True
        self.admin.save(update_fields=["is_superuser", "is_staff"])

        self.manager = make_user("rx-update-read-audit-manager", role="FUNC")
        permissions = Permission.objects.filter(
            content_type__app_label="prescription",
            codename__in={"view_drug", "manage_drug_catalog"},
        )
        self.manager.user_permissions.add(*permissions)
        self.drug = Drug.objects.create(
            code="RX-UPDATE-READ-AUDIT",
            name="Medicamento Sintético Formulário",
            presentation="Apresentação sintética",
            dispense_unit="unidade",
        )
        self.client.force_login(self.manager)

    def test_update_form_audits_rendered_drug_once_for_authenticated_actor(self):
        response = self.client.get(
            reverse("prescription:drug_update", kwargs={"pk": self.drug.pk})
        )

        self.assertEqual(response.status_code, 200)
        content_type = ContentType.objects.get_for_model(Drug)
        entries = LogEntry.objects.filter(
            content_type=content_type,
            object_pk=str(self.drug.pk),
            action=LogEntry.Action.ACCESS,
            actor=self.manager,
        )
        self.assertEqual(entries.count(), 1)
