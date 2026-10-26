import uuid
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.clinical.pep.models import Encounter
from apps.clinical.pep.tests.test_views import TEST_STORAGES

from ..services import BillingConflict, add_item, capture_dispense, close_account, reopen_account
from . import test_capture


@override_settings(STORAGES=TEST_STORAGES, SECURE_SSL_REDIRECT=False)
class AccountClosureTests(TestCase):
    def setUp(self):
        test_capture.ProductionCaptureTests.setUp(self)
        self.nurse.user_permissions.add(
            Permission.objects.get(content_type__app_label="billing", codename="close_account")
        )

    def finish_encounter(self):
        Encounter.objects.filter(pk=self.encounter.pk).update(
            status=Encounter.Status.CLOSED, ended_at=timezone.now()
        )

    def manual(self):
        return add_item(
            user=self.nurse,
            account_id=self.account.pk,
            description="Taxa",
            quantity=1,
            unit_price="5.00",
            justification="sintético",
            operation_key=uuid.uuid4(),
            confirmed=True,
        )

    def test_close_requires_consistency_and_blocks_new_items_until_reopened(self):
        with self.assertRaises(BillingConflict):
            close_account(user=self.nurse, account_id=self.account.pk)  # encontro aberto
        self.finish_encounter()
        with self.assertRaises(BillingConflict):
            close_account(user=self.nurse, account_id=self.account.pk)  # dispensação pendente
        capture_dispense(
            user=self.nurse,
            account_id=self.account.pk,
            dispense_item_id=self.dispense_item.pk,
            unit_price=Decimal("1.00"),
            operation_key=uuid.uuid4(),
        )
        closure = close_account(user=self.nurse, account_id=self.account.pk)
        self.assertEqual(closure.total, Decimal("2.00"))
        self.assertTrue(self.account.closed)
        with self.assertRaises(BillingConflict):
            self.manual()
        with self.assertRaises(BillingConflict):
            reopen_account(user=self.nurse, account_id=self.account.pk, reason=" ")

        reopen_account(user=self.nurse, account_id=self.account.pk, reason="Glosa interna")
        self.manual()
        self.assertEqual(self.account.closures.count(), 2)

    def test_http_close(self):
        self.finish_encounter()
        capture_dispense(
            user=self.nurse,
            account_id=self.account.pk,
            dispense_item_id=self.dispense_item.pk,
            unit_price=Decimal("1.00"),
            operation_key=uuid.uuid4(),
        )
        self.client.force_login(self.nurse)
        self.client.post(reverse("billing:account_close", args=[self.account.pk]))
        detail = self.client.get(reverse("billing:account_detail", args=[self.account.pk]))
        self.assertContains(detail, "Conta fechada")
        self.assertNotContains(detail, "Adicionar item")
