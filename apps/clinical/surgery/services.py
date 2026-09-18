from auditlog.context import set_actor
from auditlog.signals import accessed
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.views.decorators.debug import sensitive_variables

from apps.clinical.pep.models import Encounter
from apps.clinical.pep.permissions import accessible_patients, is_internal_professional

from .models import Procedure, SurgicalCase


class SurgeryConflict(ValueError):
    pass


def require_permission(user, capability=None):
    permissions = ["surgery.view_cases"]
    if capability:
        permissions.append(f"surgery.{capability}")
    if not is_internal_professional(user) or not user.has_perms(permissions):
        raise PermissionDenied


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
        except IntegrityError as exc:
            constraint = getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None)
            if (
                constraint != "uniq_surgery_operation_key"
                and str(exc) != "UNIQUE constraint failed: surgery_surgicalcase.operation_key"
            ):
                raise
            existing = SurgicalCase.objects.filter(operation_key=operation_key).first()
            if existing is None:
                raise
            return _retry_case(existing, user, encounter.pk, current_procedure.pk)
