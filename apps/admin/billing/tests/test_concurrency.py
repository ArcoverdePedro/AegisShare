import uuid
from datetime import date
from queue import Queue
from threading import Barrier, Thread

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connections
from django.test import TransactionTestCase, skipUnlessDBFeature

from apps.clinical.pep.models import Encounter, Patient

from ..models import BillingItem, HospitalAccount
from ..services import BillingConflict, add_item, open_account


@skipUnlessDBFeature("has_select_for_update")
class BillingConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create(
            username="billing-concurrent", nivel_permissao="ADM", is_superuser=True
        )
        patient = Patient.objects.create(
            identifier_type="OTHER",
            identifier="BILL-CONC",
            full_name="Paciente sintético",
            birth_date=date(1990, 1, 1),
            created_by=self.actor,
        )
        self.encounters = [
            Encounter.objects.create(
                patient=patient, responsible_professional=self.actor, created_by=self.actor
            )
            for _ in range(2)
        ]

    def run_concurrently(self, operation):
        barrier, results = Barrier(2), Queue()

        def worker(index):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.actor.pk)
                barrier.wait(timeout=10)
                results.put(str(operation(actor, index).pk))
            except BillingConflict:
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

    def test_parallel_open_retry_is_one_account(self):
        key = uuid.uuid4()
        results = self.run_concurrently(
            lambda actor, index: open_account(
                user=actor, encounter_id=self.encounters[0].pk, operation_key=key, confirmed=True
            )
        )
        self.assertEqual(HospitalAccount.objects.count(), 1)
        self.assertEqual(results, [str(HospitalAccount.objects.get().pk)] * 2)

    def test_distinct_open_keys_for_same_encounter_conflict(self):
        results = self.run_concurrently(
            lambda actor, index: open_account(
                user=actor,
                encounter_id=self.encounters[0].pk,
                operation_key=uuid.uuid4(),
                confirmed=True,
            )
        )
        self.assertEqual(HospitalAccount.objects.count(), 1)
        self.assertCountEqual(results, [str(HospitalAccount.objects.get().pk), "conflict"])

    def test_same_open_key_across_encounters_conflicts(self):
        key = uuid.uuid4()
        results = self.run_concurrently(
            lambda actor, index: open_account(
                user=actor,
                encounter_id=self.encounters[index].pk,
                operation_key=key,
                confirmed=True,
            )
        )
        self.assertEqual(HospitalAccount.objects.count(), 1)
        self.assertCountEqual(results, [str(HospitalAccount.objects.get().pk), "conflict"])

    def test_parallel_item_retry_is_one_item(self):
        account = open_account(
            user=self.actor,
            encounter_id=self.encounters[0].pk,
            operation_key=uuid.uuid4(),
            confirmed=True,
        )
        key = uuid.uuid4()
        results = self.run_concurrently(
            lambda actor, index: add_item(
                user=actor,
                account_id=account.pk,
                operation_key=key,
                confirmed=True,
                description="Sintético",
                quantity=3,
                unit_price="0.10",
            )
        )
        self.assertEqual(BillingItem.objects.count(), 1)
        self.assertEqual(results, [str(BillingItem.objects.get().pk)] * 2)

    def test_same_item_key_across_accounts_conflicts(self):
        accounts = [
            open_account(
                user=self.actor,
                encounter_id=encounter.pk,
                operation_key=uuid.uuid4(),
                confirmed=True,
            )
            for encounter in self.encounters
        ]
        key = uuid.uuid4()
        results = self.run_concurrently(
            lambda actor, index: add_item(
                user=actor,
                account_id=accounts[index].pk,
                operation_key=key,
                confirmed=True,
                description="Sintético",
                quantity=1,
                unit_price="0",
            )
        )
        self.assertEqual(BillingItem.objects.count(), 1)
        self.assertCountEqual(results, [str(BillingItem.objects.get().pk), "conflict"])
