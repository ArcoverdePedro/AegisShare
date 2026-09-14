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

from ..models import Admission, Bed, BedOccupancy, Location
from ..services import AdtConflictError, BedUnavailableError, admit_patient

User = get_user_model()


@skipUnlessDBFeature("has_select_for_update", "supports_partial_indexes")
class AdmissionConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.actor = User.objects.create(
            username="adt-concurrency-admin",
            nivel_permissao="ADM",
            is_superuser=True,
            is_staff=True,
        )
        self.location = Location.objects.create(
            code="ADT-CONC",
            name="Unidade Concorrência",
            kind=Location.Kind.WARD,
        )
        self.bed = Bed.objects.create(
            location=self.location,
            code="RACE-01",
            label="Leito RACE-01",
        )

    def _encounter(self, suffix):
        patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier=f"ADT-CONC-{suffix}",
            full_name=f"Paciente Concorrência {suffix}",
            birth_date=timezone.localdate() - timedelta(days=365 * 35),
            created_by=self.actor,
        )
        return Encounter.objects.create(
            patient=patient,
            encounter_type=Encounter.Type.INPATIENT,
            status=Encounter.Status.OPEN,
            started_at=timezone.now() - timedelta(hours=2),
            responsible_professional=self.actor,
            created_by=self.actor,
        )

    def test_two_admissions_cannot_occupy_same_bed(self):
        encounters = [self._encounter("A"), self._encounter("B")]
        barrier = Barrier(3)
        results = Queue()
        actor_id = self.actor.pk
        bed_id = self.bed.pk

        def worker(encounter_id):
            close_old_connections()
            try:
                actor = User.objects.get(pk=actor_id)
                barrier.wait(timeout=5)
                admission = admit_patient(
                    encounter_id=encounter_id,
                    bed_id=bed_id,
                    actor=actor,
                    operation_key=uuid.uuid4(),
                )
                results.put(("ok", encounter_id, admission.pk))
            except (BedUnavailableError, AdtConflictError) as exc:
                results.put(("conflict", encounter_id, exc.__class__.__name__))
            except Exception as exc:
                results.put(("unexpected", encounter_id, repr(exc)))
            finally:
                connections.close_all()

        threads = [Thread(target=worker, args=(encounter.pk,)) for encounter in encounters]
        with patch("apps.clinical.adt.services.emit_adt_event"):
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
        self.assertEqual(
            BedOccupancy.objects.filter(bed=self.bed, ended_at__isnull=True).count(),
            1,
        )
        self.assertEqual(
            Admission.objects.filter(encounter_id__in=[e.pk for e in encounters]).count(),
            1,
        )
