import uuid

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Sum
from django.test import TestCase, override_settings
from django.urls import reverse

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.tests.test_views import TEST_STORAGES

from ..models import InventoryItem, MaterialBalance, MaterialMovement, StockLocation
from ..services import (
    InventoryConflict,
    delivered_quantity,
    record_movement,
    request_material,
    reverse_movement,
)


@override_settings(STORAGES=TEST_STORAGES, SECURE_SSL_REDIRECT=False)
class StockLedgerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        def perms(*codenames):
            return Permission.objects.filter(
                content_type__app_label="inventory", codename__in=codenames
            )

        admin = make_user("stock-admin", role="ADM")
        admin.is_superuser = True
        admin.save(update_fields=["is_superuser"])
        cls.keeper = make_user("stock-keeper", role="FUNC")
        cls.keeper.user_permissions.add(
            *perms("view_requisitions", "request_material", "move_stock")
        )
        cls.auditor = make_user("stock-auditor", role="FUNC")
        cls.auditor.user_permissions.add(*perms("view_requisitions", "adjust_stock"))
        cls.viewer = make_user("stock-viewer", role="FUNC")
        cls.viewer.user_permissions.add(*perms("view_requisitions"))
        cls.client_user = make_user("stock-client")
        cls.item = InventoryItem.objects.create(code="LUV", name="Luva sintética", unit="par")
        cls.main = StockLocation.objects.create(code="ALM", name="Almoxarifado")
        cls.ward = StockLocation.objects.create(code="UTI", name="Posto UTI")

    def move(self, kind, quantity, *, user=None, location=None, **extra):
        return record_movement(
            user=user or self.keeper,
            kind=kind,
            item=self.item,
            location=location or self.main,
            quantity=quantity,
            operation_key=extra.pop("operation_key", uuid.uuid4()),
            **extra,
        )

    def assert_ledger_reconciles(self):
        for balance in MaterialBalance.objects.all():
            total = balance.movements.aggregate(total=Sum("quantity_delta"))["total"] or 0
            self.assertEqual(balance.quantity, total)

    def test_receipt_issue_and_transfer_reconcile(self):
        self.move("RECEIPT", 10, lot="L1")
        self.move("ISSUE", 3, lot="L1")
        self.move("TRANSFER", 4, lot="L1", to_location=self.ward)

        balances = {
            b.location.code: b.quantity for b in MaterialBalance.objects.select_related("location")
        }
        self.assertEqual(balances, {"ALM": 3, "UTI": 4})
        self.assert_ledger_reconciles()

    def test_issue_beyond_balance_is_refused_without_side_effect(self):
        self.move("RECEIPT", 2)

        with self.assertRaises(InventoryConflict):
            self.move("ISSUE", 3)
        with self.assertRaises(InventoryConflict):
            self.move("ISSUE", 1, lot="OUTRO")
        self.assertEqual(MaterialBalance.objects.get().quantity, 2)

    def test_requisition_is_not_delivery_and_supports_partial_fulfillment(self):
        requisition = request_material(
            user=self.keeper, item=self.item, quantity=5, operation_key=uuid.uuid4(), confirmed=True
        )
        self.assertEqual(delivered_quantity(requisition), 0)
        self.move("RECEIPT", 10)

        self.move("ISSUE", 2, requisition=requisition)
        self.assertEqual(delivered_quantity(requisition), 2)
        with self.assertRaises(InventoryConflict):
            self.move("ISSUE", 4, requisition=requisition)
        self.move("RETURN", 1, requisition=requisition, reason="sobra")
        self.assertEqual(delivered_quantity(requisition), 1)
        with self.assertRaises(InventoryConflict):
            self.move("RETURN", 2, requisition=requisition, reason="erro")

    def test_adjustment_requires_capability_and_records_counted_difference(self):
        self.move("RECEIPT", 10)

        with self.assertRaises(PermissionDenied):
            self.move("ADJUSTMENT", 8, reason="contagem")
        adjustment = self.move("ADJUSTMENT", 8, user=self.auditor, reason="contagem")
        self.assertEqual(adjustment.quantity_delta, -2)
        with self.assertRaises(InventoryConflict):
            self.move("ADJUSTMENT", 8, user=self.auditor, reason="recontagem")

    def test_reversal_preserves_origin_and_undoes_both_transfer_legs(self):
        self.move("RECEIPT", 5)
        transfer = self.move("TRANSFER", 5, to_location=self.ward)
        key = uuid.uuid4()

        reversal = reverse_movement(
            user=self.auditor, movement=transfer, reason="erro", operation_key=key
        )

        self.assertEqual(reversal.operation_key, key)
        self.assertEqual(MaterialMovement.objects.filter(kind="REVERSAL").count(), 2)
        self.assertEqual(
            {
                b.location.code: b.quantity
                for b in MaterialBalance.objects.select_related("location")
            },
            {"ALM": 5, "UTI": 0},
        )
        self.assertEqual(
            reverse_movement(
                user=self.auditor, movement=transfer, reason="erro", operation_key=key
            ),
            reversal,
        )
        with self.assertRaises(InventoryConflict):
            reverse_movement(
                user=self.auditor, movement=transfer, reason="de novo", operation_key=uuid.uuid4()
            )
        with self.assertRaises(ValidationError):
            transfer.delete()
        self.assert_ledger_reconciles()

    def test_reversal_of_consumed_receipt_is_refused(self):
        receipt = self.move("RECEIPT", 2)
        self.move("ISSUE", 2)

        with self.assertRaises(InventoryConflict):
            reverse_movement(
                user=self.auditor, movement=receipt, reason="erro", operation_key=uuid.uuid4()
            )

    def test_same_key_with_other_item_conflicts(self):
        key = uuid.uuid4()
        self.move("RECEIPT", 2, operation_key=key)
        other = InventoryItem.objects.create(code="GAZ", name="Gaze", unit="pacote")

        with self.assertRaises(InventoryConflict):
            record_movement(
                user=self.keeper,
                kind="RECEIPT",
                item=other,
                location=self.main,
                quantity=2,
                operation_key=key,
            )

    def test_lot_expiry_cannot_diverge(self):
        self.move("RECEIPT", 2, lot="L1", expires_on="2027-01-31")
        with self.assertRaises(InventoryConflict):
            self.move("RECEIPT", 2, lot="L1", expires_on="2027-02-28")

    def test_http_flow_and_access_boundaries(self):
        self.client.force_login(self.keeper)
        data = {
            "kind": "RECEIPT",
            "item": self.item.pk,
            "location": self.main.pk,
            "quantity": 4,
            "lot": "  L9 ",
            "operation_key": uuid.uuid4(),
            "confirmed": True,
        }
        response = self.client.post(reverse("inventory:movement_create"), data)
        movement = MaterialMovement.objects.get()
        self.assertRedirects(response, reverse("inventory:movement_detail", args=[movement.pk]))
        self.assertEqual(movement.balance.lot, "L9")
        self.assertContains(self.client.get(reverse("inventory:balance_list")), "Luva sintética")

        response = self.client.post(
            reverse("inventory:movement_create"),
            {**data, "kind": "ISSUE", "quantity": 9, "operation_key": uuid.uuid4()},
        )
        self.assertEqual(response.status_code, 409)
        response = self.client.post(
            reverse("inventory:movement_create"),
            {**data, "kind": "ADJUSTMENT", "quantity": 1, "operation_key": uuid.uuid4()},
        )
        self.assertEqual(response.status_code, 200)  # motivo obrigatório
        self.assertEqual(
            self.client.post(
                reverse("inventory:movement_detail", args=[movement.pk]),
                {"reason": "x", "operation_key": uuid.uuid4()},
            ).status_code,
            403,
        )

        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse("inventory:movement_create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("inventory:movement_list")).status_code, 200)
        self.client.force_login(self.client_user)
        self.assertEqual(self.client.get(reverse("inventory:balance_list")).status_code, 403)
