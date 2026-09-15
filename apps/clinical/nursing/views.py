from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.cache import patch_vary_headers
from django.views.decorators.http import require_GET, require_http_methods

from apps.clinical.pep.models import Encounter
from apps.clinical.pep.permissions import accessible_patients

from .forms import VitalSignsRecordForm
from .models import VitalSignsRecord
from .permissions import (
    PERM_RECORD_VITALS,
    PERM_VIEW,
    can_record_vitals,
    has_nursing_permission,
)
from .services import record_vital_signs


def _no_store(response):
    response["Cache-Control"] = "private, no-store, max-age=0"
    patch_vary_headers(response, ("Cookie", "HX-Request"))
    return response


def _scoped_encounter_or_404(user, pk):
    return get_object_or_404(
        Encounter.objects.select_related("patient", "responsible_professional").filter(
            patient__in=accessible_patients(user)
        ),
        pk=pk,
    )


@login_required
@require_GET
def nursing_worklist(request):
    if not has_nursing_permission(request.user, PERM_VIEW):
        raise PermissionDenied

    encounters = (
        Encounter.objects.select_related("patient", "responsible_professional")
        .filter(patient__in=accessible_patients(request.user))
        .order_by("-started_at")
        .distinct()
    )
    paginator = Paginator(encounters, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    return _no_store(
        render(
            request,
            "clinical/nursing/worklist.html",
            {"encounters": page_obj.object_list, "page_obj": page_obj},
        )
    )


@login_required
@require_GET
def nursing_encounter(request, pk):
    if not has_nursing_permission(request.user, PERM_VIEW):
        raise PermissionDenied

    encounter = _scoped_encounter_or_404(request.user, pk)
    vital_signs = encounter.nursing_vital_signs.select_related(
        "recorded_by", "replaces"
    ).all()[:50]
    return _no_store(
        render(
            request,
            "clinical/nursing/encounter.html",
            {
                "encounter": encounter,
                "vital_signs": vital_signs,
                "can_record_vitals": can_record_vitals(request.user, encounter),
            },
        )
    )


@login_required
@require_http_methods(["GET", "POST"])
def vitals_create(request, encounter_id):
    if not has_nursing_permission(request.user, PERM_RECORD_VITALS):
        raise PermissionDenied

    encounter = _scoped_encounter_or_404(request.user, encounter_id)
    if not can_record_vitals(request.user, encounter):
        raise PermissionDenied

    form = VitalSignsRecordForm(
        request.POST or None,
        encounter=encounter,
    )
    if request.method == "POST" and form.is_valid():
        record_vital_signs(
            encounter=encounter,
            actor=request.user,
            data=form.cleaned_data,
        )
        messages.success(request, "Sinais vitais registrados com sucesso.")
        return _no_store(redirect("nursing:encounter", pk=encounter.pk))

    return _no_store(
        render(
            request,
            "clinical/nursing/vitals_form.html",
            {"form": form, "encounter": encounter},
        )
    )


@login_required
@require_http_methods(["GET", "POST"])
def vitals_correct(request, record_id):
    if not has_nursing_permission(request.user, PERM_RECORD_VITALS):
        raise PermissionDenied

    original = get_object_or_404(
        VitalSignsRecord.objects.select_related(
            "encounter__patient",
            "encounter__responsible_professional",
            "recorded_by",
        ).filter(encounter__patient__in=accessible_patients(request.user)),
        pk=record_id,
    )
    encounter = original.encounter
    if not can_record_vitals(request.user, encounter):
        raise PermissionDenied

    initial = None
    if request.method == "GET":
        initial = {
            field_name: getattr(original, field_name)
            for field_name in VitalSignsRecordForm.Meta.fields
        }

    form = VitalSignsRecordForm(
        request.POST or None,
        encounter=encounter,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        record_vital_signs(
            encounter=encounter,
            actor=request.user,
            data=form.cleaned_data,
            replaces=original,
        )
        messages.success(request, "Correção de sinais vitais registrada com sucesso.")
        return _no_store(redirect("nursing:encounter", pk=encounter.pk))

    return _no_store(
        render(
            request,
            "clinical/nursing/vitals_form.html",
            {
                "form": form,
                "encounter": encounter,
                "is_correction": True,
                "original_record": original,
            },
        )
    )
