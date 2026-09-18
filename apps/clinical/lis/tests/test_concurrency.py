import uuid
from datetime import date
from queue import Queue
from threading import Barrier, Thread

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone

from apps.clinical.pep.models import Encounter, Patient

from ..models import LabTest, ServiceRequest, Specimen
from ..services import LisConflict, collect_specimen, order_test


@skipUnlessDBFeature("has_select_for_update")
class LisConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create(
            username="lis-concurrent",
            nivel_permissao="ADM",
            is_superuser=True,
        )
        patient = Patient.objects.create(
            identifier_type="OTHER",
            identifier="LIS-CONC",
            full_name="Paciente sintético",
            birth_date=date(1990, 1, 1),
            created_by=self.actor,
        )
        self.encounter = Encounter.objects.create(
            patient=patient, responsible_professional=self.actor, created_by=self.actor
        )
        self.test = LabTest.objects.create(
            code="SYNTH", name="Sintético", specimen_type="Sintético"
        )

    def run_concurrently(self, operation):
        barrier, results = Barrier(2), Queue()

        def worker(index):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.actor.pk)
                barrier.wait(timeout=10)
                results.put(str(operation(actor, index).pk))
            except LisConflict:
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

    def test_concurrent_identical_order_returns_same_record(self):
        key = uuid.uuid4()
        outcomes = self.run_concurrently(
            lambda actor, index: order_test(
                user=actor, encounter_id=self.encounter.pk, lab_test=self.test, operation_key=key
            )
        )
        self.assertEqual(ServiceRequest.objects.count(), 1)
        self.assertEqual(outcomes, [str(ServiceRequest.objects.get().pk)] * 2)

    def test_two_distinct_collections_produce_one_record_and_conflict(self):
        order = order_test(
            user=self.actor,
            encounter_id=self.encounter.pk,
            lab_test=self.test,
            operation_key=uuid.uuid4(),
        )
        when = timezone.now()
        outcomes = self.run_concurrently(
            lambda actor, index: collect_specimen(
                user=actor,
                order=order,
                accession_code=f"SYNTH-{index}",
                collected_at=when,
                operation_key=uuid.uuid4(),
                confirmed=True,
            )
        )
        self.assertEqual(Specimen.objects.count(), 1)
        self.assertCountEqual(outcomes, [str(Specimen.objects.get().pk), "conflict"])
