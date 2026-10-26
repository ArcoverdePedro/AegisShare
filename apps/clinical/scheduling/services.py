from datetime import datetime, timedelta

from auditlog.context import set_actor
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.admin.hr.models import absent_on
from apps.clinical.pep.events import emit_clinical_event
from apps.clinical.pep.models import Encounter
from apps.clinical.pep.permissions import can_access_patient, require_module_permission

from .models import AgendaSlot, Appointment

MAX_SLOTS_PER_BATCH = 96


class SchedulingConflict(ValueError):
    pass


def require_permission(user, capability=None):
    require_module_permission(user, "scheduling", "view_agenda", capability)


def create_slots(*, user, professional, day, start, end, minutes, capacity, location):
    require_permission(user, "manage_agenda")
    tz = timezone.get_current_timezone()
    cursor = timezone.make_aware(datetime.combine(day, start), tz)
    limit = timezone.make_aware(datetime.combine(day, end), tz)
    step = timedelta(minutes=minutes)
    starts = []
    while cursor + step <= limit and len(starts) < MAX_SLOTS_PER_BATCH:
        starts.append(cursor)
        cursor += step
    if not starts:
        raise SchedulingConflict("O intervalo não comporta nenhum horário.")
    if absent_on(professional, day):
        raise SchedulingConflict("Profissional com ausência registrada nesta data.")
    with transaction.atomic(), set_actor(user):
        existing = set(
            AgendaSlot.objects.filter(professional=professional, starts_at__in=starts).values_list(
                "starts_at", flat=True
            )
        )
        return [
            AgendaSlot.objects.create(
                professional=professional,
                starts_at=moment,
                ends_at=moment + step,
                capacity=capacity,
                location=location.strip(),
                created_by=user,
            )
            for moment in starts
            if moment not in existing
        ]


def block_slot(*, user, slot, reason):
    require_permission(user, "manage_agenda")
    with transaction.atomic(), set_actor(user):
        slot = AgendaSlot.objects.select_for_update().get(pk=slot.pk)
        slot.blocked_reason = reason.strip()
        slot.save(update_fields=["blocked_reason"])
        return slot


def _retry(operation_key, user, slot, patient):
    existing = Appointment.objects.filter(operation_key=operation_key).first()
    if existing and (existing.booked_by_id, existing.slot_id, existing.patient_id) != (
        user.pk,
        slot.pk,
        patient.pk,
    ):
        raise SchedulingConflict("Operação incompatível.")
    return existing


def book_appointment(
    *, user, slot, patient, operation_key, overbook=False, reason="", rescheduled_from=None
):
    require_permission(user, "book_appointment")
    if not can_access_patient(user, patient):
        raise PermissionDenied
    if overbook:
        require_permission(user, "overbook_appointment")
        if not reason.strip():
            raise SchedulingConflict("Encaixe exige justificativa.")
    try:
        with transaction.atomic(), set_actor(user):
            slot = AgendaSlot.objects.select_for_update().get(pk=slot.pk)
            existing = _retry(operation_key, user, slot, patient)
            if existing:
                return existing
            if slot.blocked_reason:
                raise SchedulingConflict("Horário bloqueado.")
            if slot.starts_at <= timezone.now():
                raise SchedulingConflict("Horário já iniciado.")
            if absent_on(slot.professional, timezone.localtime(slot.starts_at).date()):
                raise SchedulingConflict("Profissional com ausência registrada nesta data.")
            taken = slot.appointments.filter(status__in=Appointment.ACTIVE).count()
            if taken >= slot.capacity and not overbook:
                raise SchedulingConflict("Horário sem vaga; encaixe exige autorização.")
            if rescheduled_from:
                previous = Appointment.objects.select_for_update().get(pk=rescheduled_from.pk)
                if (
                    previous.status != Appointment.Status.BOOKED
                    or previous.patient_id != patient.pk
                ):
                    raise SchedulingConflict("Somente agendamento ativo pode ser remarcado.")
                previous.status = Appointment.Status.RESCHEDULED
                previous.save(update_fields=["status", "updated_at"])
            return Appointment.objects.create(
                slot=slot,
                patient=patient,
                overbooked=taken >= slot.capacity,
                reason=reason.strip(),
                rescheduled_from=rescheduled_from,
                booked_by=user,
                operation_key=operation_key,
            )
    except IntegrityError:
        existing = _retry(operation_key, user, slot, patient)
        if existing is None:
            raise SchedulingConflict("Paciente já agendado neste horário.") from None
        return existing


def _transition(user, appointment, capability, allowed, **changes):
    require_permission(user, capability)
    with transaction.atomic(), set_actor(user):
        appointment = (
            Appointment.objects.select_for_update().select_related("slot").get(pk=appointment.pk)
        )
        if appointment.status not in allowed:
            raise SchedulingConflict("Transição indevida para a situação atual.")
        for field, value in changes.items():
            setattr(appointment, field, value(appointment) if callable(value) else value)
        appointment.save(update_fields=[*changes, "updated_at"])
        return appointment


def cancel_appointment(*, user, appointment, reason):
    if not reason.strip():
        raise SchedulingConflict("Informe o motivo do cancelamento.")
    return _transition(
        user,
        appointment,
        "book_appointment",
        {Appointment.Status.BOOKED},
        status=Appointment.Status.CANCELLED,
        reason=reason.strip(),
    )


def mark_no_show(*, user, appointment):
    if appointment.slot.starts_at > timezone.now():
        raise SchedulingConflict("Falta só pode ser registrada após o horário.")
    return _transition(
        user,
        appointment,
        "checkin_appointment",
        {Appointment.Status.BOOKED},
        status=Appointment.Status.NO_SHOW,
    )


def _open_encounter(user, appointment):
    encounter = Encounter.objects.create(
        patient=appointment.patient,
        encounter_type=Encounter.Type.CONSULTATION,
        location=appointment.slot.location,
        responsible_professional=appointment.slot.professional,
        created_by=user,
    )
    transaction.on_commit(
        lambda: emit_clinical_event(
            event="encounter.created",
            patient_id=encounter.patient_id,
            encounter_id=encounter.pk,
            object_id=encounter.pk,
        )
    )
    return encounter


def check_in(*, user, appointment):
    """Chegada abre o encontro canonico do PEP; uma unica vez por agendamento."""
    if not can_access_patient(user, appointment.patient):
        raise PermissionDenied
    return _transition(
        user,
        appointment,
        "checkin_appointment",
        {Appointment.Status.BOOKED},
        status=Appointment.Status.CHECKED_IN,
        checked_in_at=lambda _: timezone.now(),
        encounter=lambda current: _open_encounter(user, current),
    )


def call_patient(*, user, appointment):
    return _transition(
        user,
        appointment,
        "checkin_appointment",
        {Appointment.Status.CHECKED_IN, Appointment.Status.CALLED},
        status=Appointment.Status.CALLED,
        called_at=lambda _: timezone.now(),
    )
