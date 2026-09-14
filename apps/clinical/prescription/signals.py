from django.core.exceptions import ValidationError
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver

from .models import DoseRule, Interaction, MedicationRequest, MedicationRequestItem


_ITEM_MUTATION_ERROR = "Itens só podem ser alterados enquanto a prescrição está em rascunho."
_ITEM_DELETE_ERROR = "Itens submetidos não podem ser excluídos."
_APPROVED_REFERENCE_ERROR = (
    "Referência farmacêutica aprovada é imutável; crie uma nova versão para alterar seu conteúdo."
)
_REACTIVATION_ERROR = (
    "Referência farmacêutica aprovada e desativada não pode ser reativada; crie uma nova versão."
)

_INTERACTION_GOVERNED_FIELDS = (
    "drug_a_id",
    "drug_b_id",
    "severity",
    "blocking",
    "summary",
    "reference_source",
    "reference_version",
    "approved_by_id",
    "approved_at",
)
_DOSE_RULE_GOVERNED_FIELDS = (
    "drug_id",
    "rule_code",
    "basis",
    "min_age_days",
    "max_age_days",
    "min_weight_kg",
    "max_weight_kg",
    "min_dose",
    "max_dose",
    "dose_unit",
    "per_kg",
    "reference_source",
    "reference_version",
    "approved_by_id",
    "approved_at",
)


def _persisted_request_status(instance):
    if not instance.medication_request_id:
        return None
    return (
        MedicationRequest.objects.filter(pk=instance.medication_request_id)
        .values_list("status", flat=True)
        .first()
    )


def _enforce_approved_reference_immutability(sender, instance, governed_fields):
    if instance._state.adding or not instance.pk:
        return

    persisted = sender.objects.filter(pk=instance.pk).values(
        "active",
        *governed_fields,
    ).first()
    if not persisted or persisted["approved_at"] is None:
        return

    if any(persisted[field] != getattr(instance, field) for field in governed_fields):
        raise ValidationError(_APPROVED_REFERENCE_ERROR)
    if not persisted["active"] and instance.active:
        raise ValidationError(_REACTIVATION_ERROR)


@receiver(pre_save, sender=MedicationRequestItem)
def enforce_draft_request_on_item_save(sender, instance, **kwargs):
    """Não confia no FK em cache ao decidir se um item ainda pode ser gravado."""
    status = _persisted_request_status(instance)
    if status is not None and status != MedicationRequest.Status.DRAFT:
        raise ValidationError(_ITEM_MUTATION_ERROR)


@receiver(pre_delete, sender=MedicationRequestItem)
def enforce_draft_request_on_item_delete(sender, instance, **kwargs):
    """Bloqueia exclusão quando a prescrição persistida já saiu de DRAFT."""
    status = _persisted_request_status(instance)
    if status is not None and status != MedicationRequest.Status.DRAFT:
        raise ValidationError(_ITEM_DELETE_ERROR)


@receiver(pre_save, sender=Interaction)
def enforce_approved_interaction_immutability(sender, instance, **kwargs):
    _enforce_approved_reference_immutability(
        sender,
        instance,
        _INTERACTION_GOVERNED_FIELDS,
    )


@receiver(pre_save, sender=DoseRule)
def enforce_approved_dose_rule_immutability(sender, instance, **kwargs):
    _enforce_approved_reference_immutability(
        sender,
        instance,
        _DOSE_RULE_GOVERNED_FIELDS,
    )
