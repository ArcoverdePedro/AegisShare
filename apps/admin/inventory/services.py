from auditlog.context import set_actor
from auditlog.signals import accessed
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.views.decorators.debug import sensitive_variables

from apps.clinical.pep.permissions import require_module_permission

from .forms import RequisitionForm
from .models import InventoryItem, MaterialBalance, MaterialMovement, Requisition


class InventoryConflict(ValueError):
    pass


def require_permission(user, capability=None):
    require_module_permission(user, "inventory", "view_requisitions", capability)


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
        except IntegrityError:
            # Outra requisicao gravou a mesma chave ao mesmo tempo: devolve o registro dela.
            existing = Requisition.objects.filter(operation_key=data["operation_key"]).first()
            if existing is None:
                raise
            return _retry(existing, user, current.pk, data["quantity"])


def delivered_quantity(requisition):
    """Saidas menos devolucoes/estornos vinculados; a requisicao em si nao e entrega."""
    total = requisition.movements.aggregate(total=Sum("quantity_delta"))["total"] or 0
    return -total


def _balance(item, location, lot, *, create=False, expires_on=None):
    queryset = MaterialBalance.objects.select_for_update()
    if not create:
        balance = queryset.filter(item=item, location=location, lot=lot).first()
        if balance is None:
            raise InventoryConflict("Saldo insuficiente no local/lote informado.")
        return balance
    balance, _ = queryset.get_or_create(
        item=item, location=location, lot=lot, defaults={"expires_on": expires_on}
    )
    if expires_on and balance.expires_on != expires_on:
        if balance.expires_on:
            raise InventoryConflict("A validade diverge da registrada para este lote.")
        balance.expires_on = expires_on
        balance.save(update_fields=["expires_on"])
    return balance


def _apply(balance, delta, kind, *, user, operation_key, **extra):
    if balance.quantity + delta < 0:
        raise InventoryConflict("Saldo insuficiente no local/lote informado.")
    balance.quantity += delta
    balance.save(update_fields=["quantity"])
    return MaterialMovement.objects.create(
        balance=balance,
        kind=kind,
        quantity_delta=delta,
        actor=user,
        operation_key=operation_key,
        **extra,
    )


def _existing_operation(operation_key, user, item):
    first = (
        MaterialMovement.objects.filter(operation_key=operation_key)
        .select_related("balance")
        .order_by("created_at", "id")
        .first()
    )
    if first and (first.actor_id, first.balance.item_id) != (user.pk, item.pk):
        raise InventoryConflict("Operação incompatível.")
    return first


def record_movement(
    *,
    user,
    kind,
    item,
    location,
    quantity,
    operation_key,
    to_location=None,
    lot="",
    expires_on=None,
    requisition=None,
    reason="",
    confirmed=True,
):
    require_permission(user, "adjust_stock" if kind == "ADJUSTMENT" else "move_stock")
    if not confirmed:
        raise InventoryConflict("Confirme a movimentação.")
    try:
        with transaction.atomic(), set_actor(user):
            # Trava o material: serializa movimentos do mesmo item e evita deadlock entre locais.
            item = get_object_or_404(InventoryItem.objects.select_for_update(), pk=item.pk)
            existing = _existing_operation(operation_key, user, item)
            if existing:
                return existing
            if not item.active:
                raise InventoryConflict("Selecione um material disponível.")
            common = {"user": user, "operation_key": operation_key, "reason": reason.strip()}

            if kind == "RECEIPT":
                balance = _balance(item, location, lot, create=True, expires_on=expires_on)
                return _apply(balance, quantity, kind, **common)
            if kind == "ADJUSTMENT":
                balance = _balance(item, location, lot, create=True)
                delta = quantity - balance.quantity
                if not delta:
                    raise InventoryConflict("O saldo já confere com a quantidade contada.")
                return _apply(balance, delta, kind, **common)
            if kind == "TRANSFER":
                source = _balance(item, location, lot)
                movement = _apply(source, -quantity, "TRANSFER_OUT", **common)
                target = _balance(item, to_location, lot, create=True, expires_on=source.expires_on)
                _apply(target, quantity, "TRANSFER_IN", **common)
                return movement
            if requisition:
                requisition = Requisition.objects.select_for_update().get(pk=requisition.pk)
                delivered = delivered_quantity(requisition)
                limit = requisition.quantity - delivered if kind == "ISSUE" else delivered
                if quantity > limit:
                    raise InventoryConflict("Quantidade excede o pendente da requisição.")
            if kind == "ISSUE":
                balance = _balance(item, location, lot)
                return _apply(balance, -quantity, kind, requisition=requisition, **common)
            if kind == "RETURN":
                balance = _balance(item, location, lot, create=True)
                return _apply(balance, quantity, kind, requisition=requisition, **common)
            raise InventoryConflict("Tipo de movimento inválido.")
    except IntegrityError:
        # Outra requisicao gravou a mesma chave ao mesmo tempo: devolve o registro dela.
        existing = _existing_operation(operation_key, user, item)
        if existing is None:
            raise
        return existing


def reverse_movement(*, user, movement, reason, operation_key):
    """Estorna a operacao inteira (ambas as pernas de uma transferencia)."""
    require_permission(user, "adjust_stock")
    try:
        with transaction.atomic(), set_actor(user):
            item = get_object_or_404(
                InventoryItem.objects.select_for_update(), pk=movement.balance.item_id
            )
            existing = _existing_operation(operation_key, user, item)
            if existing:
                return existing
            legs = list(
                MaterialMovement.objects.filter(operation_key=movement.operation_key)
                .exclude(kind=MaterialMovement.Kind.REVERSAL)
                .select_related("balance")
                # Credita antes de debitar: estorno de transferencia nao depende da ordem.
                .order_by("quantity_delta")
            )
            if not legs or any(hasattr(leg, "reversed_by") for leg in legs):
                raise InventoryConflict("Movimento já estornado ou não estornável.")
            reversals = [
                _apply(
                    MaterialBalance.objects.select_for_update().get(pk=leg.balance_id),
                    -leg.quantity_delta,
                    MaterialMovement.Kind.REVERSAL,
                    user=user,
                    operation_key=operation_key,
                    reason=reason.strip(),
                    reverses=leg,
                    requisition=leg.requisition,
                )
                for leg in legs
            ]
            return reversals[0]
    except IntegrityError:
        existing = _existing_operation(operation_key, user, item)
        if existing is None:
            raise
        return existing
