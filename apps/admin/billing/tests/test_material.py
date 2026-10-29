import uuid
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings

from apps.admin.inventory.models import InventoryItem, StockLocation
from apps.admin.inventory.services import InventoryConflict, record_movement, reverse_movement
from apps.clinical.pep.models import Encounter
from apps.clinical.pep.tests.test_views import TEST_STORAGES

from ..models import BillingItem, HospitalAccount
from ..services import (
    BillingConflict,
    billing_divergences,
    capture_material,
    pending_material_movements,
    reverse_item,
)
from ..totals import account_total
from . import test_capture


@override_settings(STORAGES=TEST_STORAGES, SECURE_SSL_REDIRECT=False)
class MaterialConsumptionTests(TestCase):
    def setUp(self):
        test_capture.ProductionCaptureTests.setUp(self)
        self.nurse.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="inventory",
                codename__in=["view_requisitions", "move_stock", "adjust_stock"],
            )
        )
        self.item = InventoryItem.objects.create(code="CAT", name="Cateter", unit="un")
        self.location = StockLocation.objects.create(code="POSTO", name="Posto")
        self.move("RECEIPT", 10)

    def move(self, kind, quantity, **extra):
        return record_movement(
            user=self.nurse,
            kind=kind,
            item=self.item,
            location=self.location,
            quantity=quantity,
            operation_key=uuid.uuid4(),
            **extra,
        )

    def test_consumption_bills_once_and_stock_reversal_is_flagged(self):
        used = self.move("ISSUE", 3, encounter=self.encounter)
        self.assertEqual(pending_material_movements(self.account), [used])

        billed = capture_material(
            user=self.nurse,
            account_id=self.account.pk,
            movement_id=used.pk,
            unit_price=Decimal("2.00"),
            operation_key=uuid.uuid4(),
        )
        self.assertEqual((billed.quantity, account_total(self.account)), (3, Decimal("6.00")))
        with self.assertRaises(BillingConflict):
            capture_material(
                user=self.nurse,
                account_id=self.account.pk,
                movement_id=used.pk,
                unit_price=Decimal("2.00"),
                operation_key=uuid.uuid4(),
            )

        reverse_movement(
            user=self.nurse, movement=used, reason="Não utilizado", operation_key=uuid.uuid4()
        )
        self.assertEqual(billing_divergences(self.account), [billed])
        self.assertEqual(pending_material_movements(self.account), [])
        reverse_item(
            user=self.nurse,
            item_id=billed.pk,
            justification="Estorno de estoque",
            operation_key=uuid.uuid4(),
        )
        self.assertEqual(billing_divergences(self.account), [])
        self.assertEqual(account_total(self.account), Decimal("0.00"))
        self.assertEqual(BillingItem.objects.count(), 2)

    def test_consumption_requires_open_encounter_and_issue(self):
        with self.assertRaises(InventoryConflict):
            self.move("RECEIPT", 1, encounter=self.encounter)
        closed = Encounter.objects.create(
            patient=self.patient,
            status=Encounter.Status.CANCELLED,
            responsible_professional=self.nurse,
            created_by=self.nurse,
        )
        with self.assertRaises(InventoryConflict):
            self.move("ISSUE", 1, encounter=closed)
        other_account = HospitalAccount.objects.create(
            encounter=closed, opened_by=self.nurse, operation_key=uuid.uuid4()
        )
        self.assertEqual(pending_material_movements(other_account), [])
