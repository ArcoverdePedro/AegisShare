from auditlog.context import set_actor
from auditlog.signals import accessed
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.views.decorators.debug import sensitive_variables

from apps.clinical.pep.models import Encounter
from apps.clinical.pep.permissions import accessible_patients, is_internal_professional

from .models import ImagingExam, ImagingOrder


class RisConflict(ValueError):
    pass


def require_permission(user, capability=None):
    permissions = ["ris.view_orders"]
    if capability:
        permissions.append(f"ris.{capability}")
    if not is_internal_professional(user) or not user.has_perms(permissions):
        raise PermissionDenied


def _lock_encounter(user, encounter_id, capability):
    require_permission(user, capability)
    encounter = get_object_or_404(Encounter.objects.select_for_update(), pk=encounter_id)
    get_object_or_404(accessible_patients(user), pk=encounter.patient_id)
    if encounter.status != Encounter.Status.OPEN:
        raise RisConflict("O encontro não está aberto. Consulte o histórico.")
    return encounter


def _retry_order(item, user, encounter_id, exam_id):
    if (item.requested_by_id, item.encounter_id, item.exam_id) != (
        user.pk,
        encounter_id,
        exam_id,
    ):
        raise RisConflict("Operação incompatível. Consulte o histórico.")
    accessed.send(ImagingOrder, instance=item)
    return item


@sensitive_variables()
def order_exam(*, user, encounter_id, exam, operation_key):
    with transaction.atomic(), set_actor(user):
        encounter = _lock_encounter(user, encounter_id, "order_exam")
        existing = ImagingOrder.objects.filter(operation_key=operation_key).first()
        if existing:
            return _retry_order(existing, user, encounter.pk, exam.pk)
        current_exam = get_object_or_404(ImagingExam.objects.select_for_update(), pk=exam.pk)
        if not current_exam.active:
            raise RisConflict("Selecione um exame disponível.")
        try:
            with transaction.atomic():
                return ImagingOrder.objects.create(
                    encounter=encounter,
                    exam=current_exam,
                    exam_code=current_exam.code,
                    exam_name=current_exam.name,
                    requested_by=user,
                    operation_key=operation_key,
                )
        except IntegrityError as exc:
            constraint = getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None)
            if (
                constraint != "uniq_ris_operation_key"
                and str(exc) != "UNIQUE constraint failed: ris_imagingorder.operation_key"
            ):
                raise
            existing = ImagingOrder.objects.filter(operation_key=operation_key).first()
            if existing is None:
                raise
            return _retry_order(existing, user, encounter.pk, current_exam.pk)
