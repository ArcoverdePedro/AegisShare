import uuid
from datetime import date, time, timedelta

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.models import Encounter, Patient, PatientAccessGrant
from apps.clinical.pep.tests.test_views import TEST_STORAGES

from ..models import AgendaSlot, Appointment
from ..services import (
    SchedulingConflict,
    book_appointment,
    call_patient,
    cancel_appointment,
    check_in,
    create_slots,
    mark_no_show,
)


def grant(user, *codenames):
    user.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="scheduling", codename__in=codenames)
    )


@override_settings(STORAGES=TEST_STORAGES, SECURE_SSL_REDIRECT=False)
class SchedulingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        admin = make_user("sch-admin", role="ADM")
        admin.is_superuser = True
        admin.save(update_fields=["is_superuser"])
        cls.reception = make_user("sch-reception", role="FUNC")
        grant(
            cls.reception,
            "view_agenda",
            "manage_agenda",
            "book_appointment",
            "checkin_appointment",
        )
        cls.supervisor = make_user("sch-supervisor", role="FUNC")
        grant(cls.supervisor, "view_agenda", "book_appointment", "overbook_appointment")
        cls.doctor = make_user("sch-doctor", role="FUNC")
        grant(cls.doctor, "view_agenda")
        cls.patient = Patient.objects.create(
            identifier_type="OTHER",
            identifier="SCH-1",
            full_name="Carla Lima",
            birth_date=date(1985, 5, 5),
            created_by=cls.reception,
        )
        cls.other_patient = Patient.objects.create(
            identifier_type="OTHER",
            identifier="SCH-2",
            full_name="Davi Rocha",
            birth_date=date(1970, 1, 1),
            created_by=cls.reception,
        )
        for patient in (cls.patient, cls.other_patient):
            PatientAccessGrant.objects.create(
                patient=patient, user=cls.supervisor, reason="Recepção", granted_by=cls.reception
            )
        cls.tomorrow = timezone.localdate() + timedelta(days=1)

    def slots(self, capacity=1):
        return create_slots(
            user=self.reception,
            professional=self.doctor,
            day=self.tomorrow,
            start=time(8, 0),
            end=time(9, 0),
            minutes=20,
            capacity=capacity,
            location="Consultório 1",
        )

    def book(self, slot, patient=None, user=None, **extra):
        return book_appointment(
            user=user or self.reception,
            slot=slot,
            patient=patient or self.patient,
            operation_key=extra.pop("operation_key", uuid.uuid4()),
            **extra,
        )

    def test_slot_batch_is_idempotent(self):
        self.assertEqual(len(self.slots()), 3)
        self.assertEqual(len(self.slots()), 0)
        self.assertEqual(AgendaSlot.objects.count(), 3)

    def test_capacity_and_authorized_overbooking(self):
        slot = self.slots()[0]
        key = uuid.uuid4()
        first = self.book(slot, operation_key=key)
        self.assertEqual(self.book(slot, operation_key=key), first)
        with self.assertRaises(SchedulingConflict):
            self.book(slot, patient=self.other_patient)
        with self.assertRaises(PermissionDenied):
            self.book(slot, patient=self.other_patient, overbook=True, reason="urgente")
        with self.assertRaises(SchedulingConflict):
            self.book(slot, patient=self.other_patient, user=self.supervisor, overbook=True)
        extra = self.book(
            slot, patient=self.other_patient, user=self.supervisor, overbook=True, reason="retorno"
        )
        self.assertTrue(extra.overbooked)
        with self.assertRaises(SchedulingConflict):
            self.book(slot, user=self.supervisor, overbook=True, reason="duplicado")

    def test_reschedule_preserves_history_and_frees_capacity(self):
        first, second, _ = self.slots()
        original = self.book(first)

        moved = self.book(second, rescheduled_from=original)

        original.refresh_from_db()
        self.assertEqual(original.status, Appointment.Status.RESCHEDULED)
        self.assertEqual(moved.rescheduled_from, original)
        self.book(first, patient=self.other_patient)
        with self.assertRaises(SchedulingConflict):
            self.book(second, rescheduled_from=original)

    def test_check_in_opens_one_encounter_and_flows_to_queue(self):
        appointment = self.book(self.slots()[0])

        with self.assertRaises(SchedulingConflict):
            mark_no_show(user=self.reception, appointment=appointment)
        with self.assertRaises(SchedulingConflict):
            call_patient(user=self.reception, appointment=appointment)
        arrived = check_in(user=self.reception, appointment=appointment)
        with self.assertRaises(SchedulingConflict):
            check_in(user=self.reception, appointment=appointment)
        with self.assertRaises(SchedulingConflict):
            cancel_appointment(user=self.reception, appointment=appointment, reason="x")

        self.assertEqual(Encounter.objects.get().pk, arrived.encounter_id)
        self.assertEqual(arrived.encounter.responsible_professional, self.doctor)
        self.assertEqual(
            call_patient(user=self.reception, appointment=arrived).status,
            Appointment.Status.CALLED,
        )

    def test_no_show_only_after_start(self):
        appointment = self.book(self.slots()[0])
        AgendaSlot.objects.filter(pk=appointment.slot_id).update(
            starts_at=timezone.now() - timedelta(minutes=30),
            ends_at=timezone.now() - timedelta(minutes=10),
        )
        appointment.refresh_from_db()

        self.assertEqual(
            mark_no_show(user=self.reception, appointment=appointment).status,
            Appointment.Status.NO_SHOW,
        )

    def test_privacy_boundaries_and_http_flow(self):
        slot = self.slots()[0]
        self.client.force_login(self.reception)
        url = reverse("scheduling:appointment_create", args=[self.patient.pk])
        response = self.client.post(url, {"slot": slot.pk, "operation_key": uuid.uuid4()})
        appointment = Appointment.objects.get()
        self.assertRedirects(
            response, reverse("scheduling:appointment_detail", args=[appointment.pk])
        )
        self.assertEqual(
            self.client.post(url, {"slot": slot.pk, "operation_key": uuid.uuid4()}).status_code, 409
        )

        agenda = self.client.get(reverse("scheduling:agenda") + f"?dia={self.tomorrow}")
        self.assertContains(agenda, "Carla Lima")
        self.assertEqual(agenda["Cache-Control"], "private, no-store")

        self.client.force_login(self.doctor)
        agenda = self.client.get(reverse("scheduling:agenda") + f"?dia={self.tomorrow}")
        self.assertNotContains(agenda, "Carla Lima")
        self.assertContains(agenda, f"Senha {appointment.ticket}")
        detail = reverse("scheduling:appointment_detail", args=[appointment.pk])
        self.assertEqual(self.client.get(detail).status_code, 403)
        self.assertEqual(self.client.get(url).status_code, 403)
