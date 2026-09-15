from datetime import timedelta
from decimal import Decimal

from auditlog.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
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
class DeniedAccessAuditTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="rx-denied-audit-admin",
            password="test-password",
            nivel_permissao="ADM",
        )
        self.denied = User.objects.create_user(
            username="rx-denied-audit-client",
            password="test-password",
            nivel_permissao="CLI",
        )
        permissions = Permission.objects.filter(
            content_type__app_label="prescription",
            codename__in={
                "view_drug",
                "manage_drug_catalog",
                "view_pharmacy_stock",
                "manage_pharmacy_stock",
            },
        )
        self.denied.user_permissions.set(permissions)

        self.drug = Drug.objects.create(
            code="RX-DENIED-AUDIT",
            name="Medicamento Sintético Negado",
            presentation="Apresentação sintética",
            dispense_unit="unidade",
        )
        self.stock = StockItem.objects.create(
            drug=self.drug,
            storage_location="Farmácia negação auditoria",
            minimum_level=Decimal("1"),
        )
        self.lot = Lot.objects.create(
            stock_item=self.stock,
            lot_number="DENIED-AUDIT-LOT",
            expires_on=timezone.localdate() + timedelta(days=30),
            quantity_available=Decimal("5"),
        )
        self.client.force_login(self.denied)

    def _rx_log_entries_for_denied_actor(self):
        content_types = [
            ContentType.objects.get_for_model(model)
            for model in (Drug, StockItem, Lot)
        ]
        return LogEntry.objects.filter(
            actor=self.denied,
            content_type__in=content_types,
        )

    def test_denied_gets_do_not_create_false_read_audit_entries(self):
        paths = [
            reverse("prescription:drug_catalog"),
            reverse("prescription:drug_create"),
            reverse("prescription:drug_update", kwargs={"pk": self.drug.pk}),
            reverse("prescription:pharmacy_stock"),
        ]

        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 403)

        self.assertFalse(
            self._rx_log_entries_for_denied_actor().filter(
                action=LogEntry.Action.ACCESS,
            ).exists()
        )

    def test_denied_catalog_posts_do_not_mutate_or_create_write_audit_entries(self):
        create_response = self.client.post(
            reverse("prescription:drug_create"),
            data={
                "code": "RX-DENIED-CREATE",
                "name": "Medicamento que não pode existir",
                "presentation": "Apresentação sintética",
                "strength_text": "",
                "route_hint": "",
                "dispense_unit": "unidade",
                "active": "on",
            },
        )
        self.assertEqual(create_response.status_code, 403)
        self.assertFalse(Drug.objects.filter(code="RX-DENIED-CREATE").exists())

        original_presentation = self.drug.presentation
        update_response = self.client.post(
            reverse("prescription:drug_update", kwargs={"pk": self.drug.pk}),
            data={
                "code": self.drug.code,
                "name": self.drug.name,
                "presentation": "Apresentação indevidamente alterada",
                "strength_text": self.drug.strength_text,
                "route_hint": self.drug.route_hint,
                "dispense_unit": self.drug.dispense_unit,
                "active": "on",
            },
        )
        self.assertEqual(update_response.status_code, 403)
        self.drug.refresh_from_db()
        self.assertEqual(self.drug.presentation, original_presentation)

        self.assertFalse(
            self._rx_log_entries_for_denied_actor().filter(
                action__in=(LogEntry.Action.CREATE, LogEntry.Action.UPDATE),
            ).exists()
        )
