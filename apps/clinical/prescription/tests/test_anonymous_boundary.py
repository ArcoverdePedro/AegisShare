from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ..models import Drug, Lot, StockItem

User = get_user_model()

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES)
class AnonymousRxBoundaryTests(TestCase):
    def setUp(self):
        User.objects.create_superuser(
            username="rx-anonymous-boundary-admin",
            password="test-password",
            nivel_permissao="ADM",
        )
        self.drug = Drug.objects.create(
            code="RX-ANON-BOUNDARY",
            name="Medicamento Sentinela Anônimo",
            presentation="Apresentação sigilosa sintética",
            dispense_unit="unidade",
        )
        self.stock = StockItem.objects.create(
            drug=self.drug,
            storage_location="Farmácia Sentinela Anônima",
            minimum_level=Decimal("1"),
        )
        self.lot = Lot.objects.create(
            stock_item=self.stock,
            lot_number="ANON-LOT-SECRET",
            expires_on=timezone.localdate() + timedelta(days=30),
            quantity_available=Decimal("5"),
        )

    def test_current_rx_surfaces_redirect_anonymous_user_without_data_leak(self):
        paths = [
            reverse("prescription:drug_catalog"),
            reverse("prescription:drug_create"),
            reverse("prescription:drug_update", kwargs={"pk": self.drug.pk}),
            reverse("prescription:pharmacy_stock"),
        ]
        forbidden_markers = [
            self.drug.code,
            self.drug.name,
            self.drug.presentation,
            self.stock.storage_location,
            self.lot.lot_number,
        ]

        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path, follow=True)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.redirect_chain)
                redirect_url, redirect_status = response.redirect_chain[0]
                self.assertEqual(redirect_status, 302)
                self.assertTrue(redirect_url.startswith("/login/?next="))
                self.assertEqual(response.resolver_match.url_name, "login")

                body = response.content.decode("utf-8")
                for marker in forbidden_markers:
                    self.assertNotIn(marker, body)
