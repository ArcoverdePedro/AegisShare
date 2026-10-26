from auditlog.context import set_actor
from auditlog.signals import accessed
from django.db import IntegrityError, transaction
from django.db.models import F, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from apps.clinical.pep.permissions import require_module_permission

from .forms import RequisitionForm
from .models import (
    InventoryItem,
    MaterialBalance,
    MaterialMovement,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseReceipt,
    Requisition,
)


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


def require_purchase_permission(user, capability=None):
    require_module_permission(user, "inventory", "view_purchases", capability)


def create_purchase_order(*, user, supplier, notes, operation_key, lines):
    require_purchase_permission(user, "request_purchase")
    try:
        with transaction.atomic(), set_actor(user):
            existing = PurchaseOrder.objects.filter(operation_key=operation_key).first()
            if existing:
                if existing.created_by_id != user.pk or existing.supplier_id != supplier.pk:
                    raise InventoryConflict("Operação incompatível.")
                return existing
            if not supplier.active:
                raise InventoryConflict("Selecione um fornecedor ativo.")
            order = PurchaseOrder.objects.create(
                supplier=supplier, notes=notes.strip(), created_by=user, operation_key=operation_key
            )
            for line in lines:
                PurchaseOrderLine.objects.create(order=order, **line)
            return order
    except IntegrityError:
        existing = PurchaseOrder.objects.filter(operation_key=operation_key).first()
        if existing is None or existing.created_by_id != user.pk:
            raise
        return existing


def _locked_order(order):
    return PurchaseOrder.objects.select_for_update().get(pk=order.pk)


def approve_purchase_order(*, user, order):
    require_purchase_permission(user, "approve_purchase")
    with transaction.atomic(), set_actor(user):
        order = _locked_order(order)
        if order.status != PurchaseOrder.Status.DRAFT:
            raise InventoryConflict("Somente pedidos aguardando aprovação podem ser aprovados.")
        if order.created_by_id == user.pk:
            raise InventoryConflict("Quem solicitou o pedido não pode aprová-lo.")
        order.status = PurchaseOrder.Status.APPROVED
        order.approved_by = user
        order.approved_at = timezone.now()
        order.save(update_fields=["status", "approved_by", "approved_at"])
        return order


def cancel_purchase_order(*, user, order, reason):
    require_purchase_permission(user, "approve_purchase")
    with transaction.atomic(), set_actor(user):
        order = _locked_order(order)
        if order.status not in {PurchaseOrder.Status.DRAFT, PurchaseOrder.Status.APPROVED}:
            raise InventoryConflict(
                "Pedido com recebimento ou já encerrado não pode ser cancelado."
            )
        order.status = PurchaseOrder.Status.CANCELLED
        order.cancelled_by = user
        order.cancel_reason = reason.strip()
        order.save(update_fields=["status", "cancelled_by", "cancel_reason"])
        return order


def receive_purchase(
    *,
    user,
    line,
    location,
    quantity,
    unit_price,
    invoice_number,
    operation_key,
    lot="",
    expires_on=None,
    confirmed=True,
):
    """Recebimento confirmado gera uma unica entrada de estoque, na mesma transacao."""
    require_purchase_permission(user, "receive_purchase")
    if not confirmed:
        raise InventoryConflict("Confirme o recebimento.")
    with transaction.atomic(), set_actor(user):
        order = _locked_order(line.order)
        existing = (
            PurchaseReceipt.objects.filter(movement__operation_key=operation_key)
            .select_related("movement")
            .first()
        )
        if existing:
            if (existing.line_id, existing.received_by_id) != (line.pk, user.pk):
                raise InventoryConflict("Operação incompatível.")
            return existing
        line = PurchaseOrderLine.objects.select_for_update().get(pk=line.pk)
        if order.status not in {PurchaseOrder.Status.APPROVED, PurchaseOrder.Status.PARTIAL}:
            raise InventoryConflict("O pedido não está aprovado para recebimento.")
        if quantity > line.pending:
            raise InventoryConflict(
                "Quantidade acima do pendente: registre a divergência e submeta novo pedido."
            )
        if unit_price != line.unit_price:
            raise InventoryConflict(
                "Preço diverge do aprovado: registre a divergência e submeta nova aprovação."
            )
        item = InventoryItem.objects.select_for_update().get(pk=line.item_id)
        balance = _balance(item, location, lot, create=True, expires_on=expires_on)
        movement = _apply(
            balance,
            quantity,
            MaterialMovement.Kind.RECEIPT,
            user=user,
            operation_key=operation_key,
            reason=f"Compra {order.pk} · NF {invoice_number.strip()}",
        )
        line.received_quantity += quantity
        line.save(update_fields=["received_quantity"])
        complete = not order.lines.filter(received_quantity__lt=F("quantity")).exists()
        order.status = PurchaseOrder.Status.RECEIVED if complete else PurchaseOrder.Status.PARTIAL
        order.save(update_fields=["status"])
        return PurchaseReceipt.objects.create(
            line=line, movement=movement, invoice_number=invoice_number.strip(), received_by=user
        )
