import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from aegis_share.tests.helpers import make_user

from ..events import PRESCRIPTION_EVENT_GROUP, emit_stock_low_event
from ..models import Drug, StockMovement
from ..stock_services import (
    StockStateError,
    adjust_stock,
    create_lot,
    create_stock_item,
    receive_stock,
)

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


class _RecordingChannelLayer:
    def __init__(self):
        self.calls = []

    async def group_send(self, group, payload):
        self.calls.append((group, payload))


class PharmacyStockServiceTests(TestCase):
    def setUp(self):
        self.admin = make_user("rx-stock-admin", role="ADM")
        self.manager = make_user("rx-stock-manager", role="FUNC")
        self.denied = make_user("rx-stock-denied", role="FUNC")
        self._grant_permission(self.manager, "manage_pharmacy_stock")
        self.drug = Drug.objects.create(
            code="RX-STOCK-001",
            name="Medicamento Sintético Estoque",
            presentation="Apresentação sintética",
            dispense_unit="unidade",
        )

    def _grant_permission(self, user, codename):
        permission = Permission.objects.get(
            codename=codename,
            content_type__app_label="prescription",
        )
        user.user_permissions.add(permission)
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            if hasattr(user, cache_name):
                delattr(user, cache_name)

    def _stock(self, *, minimum=Decimal("5")):
        return create_stock_item(
            actor=self.manager,
            drug_id=self.drug.pk,
            storage_location="Farmácia sintética",
            minimum_level=minimum,
        )

    def _lot(self, *, quantity=Decimal("10"), minimum=Decimal("5")):
        stock = self._stock(minimum=minimum)
        lot = create_lot(
            actor=self.manager,
            stock_item_id=stock.pk,
            lot_number="LOTE-SINT-001",
            expires_on=timezone.localdate() + timedelta(days=30),
            initial_quantity=quantity,
        )
        return stock, lot

    def test_stock_management_requires_explicit_capability(self):
        with self.assertRaises(PermissionDenied):
            create_stock_item(
                actor=self.denied,
                drug_id=self.drug.pk,
                storage_location="Local negado",
                minimum_level=1,
            )

    def test_initial_lot_quantity_is_recorded_as_receipt_movement(self):
        _, lot = self._lot(quantity=Decimal("12.5000"))

        lot.refresh_from_db()
        movement = StockMovement.objects.get(lot=lot)
        self.assertEqual(lot.quantity_available, Decimal("12.5000"))
        self.assertEqual(movement.movement_type, StockMovement.Type.RECEIPT)
        self.assertEqual(movement.quantity_delta, Decimal("12.5000"))
        self.assertEqual(movement.actor, self.manager)

    def test_receipt_is_idempotent_for_same_lot_and_operation_key(self):
        _, lot = self._lot(quantity=Decimal("1"), minimum=Decimal("0"))
        operation_key = uuid.uuid4()

        first = receive_stock(
            lot_id=lot.pk,
            actor=self.manager,
            quantity=Decimal("4"),
            operation_key=operation_key,
        )
        second = receive_stock(
            lot_id=lot.pk,
            actor=self.manager,
            quantity=Decimal("4"),
            operation_key=operation_key,
        )

        lot.refresh_from_db()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(lot.quantity_available, Decimal("5"))
        self.assertEqual(
            StockMovement.objects.filter(lot=lot, operation_key=operation_key).count(),
            1,
        )

    def test_reusing_operation_key_with_different_amount_is_rejected(self):
        _, lot = self._lot(quantity=Decimal("1"), minimum=Decimal("0"))
        operation_key = uuid.uuid4()
        receive_stock(
            lot_id=lot.pk,
            actor=self.manager,
            quantity=Decimal("4"),
            operation_key=operation_key,
        )

        with self.assertRaises(StockStateError):
            receive_stock(
                lot_id=lot.pk,
                actor=self.manager,
                quantity=Decimal("5"),
                operation_key=operation_key,
            )

        lot.refresh_from_db()
        self.assertEqual(lot.quantity_available, Decimal("5"))

    def test_adjustment_cannot_make_balance_negative(self):
        _, lot = self._lot(quantity=Decimal("3"), minimum=Decimal("0"))

        with self.assertRaises(StockStateError):
            adjust_stock(
                lot_id=lot.pk,
                actor=self.manager,
                quantity_delta=Decimal("-4"),
                reason="Ajuste sintético de inventário",
            )

        lot.refresh_from_db()
        self.assertEqual(lot.quantity_available, Decimal("3"))
        self.assertEqual(lot.movements.count(), 1)

    def test_adjustment_requires_reason(self):
        _, lot = self._lot(quantity=Decimal("3"), minimum=Decimal("0"))

        with self.assertRaises(StockStateError):
            adjust_stock(
                lot_id=lot.pk,
                actor=self.manager,
                quantity_delta=Decimal("-1"),
                reason="",
            )

    def test_expired_lot_cannot_receive_new_stock(self):
        stock = self._stock(minimum=Decimal("0"))
        lot = create_lot(
            actor=self.manager,
            stock_item_id=stock.pk,
            lot_number="LOTE-EXPIRADO",
            expires_on=timezone.localdate() - timedelta(days=1),
            initial_quantity=Decimal("0"),
        )

        with self.assertRaises(StockStateError):
            receive_stock(
                lot_id=lot.pk,
                actor=self.manager,
                quantity=Decimal("1"),
            )

    def test_low_stock_event_is_scheduled_when_balance_falls_below_minimum(self):
        stock, lot = self._lot(quantity=Decimal("10"), minimum=Decimal("5"))

        with patch("apps.clinical.prescription.stock_services.emit_stock_low_event") as emit:
            adjust_stock(
                lot_id=lot.pk,
                actor=self.manager,
                quantity_delta=Decimal("-6"),
                reason="Ajuste sintético para teste de mínimo",
            )

        emit.assert_called_once_with(
            stock_item_id=stock.pk,
            drug_id=stock.drug_id,
            storage_location=stock.storage_location,
            quantity_available=Decimal("4.0000"),
            minimum_level=Decimal("5"),
        )

    def test_direct_balance_rewrite_is_rejected(self):
        _, lot = self._lot(quantity=Decimal("2"), minimum=Decimal("0"))
        lot.quantity_available = Decimal("99")

        with self.assertRaises(ValidationError):
            lot.save()

    def test_lot_identity_is_immutable_after_first_movement(self):
        _, lot = self._lot(quantity=Decimal("2"), minimum=Decimal("0"))
        lot.lot_number = "LOTE-REESCRITO"

        with self.assertRaises(ValidationError):
            lot.save()

    def test_stock_movements_cannot_be_bulk_deleted(self):
        _, lot = self._lot(quantity=Decimal("2"), minimum=Decimal("0"))

        with self.assertRaises(ValidationError):
            StockMovement.objects.filter(lot=lot).delete()


