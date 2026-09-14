from django.core.exceptions import ValidationError
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver

from .models import MedicationRequest, MedicationRequestItem


_ITEM_MUTATION_ERROR = "Itens só podem ser alterados enquanto a prescrição está em rascunho."
_ITEM_DELETE_ERROR = "Itens submetidos não podem ser excluídos."


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
