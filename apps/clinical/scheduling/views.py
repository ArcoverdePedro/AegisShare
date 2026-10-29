from auditlog.signals import accessed
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.clinical.pep.permissions import accessible_patients

from .forms import BookingForm, ReasonForm, SlotBatchForm
from .models import AgendaSlot, Appointment
from .services import (
    SchedulingConflict,
    block_slot,
    book_appointment,
    call_patient,
    cancel_appointment,
    check_in,
    create_slots,
    mark_no_show,
    require_permission,
)


def _visible_patients(user, appointments):
    """Nome so aparece para quem ja tem acesso ao paciente; demais veem a senha."""
    ids = {a.patient_id for a in appointments}
    return set(accessible_patients(user).filter(pk__in=ids).values_list("pk", flat=True))


@login_required
@require_GET
def agenda(request):
    require_permission(request.user)
    day = parse_date(request.GET.get("dia", "")) or timezone.localdate()
    slots = (
        AgendaSlot.objects.filter(starts_at__date=day)
        .select_related("professional")
        .annotate(
            taken=Count("appointments", filter=Q(appointments__status__in=Appointment.ACTIVE))
        )
        .prefetch_related(
            Prefetch("appointments", queryset=Appointment.objects.select_related("patient"))
        )
    )
    if request.GET.get("profissional"):
        slots = slots.filter(professional_id=request.GET["profissional"])
    slots = list(slots)
    appointments = [a for slot in slots for a in slot.appointments.all()]
    return render(
        request,
        "clinical/scheduling/agenda.html",
        {"slots": slots, "day": day, "visible": _visible_patients(request.user, appointments)},
    )


@login_required
@require_GET
def queue(request):
    require_permission(request.user)
    appointments = list(
        Appointment.objects.filter(
            status__in=[Appointment.Status.CHECKED_IN, Appointment.Status.CALLED],
            slot__starts_at__date=timezone.localdate(),
        )
        .select_related("patient", "slot__professional")
        .order_by("checked_in_at")
    )
    return render(
        request,
        "clinical/scheduling/queue.html",
        {"appointments": appointments, "visible": _visible_patients(request.user, appointments)},
    )


@login_required
@require_http_methods(["GET", "POST"])
def slot_create(request):
    require_permission(request.user, "manage_agenda")
    form = SlotBatchForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            created = create_slots(user=request.user, **form.cleaned_data)
        except SchedulingConflict as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"{len(created)} horário(s) aberto(s).")
            return redirect(f"{reverse('scheduling:agenda')}?dia={form.cleaned_data['day']}")
    return render(request, "clinical/scheduling/slot_form.html", {"form": form})


@login_required
@require_POST
def slot_block(request, pk):
    require_permission(request.user, "manage_agenda")
    slot = get_object_or_404(AgendaSlot, pk=pk)
    form = ReasonForm(request.POST)
    if form.is_valid():
        block_slot(user=request.user, slot=slot, **form.cleaned_data)
        messages.success(request, "Horário bloqueado. Remarque os pacientes já agendados.")
    else:
        messages.error(request, "Informe o motivo do bloqueio.")
    return redirect(
        f"{reverse('scheduling:agenda')}?dia={timezone.localtime(slot.starts_at).date()}"
    )


@login_required
@require_http_methods(["GET", "POST"])
def appointment_create(request, patient_id):
    require_permission(request.user, "book_appointment")
    patient = get_object_or_404(accessible_patients(request.user), pk=patient_id)
    previous = None
    if request.GET.get("remarcar"):
        previous = get_object_or_404(
            Appointment,
            pk=request.GET["remarcar"],
            patient=patient,
            status=Appointment.Status.BOOKED,
        )
    form = BookingForm(request.POST or None)
    status = 200
    if request.method == "POST" and form.is_valid():
        try:
            appointment = book_appointment(
                user=request.user, patient=patient, rescheduled_from=previous, **form.cleaned_data
            )
        except SchedulingConflict as exc:
            form.add_error(None, str(exc))
            status = 409
        else:
            return redirect("scheduling:appointment_detail", pk=appointment.pk)
    return render(
        request,
        "clinical/scheduling/appointment_form.html",
        {"form": form, "patient": patient, "previous": previous},
        status=status,
    )


ACTIONS = {
    "check_in": check_in,
    "call": call_patient,
    "no_show": mark_no_show,
}


@login_required
@require_http_methods(["GET", "POST"])
def appointment_detail(request, pk):
    require_permission(request.user)
    appointment = get_object_or_404(
        Appointment.objects.select_related("patient", "slot__professional", "encounter"), pk=pk
    )
    if not accessible_patients(request.user).filter(pk=appointment.patient_id).exists():
        raise PermissionDenied
    cancel_form = ReasonForm(request.POST or None)
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action in ACTIONS:
                ACTIONS[action](user=request.user, appointment=appointment)
            elif action == "cancel" and cancel_form.is_valid():
                cancel_appointment(
                    user=request.user, appointment=appointment, **cancel_form.cleaned_data
                )
            else:
                messages.error(request, "Ação inválida ou motivo ausente.")
        except SchedulingConflict as exc:
            messages.error(request, str(exc))
        return redirect("scheduling:appointment_detail", pk=appointment.pk)
    accessed.send(Appointment, instance=appointment)
    history = []
    cursor = appointment
    while cursor.rescheduled_from_id:
        cursor = Appointment.objects.select_related("slot").get(pk=cursor.rescheduled_from_id)
        history.append(cursor)
    return render(
        request,
        "clinical/scheduling/appointment_detail.html",
        {"appointment": appointment, "history": history, "cancel_form": cancel_form},
    )
