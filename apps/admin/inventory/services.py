from auditlog.context import set_actor
from auditlog.signals import accessed
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.views.decorators.debug import sensitive_variables

from apps.clinical.pep.permissions import is_internal_professional

from .forms import RequisitionForm
from .models import InventoryItem, Requisition


class InventoryConflict(ValueError):
    pass


def require_permission(user, capability=None):
    permissions = ["inventory.view_requisitions"]
    if capability:
        permissions.append(f"inventory.{capability}")
    if not is_internal_professional(user) or not user.has_perms(permissions):
        raise PermissionDenied


def _retry(existing, user, item_id, quantity):
    if (existing.requested_by_id, existing.item_id, existing.quantity) != (
        user.pk,
        item_id,
        quantity,
    ):
        raise InventoryConflict("Operação incompatível.")
    accessed.send(Requisition, instance=existing)
    return existing


@sensitive_variables()
def request_material(*, user, item, quantity, operation_key, confirmed):
    require_permission(user, "request_material")
    form = RequisitionForm(
        {
            "item": item.pk,
            "quantity": quantity,
            "operation_key": operation_key,
            "confirmed": confirmed,
        }
    )
    if not form.is_valid():
        raise InventoryConflict("Revise os dados e a confirmação.")
    data = form.cleaned_data
    with transaction.atomic(), set_actor(user):
        current = get_object_or_404(InventoryItem.objects.select_for_update(), pk=item.pk)
        require_permission(user, "request_material")
        existing = Requisition.objects.filter(operation_key=data["operation_key"]).first()
        if existing:
            return _retry(existing, user, current.pk, data["quantity"])
        if not current.active:
            raise InventoryConflict("Selecione um material disponível.")
        try:
            with transaction.atomic():
                return Requisition.objects.create(
                    item=current,
                    item_code=current.code,
                    item_name=current.name,
                    item_unit=current.unit,
                    quantity=data["quantity"],
                    requested_by=user,
                    operation_key=data["operation_key"],
                )
        except IntegrityError as exc:
            name = getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None)
            if name != "uniq_inventory_req_operation" and str(exc) != (
                "UNIQUE constraint failed: inventory_requisition.operation_key"
            ):
                raise
            existing = Requisition.objects.filter(operation_key=data["operation_key"]).first()
            if existing is None:
                raise
            return _retry(existing, user, current.pk, data["quantity"])
