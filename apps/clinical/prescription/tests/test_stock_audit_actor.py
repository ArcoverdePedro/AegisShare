from datetime import timedelta
from decimal import Decimal

from auditlog.models import LogEntry
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from aegis_share.tests.helpers import make_user

from ..models import Drug, StockMovement
from ..stock_services import adjust_stock, create_lot, create_stock_item


class PharmacyStockAuditActorTests(TestCase):
    def setUp(self):
        self.manager = make_user("rx-stock-audit-actor", role="FUNC")
        permission = Permission.objects.get(
            codename="manage_pharmacy_stock",
            content_type__app_label="prescription",
        )
        self.manager.user_permissions.add(permission)
        self.drug = Drug.objects.create(
            code="RX-STOCK-AUDIT-ACTOR",
            name="Medicamento Sintético Ator",
            presentation="Apresentação sintética",
            dispense_unit="unidade",
        )

    def _create_entry(self, instance):
        content_type = ContentType.objects.get_for_model(instance.__class__)
        return LogEntry.objects.filter(
            content_type=content_type,
            object_pk=str(instance.pk),
            action=LogEntry.Action.CREATE,
        ).latest("timestamp")

    def assert_create_actor(self, instance):
        self.assertEqual(self._create_entry(instance).actor, self.manager)

    def test_stock_service_writes_are_attributed_to_explicit_actor(self):
        stock = create_stock_item(
            actor=self.manager,
            drug_id=self.drug.pk,
            storage_location="Farmácia ator",
            minimum_level=Decimal("2"),
        )
        lot = create_lot(
            actor=self.manager,
            stock_item_id=stock.pk,
            lot_number="LOTE-ATOR-1",
            expires_on=timezone.localdate() + timedelta(days=30),
            initial_quantity=Decimal("5"),
        )
        receipt = StockMovement.objects.get(
            lot=lot,
            movement_type=StockMovement.Type.RECEIPT,
        )
        adjustment = adjust_stock(
            lot_id=lot.pk,
            actor=self.manager,
            quantity_delta=Decimal("-1"),
            reason="Ajuste sintético de auditoria",
        )

        for instance in (stock, lot, receipt, adjustment):
            with self.subTest(model=instance.__class__.__name__):
                self.assert_create_actor(instance)

    def test_stock_service_actor_context_does_not_leak_to_later_writes(self):
        create_stock_item(
            actor=self.manager,
            drug_id=self.drug.pk,
            storage_location="Farmácia escopo",
            minimum_level=Decimal("1"),
        )

        outside_context = Drug.objects.create(
            code="RX-STOCK-AUDIT-OUTSIDE",
            name="Medicamento Fora do Contexto de Estoque",
            presentation="Apresentação sintética",
            dispense_unit="unidade",
        )

        self.assertIsNone(self._create_entry(outside_context).actor)
