from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.utils import timezone

from aegis_share.tests.helpers import make_user

from ..models import Drug, Lot, StockItem, StockMovement


class PharmacyStockIdentityDatabaseGuardTests(TestCase):
    def setUp(self):
        self.actor = make_user("rx-stock-identity-db", role="ADM")
        self.drug_a = Drug.objects.create(
            code="RX-STOCK-IDENTITY-A",
            name="Medicamento Sintético Estoque A",
            presentation="Apresentação sintética A",
            dispense_unit="unidade",
        )
        self.drug_b = Drug.objects.create(
            code="RX-STOCK-IDENTITY-B",
            name="Medicamento Sintético Estoque B",
            presentation="Apresentação sintética B",
            dispense_unit="unidade",
        )
        self.stock_item = StockItem.objects.create(
            drug=self.drug_a,
            storage_location="Farmácia Sintética A",
            minimum_level=Decimal("1"),
        )
        self.lot = Lot.objects.create(
            stock_item=self.stock_item,
            lot_number="LOT-IDENTITY-001",
            expires_on=timezone.localdate() + timedelta(days=365),
            quantity_available=Decimal("1"),
        )
        StockMovement.objects.create(
            lot=self.lot,
            movement_type=StockMovement.Type.RECEIPT,
            quantity_delta=Decimal("1"),
            actor=self.actor,
        )
        if connection.vendor != "postgresql":
            self.skipTest("Os guards desta suíte são específicos do PostgreSQL.")

    def test_bulk_update_cannot_rewrite_stock_item_drug_after_lot_exists(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            StockItem.objects.filter(pk=self.stock_item.pk).update(drug=self.drug_b)

        self.stock_item.refresh_from_db()
        self.assertEqual(self.stock_item.drug_id, self.drug_a.pk)

    def test_raw_sql_cannot_rewrite_stock_item_location_after_lot_exists(self):
        table = connection.ops.quote_name(StockItem._meta.db_table)

        with self.assertRaises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {table} SET storage_location = %s WHERE id = %s",
                ["Localização reescrita", self.stock_item.pk],
            )

        self.stock_item.refresh_from_db()
        self.assertEqual(self.stock_item.storage_location, "Farmácia Sintética A")

    def test_bulk_update_cannot_rewrite_lot_identity_after_movement(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Lot.objects.filter(pk=self.lot.pk).update(lot_number="LOT-REWRITTEN")

        self.lot.refresh_from_db()
        self.assertEqual(self.lot.lot_number, "LOT-IDENTITY-001")

    def test_raw_sql_cannot_rewrite_lot_expiry_after_movement(self):
        table = connection.ops.quote_name(Lot._meta.db_table)
        rewritten_expiry = self.lot.expires_on + timedelta(days=30)

        with self.assertRaises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {table} SET expires_on = %s WHERE id = %s",
                [rewritten_expiry, self.lot.pk],
            )

        self.lot.refresh_from_db()
        self.assertNotEqual(self.lot.expires_on, rewritten_expiry)

    def test_stock_item_without_lots_can_change_identity(self):
        stock_item = StockItem.objects.create(
            drug=self.drug_a,
            storage_location="Farmácia Sintética Editável",
        )

        updated = StockItem.objects.filter(pk=stock_item.pk).update(
            drug=self.drug_b,
            storage_location="Farmácia Sintética Editada",
        )

        self.assertEqual(updated, 1)
        stock_item.refresh_from_db()
        self.assertEqual(stock_item.drug_id, self.drug_b.pk)
        self.assertEqual(stock_item.storage_location, "Farmácia Sintética Editada")

    def test_lot_without_movements_can_change_identity(self):
        other_stock = StockItem.objects.create(
            drug=self.drug_b,
            storage_location="Farmácia Sintética B",
        )
        lot = Lot.objects.create(
            stock_item=self.stock_item,
            lot_number="LOT-EDITABLE",
            expires_on=timezone.localdate() + timedelta(days=180),
        )
        new_expiry = lot.expires_on + timedelta(days=30)

        updated = Lot.objects.filter(pk=lot.pk).update(
            stock_item=other_stock,
            lot_number="LOT-EDITED",
            expires_on=new_expiry,
        )

        self.assertEqual(updated, 1)
        lot.refresh_from_db()
        self.assertEqual(lot.stock_item_id, other_stock.pk)
        self.assertEqual(lot.lot_number, "LOT-EDITED")
        self.assertEqual(lot.expires_on, new_expiry)
