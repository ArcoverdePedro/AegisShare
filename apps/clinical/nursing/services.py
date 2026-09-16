import uuid

from auditlog.context import set_actor
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.clinical.pep.models import Encounter
from apps.clinical.prescription.models import MedicationDispenseItem

from .events import emit_medication_administered_event, emit_vitals_recorded_event
from .models import MedicationAdministration, VitalSignsRecord
from .permissions import can_administer_dispense_item, can_record_vitals

MEASURE_FIELDS = (
    "temperature_c",
    "heart_rate_bpm",
    "respiratory_rate_irpm",
    "systolic_bp_mmhg",
    "diastolic_bp_mmhg",
    "oxygen_saturation_pct",
    "weight_kg",
)


class VitalSignsIdempotencyConflictError(RuntimeError):
    """Conflito idempotente seguro, sem PHI ou detalhes de banco."""


class MedicationAdministrationIdempotencyConflictError(RuntimeError):
    """Conflito idempotente seguro de administração."""


class MedicationAdministrationStateError(RuntimeError):
    """Estado incompatível com administração, sem expor detalhes clínicos."""


def _normalize_idempotency_key(value):
    if value is None:
        return uuid.uuid4()
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise VitalSignsIdempotencyConflictError(
            "Chave de idempotência inválida."
        ) from exc


def _validate_existing_operation(
    existing,
    *,
    encounter,
    actor,
    data,
    replaces,
    origin,
):
    replaces_id = getattr(replaces, "pk", None)
    same_operation = (
        existing.encounter_id == encounter.pk
        and existing.recorded_by_id == actor.pk
        and existing.recorded_at == data["recorded_at"]
        and existing.replaces_id == replaces_id
        and existing.origin == origin
        and all(getattr(existing, field) == data.get(field) for field in MEASURE_FIELDS)
    )
    if not same_operation:
        raise VitalSignsIdempotencyConflictError(
            "Esta chave de idempotência já foi usada em outro registro de sinais vitais."
        )
    return existing


def _resolve_collision(
    *,
    idempotency_key,
    encounter,
    actor,
    data,
    replaces,
    origin,
):
    current_encounter = Encounter.objects.select_related("patient").get(pk=encounter.pk)
    if not can_record_vitals(actor, current_encounter):
        raise PermissionDenied

    existing = VitalSignsRecord.objects.filter(
        idempotency_key=idempotency_key
    ).first()
    if existing is None:
        return None
    return _validate_existing_operation(
        existing,
        encounter=current_encounter,
        actor=actor,
        data=data,
        replaces=replaces,
        origin=origin,
    )


def record_vital_signs(
    *,
    encounter,
    actor,
    data,
    idempotency_key=None,
    replaces=None,
    origin=VitalSignsRecord.Origin.ONLINE,
):
    """Persiste sinais vitais de forma atômica e idempotente."""

    idempotency_key = _normalize_idempotency_key(idempotency_key)

    try:
        with transaction.atomic():
            current_encounter = (
                Encounter.objects.select_for_update()
                .select_related("patient")
                .get(pk=encounter.pk)
            )
            if not can_record_vitals(actor, current_encounter):
                raise PermissionDenied

            existing = (
                VitalSignsRecord.objects.select_for_update()
                .filter(idempotency_key=idempotency_key)
                .first()
            )
            if existing is not None:
                return _validate_existing_operation(
                    existing,
                    encounter=current_encounter,
                    actor=actor,
                    data=data,
                    replaces=replaces,
                    origin=origin,
                )

            record = VitalSignsRecord(
                encounter=current_encounter,
                recorded_by=actor,
                recorded_at=data["recorded_at"],
                idempotency_key=idempotency_key,
                replaces=replaces,
                origin=origin,
                **{field: data.get(field) for field in MEASURE_FIELDS},
            )
            with set_actor(actor):
                record.save()
            emit_vitals_recorded_event(
                record_id=record.pk,
                encounter_id=current_encounter.pk,
                origin=record.origin,
                replaces_id=record.replaces_id,
            )
            return record
    except IntegrityError:
        existing = _resolve_collision(
            idempotency_key=idempotency_key,
            encounter=encounter,
            actor=actor,
            data=data,
            replaces=replaces,
            origin=origin,
        )
        if existing is not None:
            return existing
        raise
    except ValidationError as exc:
        errors = getattr(exc, "message_dict", {})
        if set(errors) != {"idempotency_key"}:
            raise
        existing = _resolve_collision(
            idempotency_key=idempotency_key,
            encounter=encounter,
            actor=actor,
            data=data,
            replaces=replaces,
            origin=origin,
        )
        if existing is not None:
            return existing
        raise


def _normalize_operation_key(value):
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise MedicationAdministrationIdempotencyConflictError(
            "Chave de operação inválida."
        ) from exc


