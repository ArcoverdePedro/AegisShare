import uuid
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.tests.test_views import TEST_STORAGES

from ..models import (
    InventoryItem,
    MaterialBalance,
    MaterialMovement,
    PurchaseOrder,
    StockLocation,
    Supplier,
)
from ..services import (
    InventoryConflict,
    approve_purchase_order,
    cancel_purchase_order,
    create_purchase_order,
    receive_purchase,
)


def grant(user, *codenames):
    user.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="inventory", codename__in=codenames)
    )


@override_settings(STORAGES=TEST_STORAGES, SECURE_SSL_REDIRECT=False)
class PurchaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        admin = make_user("po-admin", role="ADM")
        admin.is_superuser = True
        admin.save(update_fields=["is_superuser"])
        cls.buyer = make_user("po-buyer", role="FUNC")
        cls.approver = make_user("po-approver", role="FUNC")
        cls.receiver = make_user("po-receiver", role="FUNC")
        grant(cls.buyer, "view_purchases", "request_purchase", "approve_purchase")
        grant(cls.approver, "view_purchases", "approve_purchase")
        grant(cls.receiver, "view_purchases", "receive_purchase")
        cls.supplier = Supplier.objects.create(
            document="00.000.000/0001-00", name="Fornecedor sintético"
        )
        cls.item = InventoryItem.objects.create(code="SER", name="Seringa sintética", unit="un")
        cls.location = StockLocation.objects.create(code="ALM", name="Almoxarifado")

    def order(self, quantity=10, price="1.50"):
        return create_purchase_order(
            user=self.buyer,
            supplier=self.supplier,
            notes="Reposição",
            operation_key=uuid.uuid4(),
            lines=[{"item": self.item, "quantity": quantity, "unit_price": Decimal(price)}],
        )

    def receive(self, line, quantity, *, key=None, price="1.50", user=None):
        return receive_purchase(
            user=user or self.receiver,
            line=line,
            location=self.location,
            quantity=quantity,
            unit_price=Decimal(price),
            invoice_number="123",
            operation_key=key or uuid.uuid4(),
        )

    def test_order_does_not_add_stock_and_receipt_adds_once(self):
        order = self.order()
        line = order.lines.get()
        self.assertFalse(MaterialBalance.objects.exists())
        with self.assertRaises(InventoryConflict):
            self.receive(line, 1)  # ainda não aprovado

        approve_purchase_order(user=self.approver, order=order)
        key = uuid.uuid4()
        first = self.receive(line, 4, key=key)
        self.assertEqual(self.receive(line, 4, key=key), first)

        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.Status.PARTIAL)
        self.assertEqual(MaterialBalance.objects.get().quantity, 4)
        self.assertEqual(MaterialMovement.objects.count(), 1)

        self.receive(line, 6)
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.Status.RECEIVED)
        self.assertEqual(MaterialBalance.objects.get().quantity, 10)

    def test_divergent_quantity_or_price_is_refused(self):
        order = self.order()
        approve_purchase_order(user=self.approver, order=order)
        line = order.lines.get()

        with self.assertRaises(InventoryConflict):
            self.receive(line, 11)
        with self.assertRaises(InventoryConflict):
            self.receive(line, 1, price="1.60")
        self.assertFalse(MaterialMovement.objects.exists())

    def test_segregation_of_duties(self):
        order = self.order()

        with self.assertRaises(InventoryConflict):
            approve_purchase_order(user=self.buyer, order=order)
        with self.assertRaises(PermissionDenied):
            approve_purchase_order(user=self.receiver, order=order)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PurchaseOrder.objects.filter(pk=order.pk).update(approved_by=self.buyer)
        approve_purchase_order(user=self.approver, order=order)
        with self.assertRaises(PermissionDenied):
            self.receive(order.lines.get(), 1, user=self.approver)

    def test_cancel_only_before_receipt(self):
        order = self.order()
        approve_purchase_order(user=self.approver, order=order)
        self.receive(order.lines.get(), 1)

        with self.assertRaises(InventoryConflict):
            cancel_purchase_order(user=self.approver, order=order, reason="desistência")
        other = self.order()
        cancel_purchase_order(user=self.approver, order=other, reason="desistência")
        with self.assertRaises(InventoryConflict):
            approve_purchase_order(user=self.approver, order=other)

    def test_http_create_approve_receive(self):
        self.client.force_login(self.buyer)
        data = {
            "supplier": self.supplier.pk,
            "notes": "Reposição",
            "operation_key": uuid.uuid4(),
            "lines-TOTAL_FORMS": 2,
            "lines-INITIAL_FORMS": 0,
            "lines-MIN_NUM_FORMS": 1,
            "lines-MAX_NUM_FORMS": 50,
            "lines-0-item": self.item.pk,
            "lines-0-quantity": 2,
            "lines-0-unit_price": "3.00",
            "lines-1-item": self.item.pk,
            "lines-1-quantity": 1,
            "lines-1-unit_price": "3.00",
        }
        response = self.client.post(reverse("inventory:purchase_create"), data)
        self.assertContains(response, "uma única vez")
        for key in ("lines-1-item", "lines-1-quantity", "lines-1-unit_price"):
            data[key] = ""
        response = self.client.post(reverse("inventory:purchase_create"), data)
        order = PurchaseOrder.objects.get()
        self.assertRedirects(response, reverse("inventory:purchase_detail", args=[order.pk]))
        self.assertNotContains(self.client.get(response.url), "Aprovar pedido")

        self.client.force_login(self.approver)
        self.client.post(
            reverse("inventory:purchase_detail", args=[order.pk]), {"action": "approve"}
        )
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.Status.APPROVED)

        self.client.force_login(self.receiver)
        url = reverse("inventory:purchase_receive", args=[order.lines.get().pk])
        receipt = {
            "location": self.location.pk,
            "quantity": 2,
            "unit_price": "3.00",
            "invoice_number": "NF-1",
            "operation_key": uuid.uuid4(),
            "confirmed": True,
        }
        self.assertEqual(self.client.post(url, {**receipt, "quantity": 3}).status_code, 409)
        self.assertRedirects(
            self.client.post(url, receipt), reverse("inventory:purchase_detail", args=[order.pk])
        )
        self.assertEqual(MaterialBalance.objects.get().quantity, 2)
        self.assertEqual(self.client.get(reverse("inventory:purchase_create")).status_code, 403)
