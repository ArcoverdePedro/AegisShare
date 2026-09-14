import queue
import threading
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone

from aegis_share.tests.helpers import make_user

from ..models import Drug, StockMovement
from ..stock_services import (
    StockStateError,
    adjust_stock,
    create_lot,
    create_stock_item,
)

User = get_user_model()


@skipUnless(
    connection.vendor == "postgresql",
    "Concorrência de estoque é validada especificamente no PostgreSQL.",
)
class PharmacyStockConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.manager = make_user("rx-stock-concurrency-manager", role="ADM")
        self.manager.is_superuser = True
        self.manager.is_staff = True
        self.manager.save(update_fields=["is_superuser", "is_staff"])

        self.drug = Drug.objects.create(
            code="RX-STOCK-CONCURRENCY",
            name="Medicamento Sintético Concorrência",
            presentation="Apresentação sintética",
            dispense_unit="unidade",
        )
        self.stock = create_stock_item(
            actor=self.manager,
            drug_id=self.drug.pk,
            storage_location="Farmácia concorrência sintética",
            minimum_level=Decimal("0"),
        )
        self.lot = create_lot(
            actor=self.manager,
            stock_item_id=self.stock.pk,
            lot_number="LOTE-CONCORRENCIA-001",
            expires_on=timezone.localdate() + timedelta(days=30),
            initial_quantity=Decimal("5"),
        )

    def _run_adjustment(self, *, operation_key, barrier, outcomes):
        close_old_connections()
        try:
            actor = User.objects.get(pk=self.manager.pk)
            barrier.wait(timeout=10)
            try:
                movement = adjust_stock(
                    lot_id=self.lot.pk,
                    actor=actor,
                    quantity_delta=Decimal("-4"),
                    reason="Ajuste concorrente sintético",
                    operation_key=operation_key,
                )
            except StockStateError as exc:
                outcomes.put(("rejected", operation_key, str(exc)))
            except Exception as exc:  # pragma: no cover - diagnóstico de falha concorrente inesperada
                outcomes.put(
                    (
                        "unexpected",
                        operation_key,
                        f"{type(exc).__name__}: {exc}",
                    )
                )
            else:
                outcomes.put(("committed", operation_key, str(movement.pk)))
        finally:
            close_old_connections()

    def test_only_one_concurrent_withdrawal_commits_and_loser_rolls_back(self):
        barrier = threading.Barrier(3)
        outcomes = queue.Queue()
        operation_keys = [uuid.uuid4(), uuid.uuid4()]
        threads = [
            threading.Thread(
                target=self._run_adjustment,
                kwargs={
                    "operation_key": operation_key,
                    "barrier": barrier,
                    "outcomes": outcomes,
                },
                daemon=True,
            )
            for operation_key in operation_keys
        ]

        for thread in threads:
            thread.start()
        barrier.wait(timeout=10)
        for thread in threads:
            thread.join(timeout=15)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        recorded = [outcomes.get(timeout=5) for _ in threads]
        unexpected = [item for item in recorded if item[0] == "unexpected"]
        self.assertEqual(unexpected, [])

        committed = [item for item in recorded if item[0] == "committed"]
        rejected = [item for item in recorded if item[0] == "rejected"]
        self.assertEqual(len(committed), 1)
        self.assertEqual(len(rejected), 1)
        self.assertIn("saldo negativo", rejected[0][2].lower())

        self.lot.refresh_from_db()
        self.assertEqual(self.lot.quantity_available, Decimal("1"))

        winning_key = committed[0][1]
        losing_key = rejected[0][1]
        self.assertTrue(
            StockMovement.objects.filter(
                lot=self.lot,
                operation_key=winning_key,
                movement_type=StockMovement.Type.ADJUSTMENT,
                quantity_delta=Decimal("-4"),
            ).exists()
        )
        self.assertFalse(
            StockMovement.objects.filter(
                lot=self.lot,
                operation_key=losing_key,
            ).exists()
        )
        self.assertEqual(StockMovement.objects.filter(lot=self.lot).count(), 2)
