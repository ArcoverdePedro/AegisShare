from django.core.exceptions import ValidationError
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver

from .models import Lot, MedicationRequest, MedicationRequestItem, StockItem, StockMovement


_ITEM_MUTATION_ERROR = "Itens só podem ser alterados enquanto a prescrição está em rascunho."
_ITEM_DELETE_ERROR = "Itens submetidos não podem ser excluídos."
_LOT_BALANCE_ERROR = "Saldo de lote só pode ser alterado por movimentação de estoque."
_LOT_IDENTITY_ERROR = "Lote com movimentação não pode ter sua identidade histórica reescrita."
_STOCK_IDENTITY_ERROR = "Estoque com lotes não pode ter medicamento ou localização reescritos."
_MOVEMENT_DELETE_ERROR = "Movimentos de estoque são append-only e não podem ser excluídos."


def _persisted_request_status(instance):
    if not instance.medication_request_id:
        return None
    return (
        MedicationRequest.objects.filter(pk=instance.medication_request_id)
        .values_list("status", flat=True)
        .first()
    )


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


@receiver(pre_delete, sender=StockMovement)
def prevent_stock_movement_delete(sender, instance, **kwargs):
    raise ValidationError(_MOVEMENT_DELETE_ERROR)
