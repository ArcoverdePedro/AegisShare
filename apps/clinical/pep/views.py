from auditlog.signals import accessed
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import InvalidPage, Paginator
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe

from .events import emit_clinical_event
from .forms import (
    ClinicalEvolutionAmendmentForm,
    ClinicalEvolutionForm,
    EncounterForm,
    PatientForm,
)
from .models import ClinicalEvolution, Encounter, PatientAccessGrant
from .permissions import (
    accessible_patients,
    can_create_encounter,
    can_create_evolution,
    can_create_patient,
    is_internal_professional,
)


def _page(request, queryset):
    paginator = Paginator(queryset, 25)
    number = request.GET.get("page") or 1
    try:
        return paginator.page(paginator.num_pages if number == "last" else number)
    except InvalidPage as exc:
        raise Http404("Página inválida.") from exc


def _encounters(user):
    return Encounter.objects.filter(patient__in=accessible_patients(user)).select_related(
        "patient", "responsible_professional", "created_by"
    )


def _evolutions(user):
    return ClinicalEvolution.objects.filter(
        encounter__patient__in=accessible_patients(user)
    ).select_related("encounter__patient", "author", "amendment_of__author")


@login_required
@require_safe
def patient_list(request):
    if not is_internal_professional(request.user):
        raise PermissionDenied
    query = (request.GET.get("q") or "").strip()
    patients = accessible_patients(request.user)
    if query:
        patients = patients.filter(Q(full_name__icontains=query) | Q(identifier__icontains=query))
    page = _page(request, patients.order_by("full_name", "birth_date"))
    return render(
        request,
        "clinical/pep/patient_list.html",
        {
            "patients": page.object_list,
            "page_obj": page,
            "is_paginated": page.has_other_pages(),
            "query": query,
            "can_create_patient": can_create_patient(request.user),
        },
    )


@login_required
@require_http_methods(["GET", "HEAD", "POST"])
def patient_create(request):
    if not can_create_patient(request.user):
        raise PermissionDenied
    form = PatientForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            patient = form.save(commit=False)
            patient.created_by = request.user
            patient.save()
            PatientAccessGrant.objects.get_or_create(
                patient=patient,
                user=request.user,
                defaults={"reason": "Cadastro inicial", "granted_by": request.user},
            )
        messages.success(request, "Paciente cadastrado com sucesso.")
        return redirect("pep:patient_detail", pk=patient.pk)
    return render(request, "clinical/pep/patient_form.html", {"form": form})


@login_required
@require_safe
def patient_detail(request, pk):
    patient = get_object_or_404(accessible_patients(request.user), pk=pk)
    accessed.send(type(patient), instance=patient)
    return render(
        request,
        "clinical/pep/patient_detail.html",
        {
            "patient": patient,
            "recent_encounters": patient.encounters.select_related("responsible_professional")[:8],
            "can_create_encounter": can_create_encounter(request.user, patient),
        },
    )


@login_required
@require_safe
def encounter_list(request, patient_id):
    patient = get_object_or_404(accessible_patients(request.user), pk=patient_id)
    page = _page(request, patient.encounters.select_related("responsible_professional"))
    return render(
        request,
        "clinical/pep/encounter_list.html",
        {
            "patient": patient,
            "encounters": page.object_list,
            "page_obj": page,
            "is_paginated": page.has_other_pages(),
            "can_create_encounter": can_create_encounter(request.user, patient),
        },
    )


@login_required
@require_http_methods(["GET", "HEAD", "POST"])
def encounter_create(request, patient_id):
    patient = get_object_or_404(accessible_patients(request.user), pk=patient_id)
    if not can_create_encounter(request.user, patient):
        raise PermissionDenied
    form = EncounterForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        encounter = form.save(commit=False)
        encounter.patient = patient
        encounter.responsible_professional = request.user
        encounter.created_by = request.user
        encounter.status = Encounter.Status.OPEN
        encounter.save()
        emit_clinical_event(
            event="encounter.created",
            patient_id=patient.pk,
            encounter_id=encounter.pk,
            object_id=encounter.pk,
        )
        messages.success(request, "Encontro clínico iniciado com sucesso.")
        return redirect("pep:encounter_detail", pk=encounter.pk)
    if request.method != "POST":
        accessed.send(type(patient), instance=patient)
    return render(request, "clinical/pep/encounter_form.html", {"form": form, "patient": patient})


@login_required
@require_safe
def encounter_detail(request, pk):
    encounter = get_object_or_404(_encounters(request.user), pk=pk)
    accessed.send(type(encounter), instance=encounter)
    return render(
        request,
        "clinical/pep/encounter_detail.html",
        {
            "encounter": encounter,
            "patient": encounter.patient,
            "evolutions": encounter.evolutions.select_related("author", "amendment_of"),
            "can_create_evolution": can_create_evolution(request.user, encounter),
        },
    )


@login_required
@require_http_methods(["GET", "HEAD", "POST"])
def evolution_create(request, encounter_id):
    encounter = get_object_or_404(_encounters(request.user), pk=encounter_id)
    if not can_create_evolution(request.user, encounter):
        raise PermissionDenied
    form = ClinicalEvolutionForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        evolution = form.save(commit=False)
        evolution.encounter = encounter
        evolution.author = request.user
        evolution.save()
        emit_clinical_event(
            event="evolution.created",
            patient_id=encounter.patient_id,
            encounter_id=encounter.pk,
            object_id=evolution.pk,
        )
        messages.success(request, "Evolução clínica registrada com sucesso.")
        return redirect("pep:evolution_detail", pk=evolution.pk)
    if request.method != "POST":
        accessed.send(type(encounter), instance=encounter)
    return render(
        request,
        "clinical/pep/evolution_form.html",
        {
            "form": form,
            "encounter": encounter,
            "patient": encounter.patient,
        },
    )


@login_required
@require_safe
def evolution_detail(request, pk):
    evolution = get_object_or_404(_evolutions(request.user), pk=pk)
    accessed.send(type(evolution), instance=evolution)
    return render(
        request,
        "clinical/pep/evolution_detail.html",
        {
            "evolution": evolution,
            "encounter": evolution.encounter,
            "patient": evolution.encounter.patient,
            "amendments": evolution.amendments.select_related("author"),
            "can_amend": can_create_evolution(request.user, evolution.encounter),
        },
    )


@login_required
@require_http_methods(["GET", "HEAD", "POST"])
def evolution_amendment_create(request, pk):
    original = get_object_or_404(_evolutions(request.user), pk=pk)
    if not can_create_evolution(request.user, original.encounter):
        raise PermissionDenied
    form = ClinicalEvolutionAmendmentForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            evolution = ClinicalEvolution.objects.create(
                encounter=original.encounter,
                author=request.user,
                amendment_of=original,
                amendment_reason=form.cleaned_data["amendment_reason"],
                content=form.cleaned_data["content"],
            )
            emit_clinical_event(
                event="evolution.amended",
                patient_id=original.encounter.patient_id,
                encounter_id=original.encounter_id,
                object_id=evolution.pk,
            )
        messages.success(request, "Adendo registrado sem alterar a evolução original.")
        return redirect("pep:evolution_detail", pk=evolution.pk)
    if request.method != "POST":
        accessed.send(type(original), instance=original)
    return render(
        request,
        "clinical/pep/evolution_form.html",
        {
            "form": form,
            "original_evolution": original,
            "encounter": original.encounter,
            "patient": original.encounter.patient,
            "is_amendment": True,
        },
    )
