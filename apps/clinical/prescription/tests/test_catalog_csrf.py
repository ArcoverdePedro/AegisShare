from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import Drug

User = get_user_model()

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES)
class DrugCatalogCsrfTests(TestCase):
    def setUp(self):
        User.objects.create_superuser(
            username="rx-csrf-admin",
            password="test-password",
            nivel_permissao="ADM",
        )
        self.manager = User.objects.create_user(
            username="rx-csrf-manager",
            password="test-password",
            nivel_permissao="FUNC",
        )
        permissions = Permission.objects.filter(
            content_type__app_label="prescription",
            codename__in={"view_drug", "manage_drug_catalog"},
        )
        self.manager.user_permissions.set(permissions)
        self.drug = Drug.objects.create(
            code="RX-CSRF-EXISTING",
            name="Medicamento Sintético CSRF",
            presentation="Apresentação original",
            dispense_unit="unidade",
        )
        self.csrf_client = Client(enforce_csrf_checks=True)
        self.csrf_client.force_login(self.manager)

    def test_create_without_csrf_is_rejected_before_mutation(self):
        response = self.csrf_client.post(
            reverse("prescription:drug_create"),
            data={
                "code": "RX-CSRF-FORGED",
                "name": "Medicamento Forjado",
                "presentation": "Apresentação forjada",
                "strength_text": "",
                "route_hint": "",
                "dispense_unit": "unidade",
                "active": "on",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Drug.objects.filter(code="RX-CSRF-FORGED").exists())

    def test_update_without_csrf_is_rejected_before_mutation(self):
        response = self.csrf_client.post(
            reverse("prescription:drug_update", kwargs={"pk": self.drug.pk}),
            data={
                "code": self.drug.code,
                "name": self.drug.name,
                "presentation": "Apresentação alterada por requisição forjada",
                "strength_text": self.drug.strength_text,
                "route_hint": self.drug.route_hint,
                "dispense_unit": self.drug.dispense_unit,
                "active": "on",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.drug.refresh_from_db()
        self.assertEqual(self.drug.presentation, "Apresentação original")
