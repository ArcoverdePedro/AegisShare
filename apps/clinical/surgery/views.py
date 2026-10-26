from auditlog.context import set_actor
from auditlog.signals import accessed
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.clinical.pep.models import Encounter
from apps.clinical.pep.permissions import accessible_patients

from .forms import ScheduleForm, SurgicalCaseForm
from .models import OperatingRoom, SurgerySchedule, SurgicalCase
from .services import (
    SurgeryConflict,
    cancel_schedule,
    request_procedure,
    require_permission,
    schedule_case,
)


def _cases(user):
    return SurgicalCase.objects.filter(
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
def case_list(request):
    require_permission(request.user)
    try:
        page = Paginator(_cases(request.user), 25).get_page(request.GET.get("page"))
        page.object_list = list(page.object_list)
        with transaction.atomic(), set_actor(request.user):
            for item in page.object_list:
                accessed.send(SurgicalCase, instance=item)
    except DatabaseError:
        return _failed()
    return render(request, "clinical/surgery/case_list.html", {"page_obj": page})


@login_required
@require_GET
def case_detail(request, pk):
    require_permission(request.user)
    try:
        item = get_object_or_404(_cases(request.user), pk=pk)
        schedules = list(item.schedules.select_related("room", "surgeon", "scheduled_by"))
        with transaction.atomic(), set_actor(request.user):
            accessed.send(SurgicalCase, instance=item)
    except DatabaseError:
        return _failed()
    return render(
        request, "clinical/surgery/case_detail.html", {"item": item, "schedules": schedules}
    )


@sensitive_post_parameters()
@sensitive_variables()
@login_required
@require_http_methods(["GET", "POST"])
def case_create(request, encounter_id):
    require_permission(request.user, "request_procedure")
    try:
        encounter = get_object_or_404(
            Encounter.objects.filter(patient__in=accessible_patients(request.user)).select_related(
                "patient"
            ),
            pk=encounter_id,
        )
        form = SurgicalCaseForm(request.POST if request.method == "POST" else None)
        status = 200
        if request.method == "POST" and form.is_valid():
            try:
                item = request_procedure(
                    user=request.user, encounter_id=encounter.pk, **form.cleaned_data
                )
            except SurgeryConflict:
                form.add_error(
                    None, "Operação incompatível. Consulte o histórico e revise a solicitação."
                )
                status = 409
            else:
                return redirect("surgery:case_detail", pk=item.pk)
        form.fields["procedure"].queryset = form.fields["procedure"].queryset.filter(active=True)
        with transaction.atomic(), set_actor(request.user):
            accessed.send(Encounter, instance=encounter)
    except DatabaseError:
        return _failed()
    return render(
        request,
        "clinical/surgery/case_form.html",
        {"form": form, "encounter": encounter},
        status=status,
    )


@login_required
@require_GET
def room_map(request):
    require_permission(request.user)
    day = parse_date(request.GET.get("dia", "")) or timezone.localdate()
    schedules = (
        SurgerySchedule.objects.filter(status=SurgerySchedule.Status.SCHEDULED, starts_at__date=day)
        .select_related("room", "surgeon", "case__encounter")
        .order_by("room__code", "starts_at")
    )
    visible = set(accessible_patients(request.user).values_list("pk", flat=True))
    return render(
        request,
        "clinical/surgery/room_map.html",
        {
            "day": day,
            "rooms": OperatingRoom.objects.filter(active=True),
            "schedules": schedules,
            "visible": visible,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def schedule_create(request, pk):
    require_permission(request.user, "schedule_case")
    item = get_object_or_404(_cases(request.user), pk=pk)
    previous = None
    if request.GET.get("remarcar"):
        previous = get_object_or_404(
            item.schedules, pk=request.GET["remarcar"], status=SurgerySchedule.Status.SCHEDULED
        )
    form = ScheduleForm(request.POST or None)
    status = 200
    if request.method == "POST" and form.is_valid():
        try:
            schedule_case(
                user=request.user, case=item, rescheduled_from=previous, **form.cleaned_data
            )
        except SurgeryConflict as exc:
            form.add_error(None, str(exc))
            status = 409
        else:
            messages.success(request, "Cirurgia agendada.")
            return redirect("surgery:case_detail", pk=item.pk)
    return render(
        request,
        "clinical/surgery/schedule_form.html",
        {"form": form, "item": item, "previous": previous},
        status=status,
    )


@login_required
@require_POST
def schedule_cancel(request, pk, schedule_id):
    item = get_object_or_404(_cases(request.user), pk=pk)
    schedule = get_object_or_404(item.schedules, pk=schedule_id)
    try:
        cancel_schedule(user=request.user, schedule=schedule, reason=request.POST.get("reason", ""))
        messages.success(request, "Agendamento cancelado; sala liberada.")
    except SurgeryConflict as exc:
        messages.error(request, str(exc))
    return redirect("surgery:case_detail", pk=item.pk)
