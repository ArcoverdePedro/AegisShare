import uuid
from datetime import timedelta
from queue import Queue
from threading import Barrier, Thread

from django.contrib.auth.models import Permission
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from apps.admin.hr.models import Employee, EmployeeAbsence
from apps.clinical.pep.tests.test_views import TEST_STORAGES

from ..models import OperatingRoom, SurgerySchedule
from ..services import SurgeryConflict, cancel_schedule, schedule_case
from . import test_concurrency, test_workflow


def tomorrow_at(hour):
    day = timezone.localdate() + timedelta(days=1)
    return timezone.make_aware(timezone.datetime(day.year, day.month, day.day, hour))


@override_settings(STORAGES=TEST_STORAGES, SECURE_SSL_REDIRECT=False)
class SurgeryScheduleTests(TestCase):
    order = test_workflow.SurgeryTests.order

    @classmethod
    def setUpTestData(cls):
        test_workflow.SurgeryTests.setUpTestData.__func__(cls)
        cls.user.user_permissions.add(
            Permission.objects.get(content_type__app_label="surgery", codename="schedule_case")
        )
        cls.room = OperatingRoom.objects.create(code="SO1", name="Sala 1")
        cls.room2 = OperatingRoom.objects.create(code="SO2", name="Sala 2")

    def setUp(self):
        self.client.force_login(self.user)

    def book(self, case, start, end, *, room=None, surgeon=None, **extra):
        return schedule_case(
            user=self.user,
            case=case,
            room=room or self.room,
            surgeon=surgeon or self.user,
            starts_at=start,
            ends_at=end,
            operation_key=extra.pop("operation_key", uuid.uuid4()),
            **extra,
        )

    def test_room_and_surgeon_cannot_overlap_and_cancel_frees_room(self):
        first, second = self.order(), self.order()
        booked = self.book(first, tomorrow_at(8), tomorrow_at(10))
        with self.assertRaises(SurgeryConflict):
            self.book(second, tomorrow_at(9), tomorrow_at(11), surgeon=self.other)
        with self.assertRaises(SurgeryConflict):
            self.book(second, tomorrow_at(9), tomorrow_at(11), room=self.room2)
        self.book(
            second, tomorrow_at(10), tomorrow_at(11), surgeon=self.other
        )  # encosta, não sobrepõe

        cancel_schedule(user=self.user, schedule=booked, reason="Paciente instável")
        third = self.order()
        self.book(third, tomorrow_at(8), tomorrow_at(9), surgeon=self.other)
        booked.refresh_from_db()
        self.assertEqual((booked.status, booked.reason), ("CANCELLED", "Paciente instável"))

    def test_reschedule_keeps_history_and_ignores_own_slot(self):
        case = self.order()
        original = self.book(case, tomorrow_at(8), tomorrow_at(10))
        with self.assertRaises(SurgeryConflict):
            self.book(case, tomorrow_at(12), tomorrow_at(13))
        moved = self.book(case, tomorrow_at(9), tomorrow_at(11), rescheduled_from=original)
        original.refresh_from_db()
        self.assertEqual(original.status, SurgerySchedule.Status.RESCHEDULED)
        self.assertEqual(moved.rescheduled_from, original)

    def test_absent_surgeon_and_past_period_are_refused(self):
        case = self.order()
        employee = Employee.objects.create(user=self.other, department="CC", job_title="Cirurgião")
        EmployeeAbsence.objects.create(
            employee=employee,
            kind="LEAVE",
            starts_on=tomorrow_at(8).date(),
            ends_on=tomorrow_at(8).date(),
        )
        with self.assertRaises(SurgeryConflict):
            self.book(case, tomorrow_at(8), tomorrow_at(9), surgeon=self.other)
        with self.assertRaises(SurgeryConflict):
            self.book(
                case, timezone.now() - timedelta(hours=2), timezone.now() - timedelta(hours=1)
            )

    def test_http_schedule_and_map_privacy(self):
        case = self.order()
        url = reverse("surgery:schedule_create", args=[case.pk])
        data = {
            "room": self.room.pk,
            "surgeon": self.user.pk,
            "minutes": 90,
            "starts_at": timezone.localtime(tomorrow_at(8)).strftime("%Y-%m-%dT%H:%M"),
            "operation_key": uuid.uuid4(),
        }
        self.assertRedirects(
            self.client.post(url, data), reverse("surgery:case_detail", args=[case.pk])
        )
        self.assertEqual(
            self.client.post(url, {**data, "operation_key": uuid.uuid4()}).status_code, 409
        )
        map_url = reverse("surgery:room_map") + f"?dia={tomorrow_at(8).date()}"
        self.assertContains(self.client.get(map_url), "Procedimento sintético")

        self.client.force_login(self.other)
        response = self.client.get(map_url)
        self.assertNotContains(response, "Procedimento sintético")
        self.assertContains(response, "reservado")
        self.assertEqual(self.client.get(url).status_code, 403)


@skipUnlessDBFeature("has_select_for_update")
class ScheduleConcurrencyTests(TransactionTestCase):
    setUp = test_concurrency.SurgeryConcurrencyTests.setUp

    def test_parallel_bookings_do_not_overlap_room(self):
        from ..services import request_procedure

        room = OperatingRoom.objects.create(code="SOC", name="Sala C")
        cases = [
            request_procedure(
                user=self.actor,
                encounter_id=encounter.pk,
                procedure=self.procedure,
                operation_key=uuid.uuid4(),
            )
            for encounter in self.encounters
        ]
        barrier, results = Barrier(2), Queue()

        def worker(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                schedule_case(
                    user=self.actor,
                    case=cases[index],
                    room=room,
                    surgeon=self.actor,
                    starts_at=tomorrow_at(8),
                    ends_at=tomorrow_at(9),
                    operation_key=uuid.uuid4(),
                )
                results.put("ok")
            except SurgeryConflict:
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
        self.assertEqual(SurgerySchedule.objects.count(), 1)
