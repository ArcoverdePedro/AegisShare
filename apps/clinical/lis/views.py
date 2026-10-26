from auditlog.context import set_actor
from auditlog.signals import accessed
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.db.models import Exists, OuterRef, Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.clinical.pep.models import Encounter
from apps.clinical.pep.permissions import accessible_patients

from .forms import OrderFilterForm, OrderForm, ReasonForm, ReceiveForm, ResultForm, SpecimenForm
from .models import LabResult, ServiceRequest, Specimen, SpecimenEvent
from .services import (
    LisConflict,
    advance_result,
    cancel_order,
    collect_specimen,
    enter_result,
    order_test,
    receive_specimen,
    reject_specimen,
    require_permission,
)


def _orders(user):
    return (
        ServiceRequest.objects.filter(encounter__patient__in=accessible_patients(user))
        .select_related("encounter__patient", "requested_by", "cancellation")
        .prefetch_related(
            Prefetch(
                "specimens",
                queryset=Specimen.objects.select_related("collected_by").prefetch_related(
                    "events__actor"
                ),
            )
        )
    )


def _failed():
    return HttpResponse(
        "Não foi possível concluir a operação. Consulte o histórico e tente novamente.",
        status=503,
        content_type="text/plain; charset=utf-8",
    )


@login_required
@require_GET
def order_list(request):
    require_permission(request.user)
    form = OrderFilterForm(request.GET)
    queryset = _orders(request.user)
    if not form.is_valid():
        queryset = queryset.none()
    elif form.cleaned_data["status"]:
        active = Specimen.objects.filter(service_request=OuterRef("pk")).exclude(
            events__kind=SpecimenEvent.Kind.REJECTED
        )
        queryset = queryset.filter(
            Exists(active) if form.cleaned_data["status"] == "collected" else ~Exists(active)
        )
    page = Paginator(queryset, 25).get_page(request.GET.get("page"))
    page.object_list = list(page.object_list)
    with transaction.atomic(), set_actor(request.user):
        for item in page.object_list:
            accessed.send(ServiceRequest, instance=item)
    return render(request, "clinical/lis/order_list.html", {"page_obj": page, "form": form})


@login_required
@require_GET
def order_detail(request, pk):
    require_permission(request.user)
    item = get_object_or_404(_orders(request.user), pk=pk)
    with transaction.atomic(), set_actor(request.user):
        accessed.send(ServiceRequest, instance=item)
        for specimen in item.specimens.all():
            accessed.send(Specimen, instance=specimen)
    return render(
        request, "clinical/lis/order_detail.html", {"item": item, "reason_form": ReasonForm()}
    )


@sensitive_post_parameters()
@sensitive_variables()
@login_required
@require_http_methods(["GET", "POST"])
def order_create(request, encounter_id):
    require_permission(request.user, "order_test")
    encounter = get_object_or_404(
        Encounter.objects.filter(patient__in=accessible_patients(request.user)).select_related(
            "patient"
        ),
        pk=encounter_id,
    )
    form = OrderForm(request.POST if request.method == "POST" else None)
    status = 200
    if request.method == "POST" and form.is_valid():
        try:
            item = order_test(user=request.user, encounter_id=encounter.pk, **form.cleaned_data)
        except LisConflict as exc:
            form.add_error(None, str(exc))
            status = 409
        except DatabaseError:
            return _failed()
        else:
            messages.success(request, "Pedido registrado.")
            return redirect("lis:order_detail", pk=item.pk)
    form.fields["lab_test"].queryset = form.fields["lab_test"].queryset.filter(active=True)
    with set_actor(request.user):
        accessed.send(Encounter, instance=encounter)
    return render(
        request,
        "clinical/lis/order_form.html",
        {"form": form, "encounter": encounter},
        status=status,
    )


@sensitive_post_parameters()
@sensitive_variables()
@login_required
@require_http_methods(["GET", "POST"])
def specimen_create(request, pk):
    require_permission(request.user, "collect_specimen")
    item = get_object_or_404(_orders(request.user), pk=pk)
    if request.method == "GET" and item.collected:
        return redirect("lis:order_detail", pk=pk)
    form = SpecimenForm(request.POST if request.method == "POST" else None, order=item)
    status = 200
    if request.method == "POST" and form.is_valid():
        try:
            collect_specimen(user=request.user, order=item, **form.cleaned_data)
        except LisConflict as exc:
            form.add_error(None, str(exc))
            status = 409
        except DatabaseError:
            return _failed()
        else:
            messages.success(request, "Coleta registrada.")
            return redirect("lis:order_detail", pk=pk)
    with set_actor(request.user):
        accessed.send(ServiceRequest, instance=item)
    return render(
        request, "clinical/lis/specimen_form.html", {"form": form, "item": item}, status=status
    )


