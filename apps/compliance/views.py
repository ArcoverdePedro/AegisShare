import logging

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

from apps.clinical.pep.permissions import accessible_patients, is_internal_professional

from .forms import (
    CONFLICT_MESSAGE,
    DataSubjectRequestForm,
    RequestFilterForm,
    RequestTransitionForm,
)
from .models import DataSubjectRequest, DataSubjectRequestEvent

logger = logging.getLogger(__name__)


def _require_permission(user, capability=None):
    permissions = ["compliance.view_requests"]
    if capability:
        permissions.append(f"compliance.{capability}")
    if not is_internal_professional(user) or not user.has_perms(permissions):
        raise PermissionDenied


def _accessible_requests(user):
    return DataSubjectRequest.objects.filter(patient__in=accessible_patients(user))


def _operation_failed():
    logger.error("Falha ao persistir operação de solicitação do titular.")
    return HttpResponse(
        "Não foi possível concluir a operação. Tente novamente mais tarde.",
        status=503,
        content_type="text/plain; charset=utf-8",
    )


@login_required
@require_GET
def request_list(request):
    _require_permission(request.user)
    form = RequestFilterForm(request.GET)
    queryset = _accessible_requests(request.user).select_related("patient", "created_by")
    if not form.is_valid():
        queryset = queryset.none()
    elif form.cleaned_data["status"]:
        queryset = queryset.filter(status=form.cleaned_data["status"])
    page = Paginator(queryset, 25).get_page(request.GET.get("page"))
    page.object_list = list(page.object_list)
    with transaction.atomic(), set_actor(request.user):
        for item in page.object_list:
            accessed.send(DataSubjectRequest, instance=item)
    return render(request, "compliance/request_list.html", {"page_obj": page, "filter_form": form})


@sensitive_post_parameters()
@sensitive_variables()
@login_required
@require_http_methods(["GET", "POST"])
def request_create(request):
    _require_permission(request.user, "register_request")
    form = DataSubjectRequestForm(
        request.POST if request.method == "POST" else None, user=request.user
    )
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic(), set_actor(request.user):
                patient = get_object_or_404(
                    accessible_patients(request.user), pk=form.cleaned_data["patient"].pk
                )
                item = form.save(commit=False)
                item.patient = patient
                item.created_by = request.user
                item.save()
                DataSubjectRequestEvent.objects.create(
                    request=item, to_status=item.status, actor=request.user
                )
        except DatabaseError:
            return _operation_failed()
        messages.success(request, "Solicitação registrada.")
        return redirect("compliance:request_detail", pk=item.pk)
    return render(request, "compliance/request_form.html", {"form": form})


@login_required
@require_GET
def request_detail(request, pk):
    _require_permission(request.user)
    item = get_object_or_404(
        _accessible_requests(request.user).select_related("patient", "created_by"), pk=pk
    )
    with set_actor(request.user):
        accessed.send(DataSubjectRequest, instance=item)
    return render(
        request,
        "compliance/request_detail.html",
        {
            "item": item,
            "events": item.events.select_related("actor"),
        },
    )


@sensitive_post_parameters()
@sensitive_variables()
@login_required
@require_http_methods(["GET", "POST"])
def request_transition(request, pk):
    _require_permission(request.user, "process_request")
    item = get_object_or_404(_accessible_requests(request.user).select_related("patient"), pk=pk)
    if request.method == "GET" and item.status == DataSubjectRequest.Status.CLOSED:
        messages.info(request, "Esta solicitação já foi encerrada administrativamente.")
        return redirect("compliance:request_detail", pk=pk)

    form = RequestTransitionForm(
        request.POST if request.method == "POST" else None, current_status=item.status
    )
    response_status = 200
    if request.method == "POST":
        try:
            with transaction.atomic(), set_actor(request.user):
                # Sem joins: bloqueia apenas a solicitação, não paciente ou ator.
                locked = get_object_or_404(DataSubjectRequest.objects.select_for_update(), pk=pk)
                get_object_or_404(_accessible_requests(request.user), pk=locked.pk)
                form = RequestTransitionForm(request.POST, current_status=locked.status)
                if form.is_valid():
                    previous_status = locked.status
                    locked.status = form.cleaned_data["target_status"]
                    locked.save(update_fields=["status"])
                    DataSubjectRequestEvent.objects.create(
                        request=locked,
                        from_status=previous_status,
                        to_status=locked.status,
                        actor=request.user,
                        note=form.cleaned_data["note"],
                    )
                else:
                    response_status = (
                        409
                        if form.is_conflict or locked.status == DataSubjectRequest.Status.CLOSED
                        else 200
                    )
                    if response_status == 409:
                        form.add_error(None, CONFLICT_MESSAGE)
            if not form.errors:
                messages.success(request, "Andamento registrado.")
                return redirect("compliance:request_detail", pk=pk)
        except DatabaseError:
            return _operation_failed()

    with set_actor(request.user):
        accessed.send(DataSubjectRequest, instance=item)
    return render(
        request,
        "compliance/request_transition.html",
        {"item": item, "form": form},
        status=response_status,
    )
