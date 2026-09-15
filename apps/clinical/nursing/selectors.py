from .models import VitalSignsRecord


def latest_weight_fact(*, encounter=None, patient=None):
    """Retorna o peso mais recente no escopo, sem decidir validade clínica."""
    if (encounter is None) == (patient is None):
        raise ValueError("Informe exatamente um escopo: encounter ou patient.")

    queryset = VitalSignsRecord.objects.filter(weight_kg__isnull=False)
    if encounter is not None:
        queryset = queryset.filter(encounter=encounter)
    else:
        queryset = queryset.filter(encounter__patient=patient)

    record = queryset.only(
        "id",
        "weight_kg",
        "recorded_at",
        "recorded_by_id",
        "encounter_id",
        "origin",
        "created_at",
    ).first()
    if record is None:
        return None

    return {
        "weight_kg": record.weight_kg,
        "recorded_at": record.recorded_at,
        "record_id": record.pk,
        "recorded_by_id": record.recorded_by_id,
        "encounter_id": record.encounter_id,
        "origin": record.origin,
    }
