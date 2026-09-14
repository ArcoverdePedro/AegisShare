import uuid
from datetime import timedelta
from queue import Queue
from threading import Barrier, Thread
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone

from apps.clinical.pep.models import Encounter, Patient

from ..lifecycle import transfer_patient
from ..models import Admission, Bed, BedOccupancy, Location, Transfer
from ..services import AdtConflictError, BedUnavailableError

User = get_user_model()


@skipUnlessDBFeature("has_select_for_update", "supports_partial_indexes")
class TransferConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.actor = User.objects.create(
            username="adt-transfer-concurrency-admin",
            nivel_permissao="ADM",
            is_superuser=True,
            is_staff=True,
        )
        self.location = Location.objects.create(
            code="ADT-TR-CONC",
            name="Unidade Transferência Concorrente",
            kind=Location.Kind.WARD,
        )
        self.source_a = self._bed("SRC-A")
        self.source_b = self._bed("SRC-B")
        self.destination = self._bed("DST-01")
        self.admission_a, self.occupancy_a = self._admission("A", self.source_a)
        self.admission_b, self.occupancy_b = self._admission("B", self.source_b)

    def _bed(self, code):
        return Bed.objects.create(
            location=self.location,
            code=code,
            label=f"Leito {code}",
        )

    def _admission(self, suffix, bed):
        patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier=f"ADT-TR-CONC-{suffix}",
            full_name=f"Paciente Transferência {suffix}",
            birth_date=timezone.localdate() - timedelta(days=365 * 35),
            created_by=self.actor,
        )
        encounter = Encounter.objects.create(
            patient=patient,
            encounter_type=Encounter.Type.INPATIENT,
            status=Encounter.Status.OPEN,
            started_at=timezone.now() - timedelta(hours=4),
            responsible_professional=self.actor,
            created_by=self.actor,
        )
        admitted_at = timezone.now() - timedelta(hours=3)
        admission = Admission.objects.create(
            encounter=encounter,
            admitted_at=admitted_at,
            admitted_by=self.actor,
        )
        occupancy = BedOccupancy.objects.create(
            admission=admission,
            bed=bed,
            started_at=admitted_at,
            started_by=self.actor,
        )
        return admission, occupancy

    def test_two_transfers_cannot_occupy_same_destination(self):
        admissions = [self.admission_a, self.admission_b]
        source_by_admission = {
            self.admission_a.pk: self.source_a.pk,
            self.admission_b.pk: self.source_b.pk,
        }
        barrier = Barrier(3)
        results = Queue()
        actor_id = self.actor.pk
        destination_id = self.destination.pk

        def worker(admission_id):
            close_old_connections()
            try:
                actor = User.objects.get(pk=actor_id)
                barrier.wait(timeout=5)
                transfer = transfer_patient(
                    admission_id=admission_id,
                    destination_bed_id=destination_id,
                    actor=actor,
                    operation_key=uuid.uuid4(),
                )
                results.put(("ok", admission_id, transfer.pk))
            except (BedUnavailableError, AdtConflictError) as exc:
                results.put(("conflict", admission_id, exc.__class__.__name__))
            except Exception as exc:
                results.put(("unexpected", admission_id, repr(exc)))
            finally:
                connections.close_all()

        threads = [Thread(target=worker, args=(admission.pk,)) for admission in admissions]
        with patch("apps.clinical.adt.lifecycle.emit_adt_event"):
            for thread in threads:
                thread.start()
            barrier.wait(timeout=5)
            for thread in threads:
                thread.join(timeout=15)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        outcomes = [results.get(timeout=2) for _ in threads]
        self.assertFalse([row for row in outcomes if row[0] == "unexpected"], outcomes)
        self.assertEqual(sum(row[0] == "ok" for row in outcomes), 1, outcomes)
        self.assertEqual(sum(row[0] == "conflict" for row in outcomes), 1, outcomes)
        self.assertEqual(Transfer.objects.count(), 1)
        self.assertEqual(
            BedOccupancy.objects.filter(
                bed=self.destination,
                ended_at__isnull=True,
            ).count(),
            1,
        )

        winner_id = next(row[1] for row in outcomes if row[0] == "ok")
        loser_id = next(row[1] for row in outcomes if row[0] == "conflict")
        winner_active = BedOccupancy.objects.get(
            admission_id=winner_id,
            ended_at__isnull=True,
        )
        loser_active = BedOccupancy.objects.get(
            admission_id=loser_id,
            ended_at__isnull=True,
        )
        self.assertEqual(winner_active.bed_id, self.destination.pk)
        self.assertEqual(loser_active.bed_id, source_by_admission[loser_id])

        self.occupancy_a.refresh_from_db()
        self.occupancy_b.refresh_from_db()
        originals = {
            self.admission_a.pk: self.occupancy_a,
            self.admission_b.pk: self.occupancy_b,
        }
        self.assertIsNotNone(originals[winner_id].ended_at)
        self.assertIsNone(originals[loser_id].ended_at)
