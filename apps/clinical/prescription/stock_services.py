import uuid
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .events import emit_stock_low_event
from .models import Drug, Lot, StockItem, StockMovement
from .permissions import can_manage_stock


class StockStateError(RuntimeError):
    """Conflito operacional de estoque sem detalhes internos de persistência."""


def _require_stock_management(actor):
    if not can_manage_stock(actor):
        raise PermissionDenied


def _decimal(value, *, field_name):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise StockStateError(f"{field_name} inválido.") from exc


def _eligible_total(stock_item_id, *, on_date=None):
    on_date = on_date or timezone.localdate()
    total = (
        Lot.objects.filter(
            stock_item_id=stock_item_id,
            active=True,
            expires_on__gte=on_date,
        ).aggregate(total=Sum("quantity_available"))["total"]
        or Decimal("0")
    )
    return total


def _emit_low_stock_if_needed(stock_item, *, before_total, after_total):
    if not stock_item.active:
        return
    if after_total <= stock_item.minimum_level and after_total != before_total:
        emit_stock_low_event(
            stock_item_id=stock_item.pk,
            drug_id=stock_item.drug_id,
            storage_location=stock_item.storage_location,
            quantity_available=after_total,
            minimum_level=stock_item.minimum_level,
        )


@transaction.atomic
def create_stock_item(
    *,
    actor,
    drug_id,
    storage_location,
    minimum_level=Decimal("0"),
    active=True,
):
    _require_stock_management(actor)
    drug = Drug.objects.get(pk=drug_id)
    if not drug.active:
        raise StockStateError("Medicamento inativo não pode receber novo estoque operacional.")
    return StockItem.objects.create(
        drug=drug,
        storage_location=storage_location,
        minimum_level=_decimal(minimum_level, field_name="Nível mínimo"),
        active=active,
    )


def _apply_stock_movement(
    *,
    lot_id,
    actor,
    movement_type,
    quantity_delta,
    operation_key,
    reason="",
):
    _require_stock_management(actor)
    delta = _decimal(quantity_delta, field_name="Quantidade")
    if delta == 0:
        raise StockStateError("A movimentação deve possuir quantidade diferente de zero.")

    lot = (
        Lot.objects.select_for_update()
        .select_related("stock_item", "stock_item__drug")
        .get(pk=lot_id)
    )
    stock_item = lot.stock_item
    operation_key = operation_key or uuid.uuid4()

    existing = StockMovement.objects.filter(
        lot=lot,
        operation_key=operation_key,
        movement_type=movement_type,
    ).first()
    if existing:
        if existing.quantity_delta == delta and existing.reason == " ".join((reason or "").split()):
            return existing
        raise StockStateError("A chave de operação já foi utilizada com dados diferentes.")

    today = timezone.localdate()
    if movement_type == StockMovement.Type.RECEIPT:
        if delta <= 0:
            raise StockStateError("Entrada de estoque exige quantidade positiva.")
        if not stock_item.active or not lot.active:
            raise StockStateError("Estoque ou lote inativo não pode receber nova entrada.")
        if lot.expires_on < today:
            raise StockStateError("Lote expirado não pode receber nova entrada.")
    elif movement_type == StockMovement.Type.ADJUSTMENT:
        if not (reason or "").strip():
            raise StockStateError("Ajuste manual exige justificativa.")
    else:
        raise StockStateError("Tipo de movimentação não permitido neste serviço.")

    before_total = _eligible_total(stock_item.pk, on_date=today)
    new_balance = lot.quantity_available + delta
    if new_balance < 0:
        raise StockStateError("A movimentação resultaria em saldo negativo.")

    Lot.objects.filter(pk=lot.pk).update(
        quantity_available=new_balance,
        updated_at=timezone.now(),
    )
    movement = StockMovement.objects.create(
        lot=lot,
        movement_type=movement_type,
        quantity_delta=delta,
        actor=actor,
        operation_key=operation_key,
        reason=reason,
    )
    lot.refresh_from_db(fields=["quantity_available", "updated_at"])
    after_total = _eligible_total(stock_item.pk, on_date=today)
    _emit_low_stock_if_needed(
        stock_item,
        before_total=before_total,
        after_total=after_total,
    )
    return movement


@transaction.atomic
def create_lot(
    *,
    actor,
    stock_item_id,
    lot_number,
    expires_on,
    initial_quantity=Decimal("0"),
    active=True,
    operation_key=None,
):
    _require_stock_management(actor)
    stock_item = (
        StockItem.objects.select_for_update()
        .select_related("drug")
        .get(pk=stock_item_id)
    )
    if not stock_item.active:
        raise StockStateError("Estoque inativo não pode receber novo lote.")

    initial_quantity = _decimal(initial_quantity, field_name="Quantidade inicial")
    if initial_quantity < 0:
        raise StockStateError("A quantidade inicial não pode ser negativa.")
    if initial_quantity > 0 and expires_on < timezone.localdate():
        raise StockStateError("Lote expirado não pode ser criado com saldo disponível.")

    lot = Lot.objects.create(
        stock_item=stock_item,
        lot_number=lot_number,
        expires_on=expires_on,
        quantity_available=Decimal("0"),
        active=active,
    )
    if initial_quantity > 0:
        _apply_stock_movement(
            lot_id=lot.pk,
            actor=actor,
            movement_type=StockMovement.Type.RECEIPT,
            quantity_delta=initial_quantity,
            operation_key=operation_key or uuid.uuid4(),
            reason="Entrada inicial do lote",
        )
        lot.refresh_from_db()
    return lot


@transaction.atomic
def receive_stock(*, lot_id, actor, quantity, operation_key=None):
    return _apply_stock_movement(
        lot_id=lot_id,
        actor=actor,
        movement_type=StockMovement.Type.RECEIPT,
        quantity_delta=quantity,
        operation_key=operation_key or uuid.uuid4(),
    )


@transaction.atomic
def adjust_stock(*, lot_id, actor, quantity_delta, reason, operation_key=None):
    return _apply_stock_movement(
        lot_id=lot_id,
        actor=actor,
        movement_type=StockMovement.Type.ADJUSTMENT,
        quantity_delta=quantity_delta,
        operation_key=operation_key or uuid.uuid4(),
        reason=reason,
    )
