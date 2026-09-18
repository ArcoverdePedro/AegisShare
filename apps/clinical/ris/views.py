from auditlog.context import set_actor
from auditlog.signals import accessed
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_GET, require_http_methods

from apps.clinical.pep.models import Encounter
from apps.clinical.pep.permissions import accessible_patients

from .forms import ImagingOrderForm
from .models import ImagingOrder
from .services import RisConflict, order_exam, require_permission


def _orders(user):
    return ImagingOrder.objects.filter(
        encounter__patient__in=accessible_patients(user)
    ).select_related("encounter__patient", "requested_by")


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
    try:
        page = Paginator(_orders(request.user), 25).get_page(request.GET.get("page"))
        page.object_list = list(page.object_list)
        with transaction.atomic(), set_actor(request.user):
            for item in page.object_list:
                accessed.send(ImagingOrder, instance=item)
    except DatabaseError:
        return _failed()
    return render(request, "clinical/ris/order_list.html", {"page_obj": page})


@login_required
@require_GET
def order_detail(request, pk):
    require_permission(request.user)
    try:
        item = get_object_or_404(_orders(request.user), pk=pk)
        with transaction.atomic(), set_actor(request.user):
            accessed.send(ImagingOrder, instance=item)
    except DatabaseError:
        return _failed()
    return render(request, "clinical/ris/order_detail.html", {"item": item})


@sensitive_post_parameters()
@sensitive_variables()
@login_required
@require_http_methods(["GET", "POST"])
def order_create(request, encounter_id):
    require_permission(request.user, "order_exam")
    try:
        encounter = get_object_or_404(
            Encounter.objects.filter(patient__in=accessible_patients(request.user)).select_related(
                "patient"
            ),
            pk=encounter_id,
        )
        form = ImagingOrderForm(request.POST if request.method == "POST" else None)
        status = 200
        if request.method == "POST" and form.is_valid():
            try:
                item = order_exam(user=request.user, encounter_id=encounter.pk, **form.cleaned_data)
            except RisConflict:
                form.add_error(
                    None, "Operação incompatível. Consulte o histórico e revise o pedido."
                )
                status = 409
            else:
                return redirect("ris:order_detail", pk=item.pk)
        form.fields["exam"].queryset = form.fields["exam"].queryset.filter(active=True)
        with transaction.atomic(), set_actor(request.user):
            accessed.send(Encounter, instance=encounter)
    except DatabaseError:
        return _failed()
    return render(
        request,
        "clinical/ris/order_form.html",
        {"form": form, "encounter": encounter},
        status=status,
    )
