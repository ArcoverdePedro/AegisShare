import uuid
from datetime import date
from queue import Queue
from threading import Barrier, Thread

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connections
from django.test import TransactionTestCase, skipUnlessDBFeature

from apps.clinical.pep.models import Encounter, Patient

from ..models import ImagingExam, ImagingOrder
from ..services import RisConflict, order_exam


@skipUnlessDBFeature("has_select_for_update")
class RisConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create(
            username="ris-concurrent", nivel_permissao="ADM", is_superuser=True
        )
        patient = Patient.objects.create(
            identifier_type="OTHER",
            identifier="RIS-CONC",
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
        self.exam = ImagingExam.objects.create(code="SYNTH", name="Sintético")

    def run_concurrently(self, *, distinct_encounters):
        barrier, results = Barrier(2), Queue()
        key = uuid.uuid4()

        def worker(index):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.actor.pk)
                exam = ImagingExam.objects.get(pk=self.exam.pk)
                barrier.wait(timeout=10)
                item = order_exam(
                    user=actor,
                    encounter_id=self.encounters[index if distinct_encounters else 0].pk,
                    exam=exam,
                    operation_key=key,
                )
                results.put(str(item.pk))
            except RisConflict:
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

    def test_parallel_identical_retry_has_one_original(self):
        results = self.run_concurrently(distinct_encounters=False)
        self.assertEqual(ImagingOrder.objects.count(), 1)
        self.assertEqual(results, [str(ImagingOrder.objects.get().pk)] * 2)

    def test_cross_encounter_key_collision_returns_conflict(self):
        results = self.run_concurrently(distinct_encounters=True)
        self.assertEqual(ImagingOrder.objects.count(), 1)
        self.assertCountEqual(results, [str(ImagingOrder.objects.get().pk), "conflict"])