def _administration_item_queryset():
    return MedicationDispenseItem.objects.select_related(
        "dispense__medication_request__encounter__patient",
        "request_item__drug",
        "lot__stock_item",
    )


def _validate_administration_state(*, actor, dispense_item, data):
    medication_request = dispense_item.dispense.medication_request
    encounter = medication_request.encounter
    if not can_administer_dispense_item(actor, dispense_item):
        raise PermissionDenied
    if dispense_item.request_item.medication_request_id != medication_request.pk:
        raise MedicationAdministrationStateError("Item dispensado incompatível.")
    if dispense_item.lot.stock_item.drug_id != dispense_item.request_item.drug_id:
        raise MedicationAdministrationStateError("Item dispensado incompatível.")

    administered_at = data["administered_at"]
    if administered_at > timezone.now():
        raise MedicationAdministrationStateError("Momento da administração inválido.")
    if administered_at < encounter.started_at.replace(microsecond=0):
        raise MedicationAdministrationStateError("Momento da administração inválido.")
    if administered_at < dispense_item.dispense.dispensed_at.replace(microsecond=0):
        raise MedicationAdministrationStateError("Momento da administração inválido.")
    return dispense_item


def _normalize_administered_unit(value):
    return " ".join((value or "").split())


def _validate_existing_administration(
    existing,
    *,
    dispense_item,
    actor,
    data,
):
    same_operation = (
        existing.dispense_item_id == dispense_item.pk
        and existing.administered_by_id == actor.pk
        and existing.administered_at == data["administered_at"]
        and existing.administered_dose == data["administered_dose"]
        and existing.administered_dose_unit
        == _normalize_administered_unit(data["administered_dose_unit"])
    )
    if not same_operation:
        raise MedicationAdministrationIdempotencyConflictError(
            "Esta chave de operação já foi usada em outra administração."
        )
    return existing


def _resolve_administration_collision(
    *,
    dispense_item_id,
    actor,
    data,
    operation_key,
):
    try:
        dispense_item = _administration_item_queryset().get(pk=dispense_item_id)
    except MedicationDispenseItem.DoesNotExist as exc:
        raise MedicationAdministrationStateError("Item dispensado indisponível.") from exc
    _validate_administration_state(
        actor=actor,
        dispense_item=dispense_item,
        data=data,
    )

    existing = MedicationAdministration.objects.filter(operation_key=operation_key).first()
    if existing is None:
        return None
    return _validate_existing_administration(
        existing,
        dispense_item=dispense_item,
        actor=actor,
        data=data,
    )


def administer_medication(
    *,
    dispense_item_id,
    actor,
    data,
    operation_key,
):
    """Confirma uma administração online de forma atômica e idempotente."""

    operation_key = _normalize_operation_key(operation_key)
    administered_dose_unit = _normalize_administered_unit(data["administered_dose_unit"])
    normalized_data = {
        **data,
        "administered_dose_unit": administered_dose_unit,
    }

    try:
        with transaction.atomic():
            try:
                dispense_item = (
                    _administration_item_queryset()
                    .select_for_update()
                    .get(pk=dispense_item_id)
                )
            except MedicationDispenseItem.DoesNotExist as exc:
                raise MedicationAdministrationStateError(
                    "Item dispensado indisponível."
                ) from exc

            _validate_administration_state(
                actor=actor,
                dispense_item=dispense_item,
                data=normalized_data,
            )

            existing = (
                MedicationAdministration.objects.select_for_update()
                .filter(operation_key=operation_key)
                .first()
            )
            if existing is not None:
                return _validate_existing_administration(
                    existing,
                    dispense_item=dispense_item,
                    actor=actor,
                    data=normalized_data,
                )

            administration = MedicationAdministration(
                dispense_item=dispense_item,
                administered_by=actor,
                administered_at=normalized_data["administered_at"],
                administered_dose=normalized_data["administered_dose"],
                administered_dose_unit=administered_dose_unit,
                operation_key=operation_key,
            )
            with set_actor(actor):
                administration.save()
            emit_medication_administered_event(
                administration_id=administration.pk,
                dispense_item_id=dispense_item.pk,
                encounter_id=dispense_item.dispense.medication_request.encounter_id,
            )
            return administration
    except IntegrityError:
        existing = _resolve_administration_collision(
            dispense_item_id=dispense_item_id,
            actor=actor,
            data=normalized_data,
            operation_key=operation_key,
        )
        if existing is not None:
            return existing
        raise
    except ValidationError as exc:
        errors = getattr(exc, "message_dict", {})
        if set(errors) != {"operation_key"}:
            raise
        existing = _resolve_administration_collision(
            dispense_item_id=dispense_item_id,
            actor=actor,
            data=normalized_data,
            operation_key=operation_key,
        )
        if existing is not None:
            return existing
        raise
