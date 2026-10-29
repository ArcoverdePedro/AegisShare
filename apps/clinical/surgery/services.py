from auditlog.context import set_actor
from auditlog.signals import accessed
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from apps.admin.hr.models import absent_on
from apps.clinical.pep.models import Encounter
from apps.clinical.pep.permissions import accessible_patients, require_module_permission

from .models import OperatingRoom, Procedure, SurgeryExecution, SurgerySchedule, SurgicalCase


class SurgeryConflict(ValueError):
    pass


def require_permission(user, capability=None):
    require_module_permission(user, "surgery", "view_cases", capability)


def _lock_encounter(user, encounter_id, capability):
    require_permission(user, capability)
    encounter = get_object_or_404(Encounter.objects.select_for_update(), pk=encounter_id)
    get_object_or_404(accessible_patients(user), pk=encounter.patient_id)
    if encounter.status != Encounter.Status.OPEN:
        raise SurgeryConflict("O encontro não está aberto. Consulte o histórico.")
    return encounter


def _retry_case(item, user, encounter_id, procedure_id):
    if (item.requested_by_id, item.encounter_id, item.procedure_id) != (
        user.pk,
        encounter_id,
        procedure_id,
    ):
        raise SurgeryConflict("Operação incompatível. Consulte o histórico.")
    accessed.send(SurgicalCase, instance=item)
    return item


@sensitive_variables()
def request_procedure(*, user, encounter_id, procedure, operation_key):
    with transaction.atomic(), set_actor(user):
        encounter = _lock_encounter(user, encounter_id, "request_procedure")
        existing = SurgicalCase.objects.filter(operation_key=operation_key).first()
        if existing:
            return _retry_case(existing, user, encounter.pk, procedure.pk)
        current_procedure = get_object_or_404(
            Procedure.objects.select_for_update(), pk=procedure.pk
        )
        if not current_procedure.active:
            raise SurgeryConflict("Selecione um procedimento disponível.")
        try:
            with transaction.atomic():
                return SurgicalCase.objects.create(
                    encounter=encounter,
                    procedure=current_procedure,
                    procedure_code=current_procedure.code,
                    procedure_name=current_procedure.name,
                    requested_by=user,
                    operation_key=operation_key,
                )
        except IntegrityError:
            # Outra requisicao gravou a mesma chave ao mesmo tempo: devolve o registro dela.
            existing = SurgicalCase.objects.filter(operation_key=operation_key).first()
            if existing is None:
                raise
            return _retry_case(existing, user, encounter.pk, current_procedure.pk)


def _overlapping(queryset, starts_at, ends_at):
    return queryset.filter(
        status=SurgerySchedule.Status.SCHEDULED, starts_at__lt=ends_at, ends_at__gt=starts_at
    )


def schedule_case(
    *, user, case, room, surgeon, starts_at, ends_at, operation_key, rescheduled_from=None
):
    with transaction.atomic(), set_actor(user):
        _lock_encounter(user, case.encounter_id, "schedule_case")
        existing = SurgerySchedule.objects.filter(operation_key=operation_key).first()
        if existing:
            if (existing.scheduled_by_id, existing.case_id, existing.room_id) != (
                user.pk,
                case.pk,
                room.pk,
            ):
                raise SurgeryConflict("Operação incompatível. Consulte o histórico.")
            return existing
        # Trava sala e depois cirurgiao (ordem fixa): reservas concorrentes nao se sobrepoem.
        room = OperatingRoom.objects.select_for_update().get(pk=room.pk)
        surgeon = get_user_model().objects.select_for_update().get(pk=surgeon.pk)
        if not room.active:
            raise SurgeryConflict("Sala inativa.")
        if ends_at <= starts_at or starts_at <= timezone.now():
            raise SurgeryConflict("Informe um período futuro válido.")
        if absent_on(surgeon, timezone.localtime(starts_at).date()):
            raise SurgeryConflict("Cirurgião com ausência registrada nesta data.")
        others = SurgerySchedule.objects.exclude(pk=getattr(rescheduled_from, "pk", None))
        if _overlapping(others.filter(room=room), starts_at, ends_at).exists():
            raise SurgeryConflict("Sala já reservada no período.")
        if _overlapping(others.filter(surgeon=surgeon), starts_at, ends_at).exists():
            raise SurgeryConflict("Cirurgião já reservado no período.")
        if rescheduled_from:
            previous = SurgerySchedule.objects.select_for_update().get(pk=rescheduled_from.pk)
            if (
                previous.status != SurgerySchedule.Status.SCHEDULED
                or previous.case_id != case.pk
                or previous.executions.exists()
            ):
                raise SurgeryConflict("Somente agendamento vigente pode ser remarcado.")
            previous.status = SurgerySchedule.Status.RESCHEDULED
            previous.save(update_fields=["status", "updated_at"])
        elif case.schedules.filter(status=SurgerySchedule.Status.SCHEDULED).exists():
            raise SurgeryConflict("Caso já agendado; use remarcação.")
        return SurgerySchedule.objects.create(
            case=case,
            room=room,
            surgeon=surgeon,
            starts_at=starts_at,
            ends_at=ends_at,
            rescheduled_from=rescheduled_from,
            scheduled_by=user,
            operation_key=operation_key,
        )


def cancel_schedule(*, user, schedule, reason):
    if not reason.strip():
        raise SurgeryConflict("Informe o motivo do cancelamento.")
    with transaction.atomic(), set_actor(user):
        _lock_encounter(user, schedule.case.encounter_id, "schedule_case")
        schedule = SurgerySchedule.objects.select_for_update().get(pk=schedule.pk)
        if schedule.status != SurgerySchedule.Status.SCHEDULED:
            raise SurgeryConflict("Agendamento não está vigente.")
        if schedule.executions.exists():
            raise SurgeryConflict("Cirurgia já executada não pode ser cancelada.")
        schedule.status = SurgerySchedule.Status.CANCELLED
        schedule.reason = reason.strip()
        schedule.save(update_fields=["status", "reason", "updated_at"])
        return schedule


def record_execution(*, user, schedule, team=(), supersedes=None, reason="", **data):
    with transaction.atomic(), set_actor(user):
        _lock_encounter(user, schedule.case.encounter_id, "record_execution")
        schedule = SurgerySchedule.objects.select_for_update().get(pk=schedule.pk)
        if schedule.status != SurgerySchedule.Status.SCHEDULED:
            raise SurgeryConflict("Só agendamento vigente recebe registro de execução.")
        current = schedule.executions.filter(superseded_by__isnull=True).first()
        if current != supersedes:
            raise SurgeryConflict("Execução já registrada; use correção da versão vigente.")
        if supersedes and not reason.strip():
            raise SurgeryConflict("Informe o motivo da correção.")
        if not (
            data["room_in_at"] <= data["started_at"] <= data["ended_at"] <= data["room_out_at"]
        ):
            raise SurgeryConflict("Horários fora de ordem (entrada ≤ início ≤ fim ≤ saída).")
        if data["room_out_at"] > timezone.now():
            raise SurgeryConflict("Registro de execução não pode estar no futuro.")
        execution = SurgeryExecution.objects.create(
            schedule=schedule,
            supersedes=supersedes,
            reason=reason.strip(),
            recorded_by=user,
            **data,
        )
        execution.team.set(team)
        return execution
