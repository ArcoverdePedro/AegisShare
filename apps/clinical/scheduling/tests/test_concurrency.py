import uuid
from datetime import date, timedelta
from queue import Queue
from threading import Barrier, Thread

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone

from apps.clinical.pep.models import Patient

from ..models import AgendaSlot, Appointment
from ..services import SchedulingConflict, book_appointment


@skipUnlessDBFeature("has_select_for_update")
class BookingConcurrencyTests(TransactionTestCase):
    def test_last_vacancy_is_booked_once(self):
        actor = get_user_model().objects.create(
            username="sch-conc", nivel_permissao="ADM", is_superuser=True
        )
        patients = [
            Patient.objects.create(
                identifier_type="OTHER",
                identifier=f"C-{i}",
                full_name=f"P {i}",
                birth_date=date(1990, 1, 1),
                created_by=actor,
            )
            for i in range(2)
        ]
        start = timezone.now() + timedelta(days=1)
        slot = AgendaSlot.objects.create(
            professional=actor,
            starts_at=start,
            ends_at=start + timedelta(minutes=20),
            location="C1",
            created_by=actor,
        )
        barrier, results = Barrier(2), Queue()

        def worker(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                book_appointment(
                    user=get_user_model().objects.get(pk=actor.pk),
                    slot=slot,
                    patient=patients[index],
                    operation_key=uuid.uuid4(),
                )
                results.put("ok")
            except SchedulingConflict:
                results.put("conflict")
            except Exception as exc:
                results.put(repr(exc))
            finally:
                connections.close_all()

        threads = [Thread(target=worker, args=(i,)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        self.assertCountEqual([results.get(timeout=2) for _ in threads], ["ok", "conflict"])
        self.assertEqual(Appointment.objects.count(), 1)
