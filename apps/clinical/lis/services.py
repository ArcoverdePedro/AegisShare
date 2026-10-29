from auditlog.context import set_actor
from auditlog.signals import accessed
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from apps.clinical.pep.models import Encounter
from apps.clinical.pep.permissions import accessible_patients, require_module_permission

from .models import (
    LabResult,
    LabTest,
    ServiceRequest,
    ServiceRequestCancellation,
    Specimen,
    SpecimenEvent,
)


class LisConflict(ValueError):
    pass


def require_permission(user, capability=None):
    require_module_permission(user, "lis", "view_orders", capability)


def _lock_encounter(user, encounter_id, capability):
    require_permission(user, capability)
    encounter = get_object_or_404(Encounter.objects.select_for_update(), pk=encounter_id)
    get_object_or_404(accessible_patients(user), pk=encounter.patient_id)
    if encounter.status != Encounter.Status.OPEN:
        raise LisConflict("O encontro não está aberto. Consulte o histórico.")
    return encounter


def _retry_order(item, user, encounter_id, test_id):
    if (item.requested_by_id, item.encounter_id, item.lab_test_id) != (
        user.pk,
        encounter_id,
        test_id,
    ):
        raise LisConflict("Operação incompatível. Consulte o histórico.")
    accessed.send(ServiceRequest, instance=item)
    return item


@sensitive_variables()
def order_test(*, user, encounter_id, lab_test, operation_key):
    with transaction.atomic(), set_actor(user):
        encounter = _lock_encounter(user, encounter_id, "order_test")
        existing = ServiceRequest.objects.filter(operation_key=operation_key).first()
        if existing:
            return _retry_order(existing, user, encounter.pk, lab_test.pk)
        test = get_object_or_404(LabTest.objects.select_for_update(), pk=lab_test.pk)
        if not test.active:
            raise LisConflict("Selecione um exame disponível.")
        try:
            with transaction.atomic():
                return ServiceRequest.objects.create(
                    encounter=encounter,
                    lab_test=test,
                    test_code=test.code,
                    test_name=test.name,
                    specimen_type=test.specimen_type,
                    requested_by=user,
                    operation_key=operation_key,
                )
        except IntegrityError:
            existing = ServiceRequest.objects.filter(operation_key=operation_key).first()
            if existing is None:
                raise
            return _retry_order(existing, user, encounter.pk, test.pk)


def _retry_specimen(item, user, order, accession_code, collected_at):
    if (item.collected_by_id, item.service_request_id, item.accession_code, item.collected_at) != (
        user.pk,
        order.pk,
        accession_code,
        collected_at,
    ):
        raise LisConflict("Operação incompatível. Consulte o histórico.")
    accessed.send(Specimen, instance=item)
    return item


@sensitive_variables()
def collect_specimen(*, user, order, accession_code, collected_at, operation_key, confirmed):
    from .forms import SpecimenForm

    with transaction.atomic(), set_actor(user):
        _lock_encounter(user, order.encounter_id, "collect_specimen")
        order = ServiceRequest.objects.select_for_update().get(pk=order.pk)
        # Reutiliza a validação de entrada também para chamadas internas.
        form = SpecimenForm(
            {
                "accession_code": accession_code,
                "collected_at": collected_at,
                "operation_key": operation_key,
                "confirmed": confirmed,
            },
            order=order,
        )
        if not form.is_valid():
            raise LisConflict("Dados de coleta inválidos. Revise o formulário.")
        accession_code = form.cleaned_data["accession_code"]
        collected_at = form.cleaned_data["collected_at"]
        existing = Specimen.objects.filter(operation_key=operation_key).first()
        if existing:
            return _retry_specimen(existing, user, order, accession_code, collected_at)
        if order.cancelled:
            raise LisConflict("Pedido cancelado. Consulte o histórico.")
        if order.specimen:
            raise LisConflict("A coleta já foi registrada. Consulte o histórico.")
        try:
            with transaction.atomic():
                return Specimen.objects.create(
                    service_request=order,
                    # Recoleta: liga a amostra nova a rejeitada mais recente.
                    replaces=order.specimens.filter(replaced_by__isnull=True).first(),
                    accession_code=accession_code,
                    collected_at=collected_at,
                    collected_by=user,
                    operation_key=operation_key,
                )
        except IntegrityError:
            existing = Specimen.objects.filter(operation_key=operation_key).first()
            if existing:
                return _retry_specimen(existing, user, order, accession_code, collected_at)
            if Specimen.objects.filter(accession_code=accession_code).exists():
                raise LisConflict(
                    "Código indisponível. Confira a identificação da amostra."
                ) from None
            raise


