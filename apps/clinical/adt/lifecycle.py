import uuid

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.clinical.pep.models import Encounter
from apps.clinical.pep.permissions import can_access_patient

from .events import emit_adt_event
from .models import Admission, Bed, BedOccupancy, Discharge, Transfer
from .permissions import (
    can_access_bed,
    can_discharge,
    can_discharge_admission,
    can_transfer,
    can_transfer_admission,
)
from .services import AdtConflictError, BedUnavailableError, IdempotencyConflictError


class TransferStateError(AdtConflictError):
    pass


class DischargeStateError(AdtConflictError):
    pass


def _operation_key(value):
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise IdempotencyConflictError("Chave de operação inválida.") from exc


def _existing_transfer(existing, admission_id, destination_bed_id, actor):
    existing = Transfer.objects.select_related(
        "admission__encounter__patient",
        "source_occupancy__bed__location",
        "destination_occupancy__bed__location",
    ).get(pk=existing.pk)
    if (
        existing.admission_id != admission_id
        or existing.destination_occupancy.bed_id != destination_bed_id
    ):
        raise IdempotencyConflictError(
            "Esta chave de operação já foi usada em outra transferência."
        )
    if not can_transfer(actor):
        raise PermissionDenied
    if not can_access_patient(actor, existing.admission.encounter.patient):
        raise PermissionDenied
    if not can_access_bed(actor, existing.source_occupancy.bed):
        raise PermissionDenied
    if not can_access_bed(actor, existing.destination_occupancy.bed):
        raise PermissionDenied
    return existing


def transfer_patient(
    *,
    admission_id,
    destination_bed_id,
    actor,
    operation_key,
    transferred_at=None,
    reason="",
):
    operation_key = _operation_key(operation_key)
    transferred_at = transferred_at or timezone.now()
    try:
        with transaction.atomic():
            existing = (
                Transfer.objects.select_for_update()
                .filter(operation_key=operation_key)
                .first()
            )
            if existing:
                return _existing_transfer(
                    existing, admission_id, destination_bed_id, actor
                )

            admission = (
                Admission.objects.select_for_update()
                .select_related("encounter__patient")
                .get(pk=admission_id)
            )
            encounter = (
                Encounter.objects.select_for_update()
                .select_related("patient")
                .get(pk=admission.encounter_id)
            )
            admission.encounter = encounter
            current = (
                BedOccupancy.objects.select_for_update()
                .select_related("bed__location")
                .filter(admission=admission, ended_at__isnull=True)
                .first()
            )
            destination = (
                Bed.objects.select_for_update()
                .select_related("location")
                .get(pk=destination_bed_id)
            )

            if not current:
                raise TransferStateError("A admissão não possui ocupação ativa.")
            if not can_transfer_admission(actor, admission, destination):
                raise PermissionDenied
            if Discharge.objects.filter(admission=admission).exists():
                raise TransferStateError("A admissão já possui alta registrada.")
            if encounter.status != Encounter.Status.OPEN:
                raise TransferStateError("O encontro não está aberto.")
            if current.bed_id == destination.pk:
                raise TransferStateError("Selecione outro leito de destino.")
            if transferred_at < current.started_at:
                raise TransferStateError(
                    "A transferência não pode anteceder a ocupação atual."
                )
            if (
                not destination.active
                or destination.operational_status != Bed.OperationalStatus.AVAILABLE
                or BedOccupancy.objects.filter(
                    bed=destination, ended_at__isnull=True
                ).exists()
            ):
                raise BedUnavailableError("O leito de destino não está disponível.")

            source_bed = current.bed
            current.ended_at = transferred_at
            current.ended_by = actor
            current.end_reason = BedOccupancy.EndReason.TRANSFER
            current.save(update_fields=["ended_at", "ended_by", "end_reason"])
            target = BedOccupancy.objects.create(
                admission=admission,
                bed=destination,
                started_at=transferred_at,
                started_by=actor,
            )
            transfer = Transfer.objects.create(
                admission=admission,
                source_occupancy=current,
                destination_occupancy=target,
                transferred_at=transferred_at,
                transferred_by=actor,
                reason=reason,
                operation_key=operation_key,
            )
            emit_adt_event(
                event_type="encounter.transferred",
                encounter_id=encounter.pk,
                admission_id=admission.pk,
                occupancy_id=target.pk,
                bed_id=destination.pk,
                location_id=destination.location_id,
            )
            emit_adt_event(
                event_type="bed.released",
                bed_id=source_bed.pk,
                location_id=source_bed.location_id,
                state=source_bed.operational_status,
            )
            emit_adt_event(
                event_type="bed.occupied",
                bed_id=destination.pk,
                location_id=destination.location_id,
                state="OCCUPIED",
            )
            return transfer
    except IntegrityError as exc:
        raise AdtConflictError(
            "A transferência não pôde ser concluída porque o estado mudou."
        ) from exc


