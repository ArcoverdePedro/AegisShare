import uuid

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.clinical.pep.models import Encounter

from .models import Admission, Bed, BedOccupancy
from .permissions import can_admit_to_bed


class AdtConflictError(RuntimeError):
    """Conflito operacional seguro, sem detalhes de banco ou PHI."""


class BedUnavailableError(AdtConflictError):
    pass


class AdmissionStateError(AdtConflictError):
    pass


class IdempotencyConflictError(AdtConflictError):
    pass


def _normalize_operation_key(operation_key):
    if isinstance(operation_key, uuid.UUID):
        return operation_key
    try:
        return uuid.UUID(str(operation_key))
    except (TypeError, ValueError, AttributeError) as exc:
        raise IdempotencyConflictError("Chave de operação inválida.") from exc


def _validate_existing_operation(existing, *, encounter_id, bed_id, actor):
    occupancy = (
        existing.occupancies.filter(ended_at__isnull=True)
        .select_related("bed__location")
        .first()
    )
    if existing.encounter_id != encounter_id or not occupancy or occupancy.bed_id != bed_id:
        raise IdempotencyConflictError(
            "Esta chave de operação já foi usada em outra admissão."
        )
    if not can_admit_to_bed(actor, existing.encounter, occupancy.bed):
        raise PermissionDenied
    return existing


def admit_patient(*, encounter_id, bed_id, actor, operation_key, admitted_at=None):
    """Cria admissão e primeira ocupação de forma atômica e idempotente."""

    operation_key = _normalize_operation_key(operation_key)
    admitted_at = admitted_at or timezone.now()

    try:
        with transaction.atomic():
            existing = (
                Admission.objects.select_for_update()
                .select_related("encounter__patient")
                .filter(operation_key=operation_key)
                .first()
            )
            if existing:
                return _validate_existing_operation(
                    existing,
                    encounter_id=encounter_id,
                    bed_id=bed_id,
                    actor=actor,
                )

            encounter = (
                Encounter.objects.select_for_update()
                .select_related("patient")
                .get(pk=encounter_id)
            )
            bed = Bed.objects.select_for_update().select_related("location").get(pk=bed_id)

            if not can_admit_to_bed(actor, encounter, bed):
                raise PermissionDenied
            if encounter.encounter_type != Encounter.Type.INPATIENT:
                raise AdmissionStateError("O encontro não é uma internação.")
            if encounter.status != Encounter.Status.OPEN:
                raise AdmissionStateError("O encontro não está aberto.")
            if admitted_at < encounter.started_at:
                raise AdmissionStateError(
                    "A admissão não pode ser anterior ao início do encontro."
                )
            if not bed.active or bed.operational_status != Bed.OperationalStatus.AVAILABLE:
                raise BedUnavailableError("O leito não está disponível para admissão.")
            if Admission.objects.filter(encounter=encounter).exists():
                raise AdmissionStateError("Este encontro já possui admissão ADT.")
            if BedOccupancy.objects.filter(bed=bed, ended_at__isnull=True).exists():
                raise BedUnavailableError("O leito já possui uma ocupação ativa.")

            admission = Admission.objects.create(
                encounter=encounter,
                admitted_at=admitted_at,
                admitted_by=actor,
                operation_key=operation_key,
            )
            BedOccupancy.objects.create(
                admission=admission,
                bed=bed,
                started_at=admitted_at,
                started_by=actor,
            )
            return admission
    except IntegrityError as exc:
        raise AdtConflictError(
            "A admissão não pôde ser concluída porque o estado mudou. Atualize a tela e tente novamente."
        ) from exc
