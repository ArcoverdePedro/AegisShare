from auditlog.context import set_actor
from auditlog.signals import accessed
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_GET, require_http_methods

from .forms import RequisitionForm, material_label
from .models import InventoryItem, Requisition
from .services import InventoryConflict, request_material, require_permission


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
        _audit_read(request.user, [item])
    except DatabaseError:
        return _failed()
    return render(request, "admin/inventory/requisition_detail.html", {"item": item})


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