@login_required
@require_http_methods(["GET", "POST"])
def specimen_receive(request):
    require_permission(request.user, "receive_specimen")
    form = ReceiveForm(request.POST or None)
    status = 200
    if request.method == "POST" and form.is_valid():
        try:
            event = receive_specimen(user=request.user, **form.cleaned_data)
        except LisConflict as exc:
            form.add_error(None, str(exc))
            status = 409
        else:
            messages.success(request, f"Amostra {event.specimen.accession_code} recebida.")
            return redirect("lis:specimen_receive")
    return render(request, "clinical/lis/specimen_receive.html", {"form": form}, status=status)


@login_required
@require_POST
def specimen_reject(request, pk, specimen_id):
    item = get_object_or_404(_orders(request.user), pk=pk)
    form = ReasonForm(request.POST)
    try:
        if not form.is_valid():
            raise LisConflict("Informe o motivo da rejeição.")
        reject_specimen(user=request.user, specimen_id=specimen_id, **form.cleaned_data)
        messages.success(request, "Amostra rejeitada; registre a recoleta.")
    except LisConflict as exc:
        messages.error(request, str(exc))
    return redirect("lis:order_detail", pk=item.pk)


@login_required
@require_POST
def order_cancel(request, pk):
    item = get_object_or_404(_orders(request.user), pk=pk)
    form = ReasonForm(request.POST)
    try:
        if not form.is_valid():
            raise LisConflict("Informe o motivo do cancelamento.")
        cancel_order(user=request.user, order_id=item.pk, reason=form.cleaned_data["reason"])
        messages.success(request, "Pedido cancelado.")
    except LisConflict as exc:
        messages.error(request, str(exc))
    return redirect("lis:order_detail", pk=item.pk)


@login_required
@require_GET
def specimen_label(request, pk):
    require_permission(request.user, "collect_specimen")
    item = get_object_or_404(_orders(request.user), pk=pk)
    if not item.collected:
        return redirect("lis:order_detail", pk=pk)
    with transaction.atomic(), set_actor(request.user):
        accessed.send(Specimen, instance=item.specimen)
    return render(request, "clinical/lis/specimen_label.html", {"item": item})


@login_required
@require_http_methods(["GET", "POST"])
def result_create(request, pk, specimen_id):
    require_permission(request.user, "enter_result")
    item = get_object_or_404(_orders(request.user), pk=pk)
    specimen = get_object_or_404(item.specimens.all(), pk=specimen_id)
    supersedes = None
    if request.GET.get("retificar"):
        supersedes = get_object_or_404(specimen.results, pk=request.GET["retificar"])
    form = ResultForm(
        request.POST or None,
        initial={
            f: getattr(supersedes, f)
            for f in ("analyte", "value", "unit", "reference_range", "method")
        }
        if supersedes
        else None,
    )
    if not supersedes:
        del form.fields["reason"]
    status = 200
    if request.method == "POST" and form.is_valid():
        try:
            enter_result(
                user=request.user,
                specimen_id=specimen.pk,
                supersedes=supersedes,
                **form.cleaned_data,
            )
        except LisConflict as exc:
            form.add_error(None, str(exc))
            status = 409
        else:
            messages.success(request, "Resultado registrado; aguarda validação.")
            return redirect("lis:order_detail", pk=item.pk)
    return render(
        request,
        "clinical/lis/result_form.html",
        {"form": form, "item": item, "specimen": specimen, "supersedes": supersedes},
        status=status,
    )


@login_required
@require_POST
def result_advance(request, pk, result_id):
    item = get_object_or_404(_orders(request.user), pk=pk)
    get_object_or_404(LabResult, pk=result_id, specimen__service_request=item)
    try:
        advance_result(user=request.user, result_id=result_id)
    except LisConflict as exc:
        messages.error(request, str(exc))
    return redirect("lis:order_detail", pk=item.pk)