def _existing_discharge(existing, admission_id, disposition, actor):
    existing = Discharge.objects.select_related(
        "admission__encounter__patient", "final_occupancy__bed__location"
    ).get(pk=existing.pk)
    if existing.admission_id != admission_id or existing.disposition != disposition:
        raise IdempotencyConflictError(
            "Esta chave de operação já foi usada em outra alta."
        )
    if not can_discharge(actor):
        raise PermissionDenied
    if not can_access_patient(actor, existing.admission.encounter.patient):
        raise PermissionDenied
    if not can_access_bed(actor, existing.final_occupancy.bed):
        raise PermissionDenied
    return existing


def discharge_patient(
    *,
    admission_id,
    disposition,
    actor,
    operation_key,
    discharged_at=None,
    reason="",
):
    operation_key = _operation_key(operation_key)
    discharged_at = discharged_at or timezone.now()
    try:
        with transaction.atomic():
            existing = (
                Discharge.objects.select_for_update()
                .filter(operation_key=operation_key)
                .first()
            )
            if existing:
                return _existing_discharge(existing, admission_id, disposition, actor)

            admission = (
                Admission.objects.select_for_update()
                .select_related("encounter__patient")
                .get(pk=admission_id)
            )
            encounter = (
                Encounter.objects.select_for_update()
                .select_related("patient")
                .get(pk=admission.encounter_id)
            )
            admission.encounter = encounter
            current = (
                BedOccupancy.objects.select_for_update()
                .select_related("bed__location")
                .filter(admission=admission, ended_at__isnull=True)
                .first()
            )

            if not current:
                raise DischargeStateError("A admissão não possui ocupação ativa.")
            if not can_discharge_admission(actor, admission):
                raise PermissionDenied
            if Discharge.objects.filter(admission=admission).exists():
                raise DischargeStateError("A admissão já possui alta registrada.")
            if encounter.status != Encounter.Status.OPEN:
                raise DischargeStateError("O encontro não está aberto.")
            if discharged_at < admission.admitted_at or discharged_at < current.started_at:
                raise DischargeStateError(
                    "A alta não pode anteceder a admissão ou a ocupação atual."
                )
            if disposition not in Discharge.Disposition.values:
                raise DischargeStateError("Destino de alta inválido.")

            final_bed = current.bed
            current.ended_at = discharged_at
            current.ended_by = actor
            current.end_reason = BedOccupancy.EndReason.DISCHARGE
            current.save(update_fields=["ended_at", "ended_by", "end_reason"])
            discharge = Discharge.objects.create(
                admission=admission,
                final_occupancy=current,
                discharged_at=discharged_at,
                disposition=disposition,
                reason=reason,
                discharged_by=actor,
                operation_key=operation_key,
            )
            encounter.status = Encounter.Status.CLOSED
            encounter.ended_at = discharged_at
            encounter.save(update_fields=["status", "ended_at", "updated_at"])
            emit_adt_event(
                event_type="encounter.discharged",
                encounter_id=encounter.pk,
                admission_id=admission.pk,
                occupancy_id=current.pk,
                bed_id=final_bed.pk,
                location_id=final_bed.location_id,
            )
            emit_adt_event(
                event_type="bed.released",
                bed_id=final_bed.pk,
                location_id=final_bed.location_id,
                state=final_bed.operational_status,
            )
            return discharge
    except IntegrityError as exc:
        raise AdtConflictError(
            "A alta não pôde ser concluída porque o estado mudou."
        ) from exc
