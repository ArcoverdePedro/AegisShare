from auditlog.context import set_actor
from auditlog.signals import accessed
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_GET, require_http_methods

from apps.clinical.pep.models import Encounter
from apps.clinical.pep.permissions import accessible_patients

from .forms import OrderFilterForm, OrderForm, SpecimenForm
from .models import ServiceRequest, Specimen
from .services import LisConflict, collect_specimen, order_test, require_permission


def _orders(user):
    return ServiceRequest.objects.filter(
        encounter__patient__in=accessible_patients(user)
    ).select_related("encounter__patient", "requested_by", "specimen__collected_by")


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
        queryset = queryset.filter(specimen__isnull=form.cleaned_data["status"] == "requested")
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
        if item.collected:
            accessed.send(Specimen, instance=item.specimen)
    return render(request, "clinical/lis/order_detail.html", {"item": item})


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
