import uuid
from decimal import Decimal, InvalidOperation

from auditlog.context import set_actor
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from .events import emit_medication_dispensed_event, emit_stock_low_event
from .models import (
    Lot,
    MedicationDispense,
    MedicationDispenseItem,
    MedicationRequest,
    MedicationRequestItem,
    StockMovement,
)
from .permissions import can_dispense_prescription


class DispenseStateError(RuntimeError):
    """Conflito seguro de dispensação sem detalhes internos de persistência."""


def _decimal(value):
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise DispenseStateError("Quantidade inválida.") from exc
    if quantity <= 0:
        raise DispenseStateError("A quantidade deve ser maior que zero.")
    return quantity


def _normalize_allocations(allocations):
    normalized = []
    seen_pairs = set()
    for allocation in allocations:
        request_item_id = str(allocation["request_item_id"])
        lot_id = str(allocation["lot_id"])
        quantity = _decimal(allocation["quantity"])
        pair = (request_item_id, lot_id)
        if pair in seen_pairs:
            raise DispenseStateError("O mesmo item e lote não podem ser repetidos na operação.")
        seen_pairs.add(pair)
        normalized.append(
            {
                "request_item_id": request_item_id,
                "lot_id": lot_id,
                "quantity": quantity,
            }
        )
    if not normalized:
        raise DispenseStateError("Informe ao menos um item para dispensação.")
    return normalized


def _existing_matches(existing, normalized):
    persisted = sorted(
        (
            str(item.request_item_id),
            str(item.lot_id),
            item.quantity,
        )
        for item in existing.items.all()
    )
    incoming = sorted(
        (
            item["request_item_id"],
            item["lot_id"],
            item["quantity"],
        )
        for item in normalized
    )
    return persisted == incoming


@transaction.atomic
def dispense_medication(*, request_id, actor, operation_key, allocations):
    normalized = _normalize_allocations(allocations)
    try:
        operation_key = uuid.UUID(str(operation_key))
    except (TypeError, ValueError, AttributeError) as exc:
        raise DispenseStateError("Chave de operação inválida.") from exc

    existing = (
        MedicationDispense.objects.select_related("medication_request__encounter__patient")
        .prefetch_related("items")
        .filter(operation_key=operation_key)
        .first()
    )
    if existing:
        if (
            existing.medication_request_id != request_id
            or existing.dispensed_by_id != actor.pk
            or not _existing_matches(existing, normalized)
        ):
            raise DispenseStateError("A chave de operação já foi utilizada com dados diferentes.")
        return existing

    medication_request = (
        MedicationRequest.objects.select_for_update()
        .select_related("encounter__patient")
        .get(pk=request_id)
    )
    if not can_dispense_prescription(actor, medication_request):
        raise PermissionDenied
    if medication_request.status != MedicationRequest.Status.VALIDATED:
        raise DispenseStateError("A dispensação exige prescrição validada.")

    request_item_ids = {item["request_item_id"] for item in normalized}
    request_items = {
        str(item.pk): item
        for item in MedicationRequestItem.objects.select_related("drug").filter(
            medication_request=medication_request,
            pk__in=request_item_ids,
        )
    }
    if set(request_items) != request_item_ids:
        raise DispenseStateError("Item de prescrição inválido para esta dispensação.")

    lot_ids = sorted({item["lot_id"] for item in normalized})
    lots = {
        str(lot.pk): lot
        for lot in Lot.objects.select_for_update()
        .select_related("stock_item", "stock_item__drug")
        .filter(pk__in=lot_ids)
        .order_by("pk")
    }
    if set(lots) != set(lot_ids):
        raise DispenseStateError("Lote inválido para esta dispensação.")

    today = timezone.localdate()
    before_totals = {}
    for lot in lots.values():
        before_totals[lot.stock_item_id] = sum(
            (
                eligible.quantity_available
                for eligible in Lot.objects.filter(
                    stock_item_id=lot.stock_item_id,
                    active=True,
                    expires_on__gte=today,
                )
            ),
            Decimal("0"),
        )

    with set_actor(actor):
        dispense = MedicationDispense.objects.create(
            medication_request=medication_request,
            dispensed_by=actor,
            operation_key=operation_key,
            dispensed_at=timezone.now(),
        )

        for allocation in normalized:
            request_item = request_items[allocation["request_item_id"]]
            lot = lots[allocation["lot_id"]]
            quantity = allocation["quantity"]
            if not request_item.drug.active:
                raise DispenseStateError("Medicamento inativo não pode ser dispensado.")
            if not lot.stock_item.active or not lot.active:
                raise DispenseStateError("Estoque ou lote inativo não pode ser dispensado.")
            if lot.expires_on < today:
                raise DispenseStateError("Lote expirado não pode ser dispensado.")
            if lot.stock_item.drug_id != request_item.drug_id:
                raise DispenseStateError("O lote não corresponde ao medicamento prescrito.")
            if lot.quantity_available < quantity:
                raise DispenseStateError("Saldo insuficiente para concluir a dispensação.")

            dispense_item = MedicationDispenseItem.objects.create(
                dispense=dispense,
                request_item=request_item,
                lot=lot,
                quantity=quantity,
            )
            lot.quantity_available -= quantity
            Lot.objects.filter(pk=lot.pk).update(
                quantity_available=lot.quantity_available,
                updated_at=timezone.now(),
            )
            StockMovement.objects.create(
                lot=lot,
                movement_type=StockMovement.Type.DISPENSE,
                quantity_delta=-quantity,
                dispense_item=dispense_item,
                actor=actor,
                operation_key=operation_key,
            )

    touched_stock_items = {lot.stock_item_id: lot.stock_item for lot in lots.values()}
    for stock_item_id, stock_item in touched_stock_items.items():
        after_total = sum(
            (
                eligible.quantity_available
                for eligible in Lot.objects.filter(
                    stock_item_id=stock_item_id,
                    active=True,
                    expires_on__gte=today,
                )
            ),
            Decimal("0"),
        )
        if after_total <= stock_item.minimum_level and after_total != before_totals[stock_item_id]:
            emit_stock_low_event(
                stock_item_id=stock_item.pk,
                drug_id=stock_item.drug_id,
                storage_location=stock_item.storage_location,
                quantity_available=after_total,
                minimum_level=stock_item.minimum_level,
            )

    emit_medication_dispensed_event(
        dispense_id=dispense.pk,
        prescription_id=medication_request.pk,
        encounter_id=medication_request.encounter_id,
        item_count=len(normalized),
    )
    return dispense
