from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from .models import DoseRule, Drug, Interaction
from .permissions import can_manage_reference_data


class CatalogStateError(RuntimeError):
    """Conflito de governança seguro, sem detalhes internos."""


_DRUG_CLINICAL_FIELDS = (
    "code",
    "name",
    "presentation",
    "strength_text",
    "route_hint",
    "dispense_unit",
)


def _require_catalog_management(actor):
    if not can_manage_reference_data(actor):
        raise PermissionDenied


def _reference_approval(*, actor, active):
    if not active:
        return None, None
    return actor, timezone.now()


@transaction.atomic
def create_drug(
    *,
    actor,
    code,
    name,
    presentation,
    dispense_unit,
    strength_text="",
    route_hint="",
    active=True,
):
    _require_catalog_management(actor)
    return Drug.objects.create(
        code=code,
        name=name,
        presentation=presentation,
        strength_text=strength_text,
        route_hint=route_hint,
        dispense_unit=dispense_unit,
        active=active,
    )


@transaction.atomic
def update_drug(
    *,
    drug_id,
    actor,
    code,
    name,
    presentation,
    dispense_unit,
    strength_text="",
    route_hint="",
    active=True,
):
    """Atualiza catálogo sem reescrever significado histórico já prescrito."""
    _require_catalog_management(actor)
    drug = Drug.objects.select_for_update().get(pk=drug_id)
    incoming = {
        "code": code,
        "name": name,
        "presentation": presentation,
        "strength_text": strength_text,
        "route_hint": route_hint,
        "dispense_unit": dispense_unit,
    }
    if drug.request_items.exists() and any(
        getattr(drug, field) != value for field, value in incoming.items()
    ):
        raise CatalogStateError(
            "Medicamento já utilizado em prescrição não pode ter seus dados clínicos reescritos; desative-o e cadastre uma nova referência."
        )

    for field, value in incoming.items():
        setattr(drug, field, value)
    drug.active = active
    drug.save()
    return drug


@transaction.atomic
def create_interaction_reference(
    *,
    actor,
    drug_a_id,
    drug_b_id,
    severity,
    blocking,
    summary,
    reference_source,
    reference_version,
    active=False,
):
    _require_catalog_management(actor)
    approved_by, approved_at = _reference_approval(actor=actor, active=active)
    interaction = Interaction(
        drug_a_id=drug_a_id,
        drug_b_id=drug_b_id,
        severity=severity,
        blocking=blocking,
        summary=summary,
        reference_source=reference_source,
        reference_version=reference_version,
        approved_by=approved_by,
        approved_at=approved_at,
        active=active,
    )
    interaction.save()
    return interaction


@transaction.atomic
def set_interaction_reference_active(*, interaction_id, actor, active):
    _require_catalog_management(actor)
    interaction = Interaction.objects.select_for_update().get(pk=interaction_id)
    if interaction.active == active:
        return interaction
    interaction.active = active
    if active:
        interaction.approved_by = actor
        interaction.approved_at = timezone.now()
    interaction.save()
    return interaction


@transaction.atomic
def create_dose_rule_reference(
    *,
    actor,
    drug_id,
    rule_code,
    basis,
    dose_unit,
    reference_source,
    reference_version,
    min_age_days=None,
    max_age_days=None,
    min_weight_kg=None,
    max_weight_kg=None,
    min_dose=None,
    max_dose=None,
    per_kg=False,
    active=False,
):
    _require_catalog_management(actor)
    approved_by, approved_at = _reference_approval(actor=actor, active=active)
    rule = DoseRule(
        drug_id=drug_id,
        rule_code=rule_code,
        basis=basis,
        min_age_days=min_age_days,
        max_age_days=max_age_days,
        min_weight_kg=min_weight_kg,
        max_weight_kg=max_weight_kg,
        min_dose=min_dose,
        max_dose=max_dose,
        dose_unit=dose_unit,
        per_kg=per_kg,
        reference_source=reference_source,
        reference_version=reference_version,
        approved_by=approved_by,
        approved_at=approved_at,
        active=active,
    )
    rule.save()
    return rule


@transaction.atomic
def set_dose_rule_reference_active(*, rule_id, actor, active):
    _require_catalog_management(actor)
    rule = DoseRule.objects.select_for_update().get(pk=rule_id)
    if rule.active == active:
        return rule
    rule.active = active
    if active:
        rule.approved_by = actor
        rule.approved_at = timezone.now()
    rule.save()
    return rule
