import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from apps.clinical.pep.models import Encounter

from .models import VitalSignsRecord
from .permissions import can_record_vitals

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
            record.save()
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
