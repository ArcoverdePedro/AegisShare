from datetime import timedelta
from decimal import Decimal

from auditlog.models import LogEntry
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from aegis_share.tests.helpers import make_user

from ..models import Drug, Lot, StockItem

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES)
class PharmacyStockPaginationAuditTests(TestCase):
    def setUp(self):
        self.admin = make_user("rx-stock-page-audit-admin", role="ADM")
        self.admin.is_superuser = True
        self.admin.is_staff = True
        self.admin.save(update_fields=["is_superuser", "is_staff"])

        self.viewer = make_user("rx-stock-page-audit-viewer", role="FUNC")
        permission = Permission.objects.get(
            codename="view_pharmacy_stock",
            content_type__app_label="prescription",
        )
        self.viewer.user_permissions.add(permission)

        expires_on = timezone.localdate() + timedelta(days=90)
        for index in range(31):
            drug = Drug.objects.create(
                code=f"RX-STOCK-PAGE-{index:02d}",
                name=f"Medicamento Estoque Paginação {index:02d}",
                presentation="Apresentação sintética",
                dispense_unit="unidade",
            )
            stock = StockItem.objects.create(
                drug=drug,
                storage_location="Farmácia paginação",
                minimum_level=Decimal("1"),
            )
            Lot.objects.create(
                stock_item=stock,
                lot_number=f"PAGE-LOT-{index:02d}",
                expires_on=expires_on,
                quantity_available=Decimal("5"),
            )

    def test_only_stock_and_lots_rendered_on_current_page_are_audited(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("prescription:pharmacy_stock"))

        self.assertEqual(response.status_code, 200)
        visible_stock_ids = {stock.pk for stock in response.context["stock_items"]}
        self.assertEqual(len(visible_stock_ids), 30)

        outside_stock = StockItem.objects.exclude(pk__in=visible_stock_ids).get()
        outside_lot = outside_stock.lots.get()

        stock_content_type = ContentType.objects.get_for_model(StockItem)
        lot_content_type = ContentType.objects.get_for_model(Lot)
        stock_access = LogEntry.objects.filter(
            content_type=stock_content_type,
            action=LogEntry.Action.ACCESS,
            actor=self.viewer,
        )
        lot_access = LogEntry.objects.filter(
            content_type=lot_content_type,
            action=LogEntry.Action.ACCESS,
            actor=self.viewer,
        )

        self.assertEqual(stock_access.count(), 30)
        self.assertEqual(lot_access.count(), 30)
        self.assertFalse(stock_access.filter(object_pk=str(outside_stock.pk)).exists())
        self.assertFalse(lot_access.filter(object_pk=str(outside_lot.pk)).exists())

        second_page = self.client.get(reverse("prescription:pharmacy_stock") + "?page=2")

        self.assertEqual(second_page.status_code, 200)
        self.assertTrue(
            LogEntry.objects.filter(
                content_type=stock_content_type,
                object_pk=str(outside_stock.pk),
                action=LogEntry.Action.ACCESS,
                actor=self.viewer,
            ).exists()
        )
        self.assertTrue(
            LogEntry.objects.filter(
                content_type=lot_content_type,
                object_pk=str(outside_lot.pk),
                action=LogEntry.Action.ACCESS,
                actor=self.viewer,
            ).exists()
        )