class PharmacyStockEventTests(TestCase):
    def test_low_stock_payload_is_operational_and_contract_compatible(self):
        layer = _RecordingChannelLayer()
        stock_item_id = uuid.uuid4()
        drug_id = uuid.uuid4()

        with (
            patch("apps.clinical.prescription.events.get_channel_layer", return_value=layer),
            patch(
                "apps.clinical.prescription.events.transaction.on_commit",
                side_effect=lambda callback: callback(),
            ),
        ):
            emit_stock_low_event(
                stock_item_id=stock_item_id,
                drug_id=drug_id,
                storage_location="Farmácia técnica",
                quantity_available=Decimal("4.5"),
                minimum_level=Decimal("5"),
            )

        self.assertEqual(len(layer.calls), 1)
        group, payload = layer.calls[0]
        self.assertEqual(group, PRESCRIPTION_EVENT_GROUP)
        self.assertEqual(payload["event_type"], "stock.low")
        self.assertEqual(payload["stock_item_id"], str(stock_item_id))
        self.assertEqual(payload["drug_id"], str(drug_id))
        self.assertEqual(payload["quantity_available"], 4.5)
        self.assertEqual(payload["minimum_level"], 5.0)
        forbidden = {"patient_id", "patient_name", "cpf", "prescription_text"}
        self.assertFalse(forbidden.intersection(payload))


@override_settings(STORAGES=TEST_STORAGES)
class PharmacyStockViewTests(TestCase):
    def setUp(self):
        self.admin = make_user("rx-stock-view-admin", role="ADM")
        self.admin.is_superuser = True
        self.admin.is_staff = True
        self.admin.save(update_fields=["is_superuser", "is_staff"])

        self.viewer = make_user("rx-stock-viewer", role="FUNC")
        self.denied = make_user("rx-stock-view-denied", role="FUNC")
        self._grant_permission(self.viewer, "view_pharmacy_stock")

        self.drug = Drug.objects.create(
            code="RX-STOCK-VIEW",
            name="Medicamento Sintético Visível",
            presentation="Apresentação sintética",
            dispense_unit="unidade",
        )
        self.stock = create_stock_item(
            actor=self.admin,
            drug_id=self.drug.pk,
            storage_location="Farmácia principal",
            minimum_level=Decimal("5"),
        )
        self.lot = create_lot(
            actor=self.admin,
            stock_item_id=self.stock.pk,
            lot_number="VIEW-LOT-001",
            expires_on=timezone.localdate() + timedelta(days=60),
            initial_quantity=Decimal("4"),
        )

    def _grant_permission(self, user, codename):
        permission = Permission.objects.get(
            codename=codename,
            content_type__app_label="prescription",
        )
        user.user_permissions.add(permission)
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            if hasattr(user, cache_name):
                delattr(user, cache_name)

    def test_stock_page_requires_capability_and_is_no_store(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("prescription:pharmacy_stock"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Medicamento Sintético Visível")
        self.assertContains(response, "Estoque baixo")
        self.assertContains(response, "VIEW-LOT-001")
        self.assertIn("no-store", response["Cache-Control"])

        self.client.force_login(self.denied)
        denied_response = self.client.get(reverse("prescription:pharmacy_stock"))
        self.assertEqual(denied_response.status_code, 403)
