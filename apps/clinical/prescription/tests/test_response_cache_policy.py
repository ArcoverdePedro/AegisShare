from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from aegis_share.tests.helpers import make_user

from ..models import Drug
from .surface_contract import RX_GET_SURFACE_NAMES

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES)
class PrescriptionResponseCachePolicyTests(TestCase):
    def setUp(self):
        self.admin = make_user("rx-cache-admin", role="ADM")
        self.admin.is_superuser = True
        self.admin.is_staff = True
        self.admin.save(update_fields=["is_superuser", "is_staff"])

        self.user = make_user("rx-cache-user", role="FUNC")
        self._grant_permissions(
            "view_drug",
            "manage_drug_catalog",
            "view_pharmacy_stock",
        )
        self.drug = Drug.objects.create(
            code="RX-CACHE-001",
            name="Medicamento Sintético Cache",
            presentation="Apresentação sintética",
            dispense_unit="unidade",
        )
        self.client.force_login(self.user)

    def _grant_permissions(self, *codenames):
        permissions = Permission.objects.filter(
            content_type__app_label="prescription",
            codename__in=codenames,
        )
        self.user.user_permissions.add(*permissions)
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            if hasattr(self.user, cache_name):
                delattr(self.user, cache_name)

    def assert_private_no_store(self, response):
        self.assertEqual(response.status_code, 200)
        cache_control = {
            directive.strip()
            for directive in response["Cache-Control"].split(",")
        }
        self.assertEqual(cache_control, {"private", "no-store", "max-age=0"})

        vary = {value.strip().lower() for value in response["Vary"].split(",")}
        self.assertIn("cookie", vary)
        self.assertIn("hx-request", vary)

    def test_every_reviewed_rx_get_surface_is_private_and_no_store(self):
        routes = {
            "drug_catalog": reverse("prescription:drug_catalog"),
            "drug_create": reverse("prescription:drug_create"),
            "drug_update": reverse(
                "prescription:drug_update",
                kwargs={"pk": self.drug.pk},
            ),
            "pharmacy_stock": reverse("prescription:pharmacy_stock"),
        }
        self.assertEqual(set(routes), RX_GET_SURFACE_NAMES)

        for name, route in routes.items():
            with self.subTest(name=name, route=route):
                self.assert_private_no_store(self.client.get(route))
