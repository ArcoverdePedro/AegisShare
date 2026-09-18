from auditlog.context import set_actor
from auditlog.signals import accessed
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.views.decorators.debug import sensitive_variables

from apps.clinical.pep.models import Encounter
from apps.clinical.pep.permissions import accessible_patients, is_internal_professional

from .models import LabTest, ServiceRequest, Specimen


class LisConflict(ValueError):
    pass


def require_permission(user, capability=None):
    permissions = ["lis.view_orders"]
    if capability:
        permissions.append(f"lis.{capability}")
    if not is_internal_professional(user) or not user.has_perms(permissions):
        raise PermissionDenied


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
        if Specimen.objects.filter(service_request=order).exists():
            raise LisConflict("A coleta já foi registrada. Consulte o histórico.")
        try:
            with transaction.atomic():
                return Specimen.objects.create(
                    service_request=order,
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
