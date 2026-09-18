import uuid
from datetime import date
from queue import Queue
from threading import Barrier, Thread

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connections
from django.test import TransactionTestCase, skipUnlessDBFeature

from apps.clinical.pep.models import Encounter, Patient

from ..models import Procedure, SurgicalCase
from ..services import SurgeryConflict, request_procedure


@skipUnlessDBFeature("has_select_for_update")
class SurgeryConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create(
            username="surgery-concurrent", nivel_permissao="ADM", is_superuser=True
        )
        patient = Patient.objects.create(
            identifier_type="OTHER",
            identifier="SURG-CONC",
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
        self.procedure = Procedure.objects.create(code="SYNTH", name="Sintético")

    def run_concurrently(self, *, distinct_encounters):
        barrier, results = Barrier(2), Queue()
        key = uuid.uuid4()

        def worker(index):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.actor.pk)
                procedure = Procedure.objects.get(pk=self.procedure.pk)
                barrier.wait(timeout=10)
                item = request_procedure(
                    user=actor,
                    encounter_id=self.encounters[index if distinct_encounters else 0].pk,
                    procedure=procedure,
                    operation_key=key,
                )
                results.put(str(item.pk))
            except SurgeryConflict:
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
        self.assertEqual(SurgicalCase.objects.count(), 1)
        self.assertEqual(results, [str(SurgicalCase.objects.get().pk)] * 2)

    def test_cross_encounter_key_collision_returns_conflict(self):
        results = self.run_concurrently(distinct_encounters=True)
        self.assertEqual(SurgicalCase.objects.count(), 1)
        self.assertCountEqual(results, [str(SurgicalCase.objects.get().pk), "conflict"])
