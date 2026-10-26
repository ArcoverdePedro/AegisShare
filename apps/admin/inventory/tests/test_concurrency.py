import uuid
from queue import Queue
from threading import Barrier, Thread

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connections
from django.test import TransactionTestCase, skipUnlessDBFeature

from ..models import InventoryItem, MaterialBalance, MaterialMovement, Requisition, StockLocation
from ..services import InventoryConflict, record_movement, request_material


@skipUnlessDBFeature("has_select_for_update")
class InventoryConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create(
            username="inventory-concurrent", nivel_permissao="ADM", is_superuser=True
        )
        self.items = [
            InventoryItem.objects.create(code=f"CONC-{index}", name="Synthetic", unit="caixa")
            for index in range(2)
        ]

    def run_concurrently(self, operation):
        barrier, results = Barrier(2), Queue()

        def worker(index):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.actor.pk)
                barrier.wait(timeout=10)
                results.put(str(operation(actor, index).pk))
            except InventoryConflict:
                results.put("conflict")
            except Exception as exc:
                results.put(repr(exc))
            finally:
                connections.close_all()

        threads = [Thread(target=worker, args=(index,)) for index in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        return [results.get(timeout=2) for _ in threads]

    def test_parallel_retry_is_one_requisition(self):
        key = uuid.uuid4()
        results = self.run_concurrently(
            lambda actor, index: request_material(
                user=actor, item=self.items[0], quantity=3, operation_key=key, confirmed=True
            )
        )
        self.assertEqual(Requisition.objects.count(), 1)
        self.assertEqual(results, [str(Requisition.objects.get().pk)] * 2)

    def test_same_key_across_items_conflicts(self):
        key = uuid.uuid4()
        results = self.run_concurrently(
            lambda actor, index: request_material(
                user=actor, item=self.items[index], quantity=3, operation_key=key, confirmed=True
            )
        )
        self.assertEqual(Requisition.objects.count(), 1)
        self.assertCountEqual(results, [str(Requisition.objects.get().pk), "conflict"])

    def test_same_key_different_quantities_conflicts(self):
        key = uuid.uuid4()
        results = self.run_concurrently(
            lambda actor, index: request_material(
                user=actor,
                item=self.items[0],
                quantity=index + 1,
                operation_key=key,
                confirmed=True,
            )
        )
        self.assertEqual(Requisition.objects.count(), 1)
        self.assertCountEqual(results, [str(Requisition.objects.get().pk), "conflict"])

    def test_distinct_keys_identical_content_are_distinct(self):
        results = self.run_concurrently(
            lambda actor, index: request_material(
                user=actor,
                item=self.items[0],
                quantity=3,
                operation_key=uuid.uuid4(),
                confirmed=True,
            )
        )
        self.assertEqual(Requisition.objects.count(), 2)
        self.assertCountEqual(
            results, list(map(str, Requisition.objects.values_list("pk", flat=True)))
        )

    def test_last_balance_dispute_never_goes_negative(self):
        location = StockLocation.objects.create(code="ALM", name="Almoxarifado")
        record_movement(
            user=self.actor,
            kind="RECEIPT",
            item=self.items[0],
            location=location,
            quantity=1,
            operation_key=uuid.uuid4(),
        )
        results = self.run_concurrently(
            lambda actor, index: record_movement(
                user=actor,
                kind="ISSUE",
                item=self.items[0],
                location=location,
                quantity=1,
                operation_key=uuid.uuid4(),
            )
        )
        self.assertEqual(results.count("conflict"), 1)
        self.assertEqual(MaterialBalance.objects.get().quantity, 0)
        self.assertEqual(MaterialMovement.objects.filter(kind="ISSUE").count(), 1)

    def test_parallel_movement_retry_is_one_entry(self):
        location = StockLocation.objects.create(code="ALM", name="Almoxarifado")
        key = uuid.uuid4()
        results = self.run_concurrently(
            lambda actor, index: record_movement(
                user=actor,
                kind="RECEIPT",
                item=self.items[0],
                location=location,
                quantity=5,
                operation_key=key,
            )
        )
        self.assertEqual(MaterialMovement.objects.count(), 1)
        self.assertEqual(results, [str(MaterialMovement.objects.get().pk)] * 2)
        self.assertEqual(MaterialBalance.objects.get().quantity, 5)
