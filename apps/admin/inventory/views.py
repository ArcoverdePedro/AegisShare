from auditlog.context import set_actor
from auditlog.signals import accessed
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_GET, require_http_methods

from .forms import (
    MovementForm,
    PurchaseLineFormSet,
    PurchaseOrderForm,
    PurchaseReceiptForm,
    RequisitionForm,
    ReversalForm,
    material_label,
)
from .models import (
    InventoryItem,
    MaterialBalance,
    MaterialMovement,
    PurchaseOrder,
    PurchaseOrderLine,
    Requisition,
)
from .services import (
    InventoryConflict,
    approve_purchase_order,
    cancel_purchase_order,
    create_purchase_order,
    delivered_quantity,
    receive_purchase,
    record_movement,
    request_material,
    require_permission,
    require_purchase_permission,
    reverse_movement,
)


def _failed():
    return HttpResponse(
        "Não foi possível concluir a operação. Consulte o histórico e tente novamente.",
        status=503,
        content_type="text/plain; charset=utf-8",
    )


def _audit_read(user, items):
    with transaction.atomic(), set_actor(user):
        for item in items:
            accessed.send(type(item), instance=item)


def _page(request, queryset):
    page = Paginator(queryset, 25).get_page(request.GET.get("page"))
    page.object_list = list(page.object_list)
    _audit_read(request.user, page.object_list)
    return page


@login_required
@require_GET
def item_list(request):
    require_permission(request.user)
    try:
        page = _page(request, InventoryItem.objects.filter(active=True))
    except DatabaseError:
        return _failed()
    return render(request, "admin/inventory/item_list.html", {"page_obj": page})


@login_required
@require_GET
def requisition_list(request):
    require_permission(request.user)
    try:
        page = _page(request, Requisition.objects.select_related("requested_by"))
    except DatabaseError:
        return _failed()
    return render(request, "admin/inventory/requisition_list.html", {"page_obj": page})


@login_required
@require_GET
def requisition_detail(request, pk):
    require_permission(request.user)
    try:
        item = get_object_or_404(Requisition.objects.select_related("requested_by"), pk=pk)
        movements = list(item.movements.select_related("balance__location", "actor"))
        _audit_read(request.user, [item, *movements])
        delivered = delivered_quantity(item)
    except DatabaseError:
        return _failed()
    return render(
        request,
        "admin/inventory/requisition_detail.html",
        {"item": item, "movements": movements, "delivered": delivered},
    )


@sensitive_post_parameters()
@sensitive_variables()
@login_required
@require_http_methods(["GET", "POST"])
def requisition_create(request):
    require_permission(request.user, "request_material")
    try:
        form = RequisitionForm(request.POST if request.method == "POST" else None)
        status = 200
        if request.method == "POST" and form.is_valid():
            try:
                item = request_material(user=request.user, **form.cleaned_data)
            except InventoryConflict:
                form.add_error(
                    None, "Operação incompatível. Consulte o histórico e revise os dados."
                )
                status = 409
            else:
                return redirect("inventory:requisition_detail", pk=item.pk)
        # ponytail: select nativo carrega catálogo ativo; busca paginada se o volume exigir.
        choices = list(InventoryItem.objects.filter(active=True))
        _audit_read(request.user, choices)
        # Renderiza exatamente as escolhas auditadas, sem uma segunda consulta ao catálogo.
        form.fields["item"].choices = [("", form.fields["item"].empty_label)] + [
            (item.pk, material_label(item)) for item in choices
        ]
    except DatabaseError:
        return _failed()
    return render(request, "admin/inventory/requisition_form.html", {"form": form}, status=status)


def _can_move(user):
    return user.has_perm("inventory.move_stock") or user.has_perm("inventory.adjust_stock")


@login_required
@require_GET
def balance_list(request):
    require_permission(request.user)
    try:
        page = _page(
            request,
            MaterialBalance.objects.filter(quantity__gt=0).select_related("item", "location"),
        )
    except DatabaseError:
        return _failed()
    return render(
        request,
        "admin/inventory/balance_list.html",
        {"page_obj": page, "can_move": _can_move(request.user)},
    )


@login_required
@require_GET
def movement_list(request):
    require_permission(request.user)
    try:
        page = _page(
            request,
            MaterialMovement.objects.select_related(
                "balance__item", "balance__location", "actor", "requisition"
            ),
        )
    except DatabaseError:
        return _failed()
    return render(request, "admin/inventory/movement_list.html", {"page_obj": page})


@sensitive_post_parameters()
@login_required
@require_http_methods(["GET", "POST"])
def movement_create(request):
    require_permission(request.user)
    if not _can_move(request.user):
        raise PermissionDenied
    form = MovementForm(request.POST or None, initial=request.GET.dict())
    status = 200
    try:
        if request.method == "POST" and form.is_valid():
            try:
                movement = record_movement(user=request.user, **form.cleaned_data)
            except InventoryConflict as exc:
                form.add_error(None, str(exc))
                status = 409
            else:
                return redirect("inventory:movement_detail", pk=movement.pk)
    except DatabaseError:
        return _failed()
    return render(request, "admin/inventory/movement_form.html", {"form": form}, status=status)