def _specimen_event(*, user, specimen, kind, reason, operation_key):
    existing = SpecimenEvent.objects.filter(operation_key=operation_key).first()
    if existing:
        if (existing.actor_id, existing.specimen_id, existing.kind) != (user.pk, specimen.pk, kind):
            raise LisConflict("Operação incompatível. Consulte o histórico.")
        return existing
    status = specimen.status
    if status == SpecimenEvent.Kind.REJECTED:
        raise LisConflict("Amostra rejeitada não avança; registre recoleta.")
    if kind == SpecimenEvent.Kind.RECEIVED and status == SpecimenEvent.Kind.RECEIVED:
        raise LisConflict("Amostra já recebida.")
    if specimen.service_request.cancelled:
        raise LisConflict("Pedido cancelado. Consulte o histórico.")
    return SpecimenEvent.objects.create(
        specimen=specimen, kind=kind, reason=reason, actor=user, operation_key=operation_key
    )


def _lock_specimen(user, capability, **lookup):
    require_permission(user, capability)
    specimen = get_object_or_404(
        Specimen.objects.select_for_update().select_related("service_request"), **lookup
    )
    _lock_encounter(user, specimen.service_request.encounter_id, capability)
    return specimen


def receive_specimen(*, user, accession_code, operation_key):
    """Leitura do codigo confirma somente o recebimento no laboratorio."""
    with transaction.atomic(), set_actor(user):
        specimen = _lock_specimen(user, "receive_specimen", accession_code=accession_code.strip())
        return _specimen_event(
            user=user,
            specimen=specimen,
            kind=SpecimenEvent.Kind.RECEIVED,
            reason="",
            operation_key=operation_key,
        )


def reject_specimen(*, user, specimen_id, reason, operation_key):
    if not reason.strip():
        raise LisConflict("Informe o motivo da rejeição.")
    with transaction.atomic(), set_actor(user):
        specimen = _lock_specimen(user, "receive_specimen", pk=specimen_id)
        return _specimen_event(
            user=user,
            specimen=specimen,
            kind=SpecimenEvent.Kind.REJECTED,
            reason=reason.strip(),
            operation_key=operation_key,
        )


def cancel_order(*, user, order_id, reason):
    if not reason.strip():
        raise LisConflict("Informe o motivo do cancelamento.")
    with transaction.atomic(), set_actor(user):
        order = get_object_or_404(ServiceRequest.objects.select_for_update(), pk=order_id)
        _lock_encounter(user, order.encounter_id, "cancel_order")
        if order.cancelled:
            raise LisConflict("Pedido já cancelado.")
        if order.specimen and order.specimen.status == SpecimenEvent.Kind.RECEIVED:
            raise LisConflict("Amostra já recebida: rejeite-a antes de cancelar o pedido.")
        return ServiceRequestCancellation.objects.create(
            service_request=order, reason=reason.strip(), cancelled_by=user
        )


RESULT_FIELDS = ("analyte", "value", "unit", "reference_range", "method")


def enter_result(*, user, specimen_id, operation_key, supersedes=None, reason="", **data):
    with transaction.atomic(), set_actor(user):
        specimen = _lock_specimen(user, "enter_result", pk=specimen_id)
        existing = LabResult.objects.filter(operation_key=operation_key).first()
        if existing:
            if (existing.entered_by_id, existing.specimen_id) != (user.pk, specimen.pk):
                raise LisConflict("Operação incompatível. Consulte o histórico.")
            return existing
        if specimen.status != SpecimenEvent.Kind.RECEIVED:
            raise LisConflict("Resultado exige amostra recebida e não rejeitada.")
        if specimen.service_request.cancelled:
            raise LisConflict("Pedido cancelado.")
        if supersedes:
            supersedes = LabResult.objects.select_for_update().get(pk=supersedes.pk)
            if (
                supersedes.specimen_id != specimen.pk
                or supersedes.status != LabResult.Status.RELEASED
            ):
                raise LisConflict("Só resultado liberado desta amostra pode ser retificado.")
            if hasattr(supersedes, "superseded_by"):
                raise LisConflict("Resultado já retificado.")
            if not reason.strip():
                raise LisConflict("Informe o motivo da retificação.")
        return LabResult.objects.create(
            specimen=specimen,
            supersedes=supersedes,
            reason=reason.strip(),
            entered_by=user,
            operation_key=operation_key,
            **{field: data.get(field, "").strip() for field in RESULT_FIELDS},
        )


def advance_result(*, user, result_id):
    """Registrado -> validado -> liberado; liberacao torna visivel ao solicitante."""
    with transaction.atomic(), set_actor(user):
        result = get_object_or_404(LabResult.objects.select_for_update(), pk=result_id)
        _lock_specimen(user, "validate_result", pk=result.specimen_id)
        now = timezone.now()
        if result.status == LabResult.Status.ENTERED:
            result.status, result.validated_by, result.validated_at = "VALIDATED", user, now
        elif result.status == LabResult.Status.VALIDATED:
            result.status, result.released_by, result.released_at = "RELEASED", user, now
        else:
            raise LisConflict("Resultado já liberado; use retificação.")
        result.save(
            update_fields=["status", "validated_by", "validated_at", "released_by", "released_at"]
        )
        return result
