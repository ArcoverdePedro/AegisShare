from django.core.exceptions import ValidationError
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver

from .models import (
    DoseRule,
    Drug,
    Interaction,
    Lot,
    MedicationDispense,
    MedicationDispenseItem,
    MedicationRequest,
    MedicationRequestItem,
    MedicationSafetyFinding,
    MedicationSafetyReview,
    StockItem,
    StockMovement,
)

_ITEM_MUTATION_ERROR = "Itens só podem ser alterados enquanto a prescrição está em rascunho."
_ITEM_DELETE_ERROR = "Itens submetidos não podem ser excluídos."
_REQUEST_DELETE_ERROR = "Prescrições submetidas não podem ser excluídas."
_LOT_BALANCE_ERROR = "Saldo de lote só pode ser alterado por movimentação de estoque."
_LOT_IDENTITY_ERROR = "Lote com movimentação não pode ter sua identidade histórica reescrita."
_STOCK_IDENTITY_ERROR = "Estoque com lotes não pode ter medicamento ou localização reescritos."
_APPEND_ONLY_DELETE_ERROR = "Registros farmacêuticos append-only não podem ser excluídos."
_APPROVED_REFERENCE_MUTATION_ERROR = "Referência clínica aprovada não pode ser reescrita."
_APPROVED_REFERENCE_DELETE_ERROR = "Referência clínica aprovada não pode ser excluída."
_APPROVED_REFERENCE_REACTIVATION_ERROR = (
    "Referência clínica aprovada e desativada exige uma nova versão para voltar ao uso."
)
_USED_DRUG_MUTATION_ERROR = (
    "Medicamento já utilizado em prescrição não pode ter seus dados históricos reescritos."
)
_DRUG_HISTORICAL_FIELDS = (
    "code",
    "name",
    "presentation",
    "strength_text",
    "route_hint",
    "dispense_unit",
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


def _preserve_approved_reference(sender, instance, governed_fields):
    if instance._state.adding or not instance.pk:
        return
    persisted = sender.objects.filter(pk=instance.pk).values(
        *governed_fields,
        "active",
    ).first()
    if not persisted or persisted["approved_at"] is None:
        return
    if any(persisted[field] != getattr(instance, field) for field in governed_fields):
        raise ValidationError(_APPROVED_REFERENCE_MUTATION_ERROR)
    if not persisted["active"] and instance.active:
        raise ValidationError(_APPROVED_REFERENCE_REACTIVATION_ERROR)


@receiver(pre_save, sender=Drug)
def preserve_used_drug_history(sender, instance, **kwargs):
    if instance._state.adding or not instance.pk:
        return
    if not MedicationRequestItem.objects.filter(drug_id=instance.pk).exists():
        return
    persisted = sender.objects.filter(pk=instance.pk).values(*_DRUG_HISTORICAL_FIELDS).first()
    if persisted and any(
        persisted[field] != getattr(instance, field) for field in _DRUG_HISTORICAL_FIELDS
    ):
        raise ValidationError(_USED_DRUG_MUTATION_ERROR)


@receiver(pre_save, sender=Interaction)
def preserve_approved_interaction(sender, instance, **kwargs):
    _preserve_approved_reference(sender, instance, _INTERACTION_GOVERNED_FIELDS)


@receiver(pre_save, sender=DoseRule)
def preserve_approved_dose_rule(sender, instance, **kwargs):
    _preserve_approved_reference(sender, instance, _DOSE_RULE_GOVERNED_FIELDS)


@receiver(pre_delete, sender=Interaction)
@receiver(pre_delete, sender=DoseRule)
def prevent_approved_reference_delete(sender, instance, **kwargs):
    if instance.pk and sender.objects.filter(pk=instance.pk, approved_at__isnull=False).exists():
        raise ValidationError(_APPROVED_REFERENCE_DELETE_ERROR)


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


@receiver(pre_delete, sender=MedicationRequest)
def preserve_submitted_request_history(sender, instance, **kwargs):
    """Consulta o estado persistido para impedir bypass por instância stale ou bulk delete."""
    if not instance.pk:
        return
    status = sender.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    if status is not None and status != MedicationRequest.Status.DRAFT:
        raise ValidationError(_REQUEST_DELETE_ERROR)


@receiver(pre_save, sender=StockItem)
def preserve_stock_item_identity(sender, instance, **kwargs):
    if instance._state.adding or not instance.pk:
        return
    persisted = sender.objects.filter(pk=instance.pk).values(
        "drug_id",
        "storage_location",
    ).first()
    if not persisted or not instance.lots.exists():
        return
    if (
        persisted["drug_id"] != instance.drug_id
        or persisted["storage_location"] != instance.storage_location
    ):
        raise ValidationError(_STOCK_IDENTITY_ERROR)


@receiver(pre_save, sender=Lot)
def preserve_lot_ledger_boundary(sender, instance, **kwargs):
    if instance._state.adding or not instance.pk:
        return
    persisted = sender.objects.filter(pk=instance.pk).values(
        "stock_item_id",
        "lot_number",
        "expires_on",
        "quantity_available",
    ).first()
    if not persisted:
        return
    if persisted["quantity_available"] != instance.quantity_available:
        raise ValidationError(_LOT_BALANCE_ERROR)
    if instance.movements.exists() and (
        persisted["stock_item_id"] != instance.stock_item_id
        or persisted["lot_number"] != instance.lot_number
        or persisted["expires_on"] != instance.expires_on
    ):
        raise ValidationError(_LOT_IDENTITY_ERROR)


@receiver(pre_delete, sender=MedicationSafetyReview)
@receiver(pre_delete, sender=MedicationSafetyFinding)
@receiver(pre_delete, sender=MedicationDispense)
@receiver(pre_delete, sender=MedicationDispenseItem)
@receiver(pre_delete, sender=StockMovement)
def prevent_append_only_record_delete(sender, instance, **kwargs):
    raise ValidationError(_APPEND_ONLY_DELETE_ERROR)
