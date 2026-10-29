import uuid
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.clinical.nursing.tests import test_administration_services as rx_fixture
from apps.clinical.pep.tests.test_views import TEST_STORAGES
from apps.clinical.prescription.models import MedicationDispenseItem

from ..models import BillingItem, HospitalAccount
from ..services import BillingConflict, capture_dispense, pending_dispense_items, reverse_item
from ..totals import account_total


@override_settings(STORAGES=TEST_STORAGES, SECURE_SSL_REDIRECT=False)
class ProductionCaptureTests(TestCase):
    def setUp(self):
        rx_fixture.MedicationAdministrationServiceTests.setUp(self)
        self.nurse.is_superuser = True  # evita o redirecionamento de primeiro acesso
        self.nurse.save(update_fields=["is_superuser"])
        self.nurse.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="billing",
                codename__in=["view_accounts", "add_item", "reverse_item"],
            )
        )
        self.account = HospitalAccount.objects.create(
            encounter=self.encounter, opened_by=self.nurse, operation_key=uuid.uuid4()
        )

    def capture(self, item=None, key=None):
        return capture_dispense(
            user=self.nurse,
            account_id=self.account.pk,
            dispense_item_id=(item or self.dispense_item).pk,
            unit_price=Decimal("3.50"),
            operation_key=key or uuid.uuid4(),
        )

    def test_each_dispense_bills_once_and_reversal_allows_correction(self):
        self.assertEqual(pending_dispense_items(self.account), [self.dispense_item])
        key = uuid.uuid4()
        billed = self.capture(key=key)
        self.assertEqual(self.capture(key=key), billed)
        self.assertEqual((billed.quantity, billed.source), (2, BillingItem.Source.DISPENSE))
        with self.assertRaises(BillingConflict):
            self.capture()
        self.assertEqual(pending_dispense_items(self.account), [])
        self.assertEqual(account_total(self.account), Decimal("7.00"))

        reversal = reverse_item(
            user=self.nurse,
            item_id=billed.pk,
            justification="Preço errado",
            operation_key=uuid.uuid4(),
        )
        self.assertEqual(reversal.reverses, billed)
        self.assertEqual(account_total(self.account), Decimal("0.00"))
        with self.assertRaises(BillingConflict):
            reverse_item(
                user=self.nurse, item_id=billed.pk, justification="x", operation_key=uuid.uuid4()
            )
        self.assertEqual(pending_dispense_items(self.account), [self.dispense_item])
        self.capture()
        self.assertEqual(account_total(self.account), Decimal("7.00"))
        self.assertEqual(BillingItem.objects.count(), 3)

    def test_fractional_quantity_is_refused(self):
        fractional = MedicationDispenseItem.objects.create(
            dispense=self.dispense,
            request_item=self.request_item,
            lot=self.lot,
            quantity=Decimal("0.5"),
        )
        with self.assertRaises(BillingConflict):
            self.capture(fractional)

    def test_http_capture_and_reverse(self):
        self.client.force_login(self.nurse)
        detail = reverse("billing:account_detail", args=[self.account.pk])
        self.assertContains(self.client.get(detail), "Produção sem lançamento")

        self.client.post(
            reverse("billing:dispense_capture", args=[self.account.pk, self.dispense_item.pk]),
            {"unit_price": "1.25", "operation_key": uuid.uuid4()},
        )
        item = BillingItem.objects.get()
        self.client.post(
            reverse("billing:item_reverse", args=[self.account.pk, item.pk]),
            {"justification": "Duplicado", "operation_key": uuid.uuid4()},
        )
        self.assertTrue(BillingItem.objects.filter(reverses=item).exists())
        self.assertContains(self.client.get(detail), "Estornado")
