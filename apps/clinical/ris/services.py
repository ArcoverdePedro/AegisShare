from auditlog.context import set_actor
from auditlog.signals import accessed
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from apps.clinical.pep.models import Encounter
from apps.clinical.pep.permissions import accessible_patients, require_module_permission

from .models import ImagingExam, ImagingOrder, ImagingReport


class RisConflict(ValueError):
    pass


def require_permission(user, capability=None):
    require_module_permission(user, "ris", "view_orders", capability)


def _lock_encounter(user, encounter_id, capability, *, require_open=True):
    require_permission(user, capability)
    encounter = get_object_or_404(Encounter.objects.select_for_update(), pk=encounter_id)
    get_object_or_404(accessible_patients(user), pk=encounter.patient_id)
    if require_open and encounter.status != Encounter.Status.OPEN:
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
        except IntegrityError:
            # Outra requisicao gravou a mesma chave ao mesmo tempo: devolve o registro dela.
            existing = ImagingOrder.objects.filter(operation_key=operation_key).first()
            if existing is None:
                raise
            return _retry_order(existing, user, encounter.pk, current_exam.pk)


def write_report(*, user, order, performed_at, findings, impression, reason=""):
    with transaction.atomic(), set_actor(user):
        _lock_encounter(user, order.encounter_id, "write_report", require_open=False)
        order = ImagingOrder.objects.select_for_update().get(pk=order.pk)
        current = order.reports.filter(superseded_by__isnull=True).first()
        if current and not current.released_at:
            raise RisConflict("Há laudo aguardando liberação.")
        if current and not reason.strip():
            raise RisConflict("Informe o motivo da retificação.")
        if performed_at < order.requested_at or performed_at > timezone.now():
            raise RisConflict("Informe a realização entre o pedido e agora.")
        return ImagingReport.objects.create(
            order=order,
            performed_at=performed_at,
            findings=findings.strip(),
            impression=impression.strip(),
            supersedes=current,
            reason=reason.strip(),
            authored_by=user,
        )


def release_report(*, user, report_id):
    with transaction.atomic(), set_actor(user):
        report = get_object_or_404(ImagingReport.objects.select_for_update(), pk=report_id)
        _lock_encounter(user, report.order.encounter_id, "release_report", require_open=False)
        if report.released_at:
            raise RisConflict("Laudo já liberado.")
        report.released_by, report.released_at = user, timezone.now()
        report.save(update_fields=["released_by", "released_at"])
        return report