@sensitive_post_parameters()
@login_required
@require_http_methods(["GET", "POST"])
def movement_detail(request, pk):
    require_permission(request.user)
    form = ReversalForm(request.POST or None)
    status = 200
    try:
        movement = get_object_or_404(
            MaterialMovement.objects.select_related(
                "balance__item", "balance__location", "actor", "requisition", "reverses"
            ),
            pk=pk,
        )
        if request.method == "POST" and form.is_valid():
            try:
                reversal = reverse_movement(
                    user=request.user, movement=movement, **form.cleaned_data
                )
            except InventoryConflict as exc:
                form.add_error(None, str(exc))
                status = 409
            else:
                return redirect("inventory:movement_detail", pk=reversal.pk)
        legs = list(
            MaterialMovement.objects.filter(operation_key=movement.operation_key).select_related(
                "balance__location"
            )
        )
        reversed_by = MaterialMovement.objects.filter(reverses__in=legs).first()
        _audit_read(request.user, legs)
    except DatabaseError:
        return _failed()
    return render(
        request,
        "admin/inventory/movement_detail.html",
        {"movement": movement, "legs": legs, "reversed_by": reversed_by, "form": form},
        status=status,
    )


@login_required
@require_GET
def purchase_list(request):
    require_purchase_permission(request.user)
    try:
        page = _page(request, PurchaseOrder.objects.select_related("supplier", "created_by"))
    except DatabaseError:
        return _failed()
    return render(request, "admin/inventory/purchase_list.html", {"page_obj": page})


@login_required
@require_http_methods(["GET", "POST"])
def purchase_create(request):
    require_purchase_permission(request.user, "request_purchase")
    data = request.POST if request.method == "POST" else None
    form = PurchaseOrderForm(data)
    lines = PurchaseLineFormSet(data, prefix="lines")
    status = 200
    try:
        if request.method == "POST" and form.is_valid() and lines.is_valid():
            try:
                order = create_purchase_order(
                    user=request.user,
                    lines=[line.cleaned_data for line in lines if line.cleaned_data],
                    **form.cleaned_data,
                )
            except InventoryConflict as exc:
                form.add_error(None, str(exc))
                status = 409
            else:
                return redirect("inventory:purchase_detail", pk=order.pk)
    except DatabaseError:
        return _failed()
    return render(
        request,
        "admin/inventory/purchase_form.html",
        {"form": form, "lines": lines},
        status=status,
    )


@login_required
@require_http_methods(["GET", "POST"])
def purchase_detail(request, pk):
    require_purchase_permission(request.user)
    cancel_form = ReversalForm(request.POST or None)
    try:
        order = get_object_or_404(
            PurchaseOrder.objects.select_related("supplier", "created_by", "approved_by"), pk=pk
        )
        if request.method == "POST":
            try:
                if request.POST.get("action") == "approve":
                    approve_purchase_order(user=request.user, order=order)
                    messages.success(request, "Pedido aprovado.")
                    return redirect("inventory:purchase_detail", pk=order.pk)
                if cancel_form.is_valid():
                    cancel_purchase_order(
                        user=request.user, order=order, reason=cancel_form.cleaned_data["reason"]
                    )
                    messages.success(request, "Pedido cancelado.")
                    return redirect("inventory:purchase_detail", pk=order.pk)
            except InventoryConflict as exc:
                messages.error(request, str(exc))
                return redirect("inventory:purchase_detail", pk=order.pk)
        lines = list(order.lines.select_related("item").prefetch_related("receipts__received_by"))
        _audit_read(request.user, [order, *lines])
    except DatabaseError:
        return _failed()
    return render(
        request,
        "admin/inventory/purchase_detail.html",
        {"order": order, "lines": lines, "cancel_form": cancel_form},
    )


@sensitive_post_parameters()
@login_required
@require_http_methods(["GET", "POST"])
def purchase_receive(request, pk):
    require_purchase_permission(request.user, "receive_purchase")
    form = PurchaseReceiptForm(request.POST or None)
    status = 200
    try:
        line = get_object_or_404(
            PurchaseOrderLine.objects.select_related("order__supplier", "item"), pk=pk
        )
        if request.method == "POST" and form.is_valid():
            try:
                receive_purchase(user=request.user, line=line, **form.cleaned_data)
            except InventoryConflict as exc:
                form.add_error(None, str(exc))
                status = 409
            else:
                return redirect("inventory:purchase_detail", pk=line.order_id)
        _audit_read(request.user, [line])
    except DatabaseError:
        return _failed()
    return render(
        request,
        "admin/inventory/purchase_receive.html",
        {"form": form, "line": line},
        status=status,
    )
