from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView

from .forms import (
    ClinicalEvolutionAmendmentForm,
    ClinicalEvolutionForm,
    EncounterForm,
    PatientForm,
)
from .models import ClinicalEvolution, Encounter, Patient, PatientAccessGrant
from .permissions import (
    accessible_patients,
    can_create_encounter,
    can_create_evolution,
    can_create_patient,
    is_internal_professional,
)


class PatientListView(LoginRequiredMixin, ListView):
    model = Patient
    template_name = "clinical/pep/patient_list.html"
    context_object_name = "patients"
    paginate_by = 25

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not is_internal_professional(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = accessible_patients(self.request.user)
        query = (self.request.GET.get("q") or "").strip()
        if query:
            queryset = queryset.filter(
                Q(full_name__icontains=query) | Q(identifier__icontains=query)
            )
        return queryset.order_by("full_name", "birth_date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = (self.request.GET.get("q") or "").strip()
        context["can_create_patient"] = can_create_patient(self.request.user)
        return context


class PatientCreateView(LoginRequiredMixin, CreateView):
    model = Patient
    form_class = PatientForm
    template_name = "clinical/pep/patient_form.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_create_patient(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    @transaction.atomic
    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.created_by = self.request.user
        self.object.save()
        PatientAccessGrant.objects.get_or_create(
            patient=self.object,
            user=self.request.user,
            defaults={
                "reason": "Cadastro inicial",
                "granted_by": self.request.user,
            },
        )
        messages.success(self.request, "Paciente cadastrado com sucesso.")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("pep:patient_detail", kwargs={"pk": self.object.pk})


class PatientDetailView(LoginRequiredMixin, DetailView):
    model = Patient
    template_name = "clinical/pep/patient_detail.html"
    context_object_name = "patient"

    def get_queryset(self):
        return accessible_patients(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["recent_encounters"] = self.object.encounters.select_related(
            "responsible_professional"
        )[:8]
        context["can_create_encounter"] = can_create_encounter(
            self.request.user,
            self.object,
        )
        return context


class PatientEncounterMixin:
    patient_url_kwarg = "patient_id"

    def get_patient(self):
        if not hasattr(self, "_patient"):
            self._patient = get_object_or_404(
                accessible_patients(self.request.user),
                pk=self.kwargs[self.patient_url_kwarg],
            )
        return self._patient

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["patient"] = self.get_patient()
        return context


class EncounterListView(LoginRequiredMixin, PatientEncounterMixin, ListView):
    model = Encounter
    template_name = "clinical/pep/encounter_list.html"
    context_object_name = "encounters"
    paginate_by = 25

    def get_queryset(self):
        return self.get_patient().encounters.select_related(
            "responsible_professional"
        ).all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_create_encounter"] = can_create_encounter(
            self.request.user,
            self.get_patient(),
        )
        return context


class EncounterCreateView(LoginRequiredMixin, PatientEncounterMixin, CreateView):
    model = Encounter
    form_class = EncounterForm
    template_name = "clinical/pep/encounter_form.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            patient = self.get_patient()
            if not can_create_encounter(request.user, patient):
                raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.patient = self.get_patient()
        form.instance.responsible_professional = self.request.user
        form.instance.created_by = self.request.user
        form.instance.status = Encounter.Status.OPEN
        messages.success(self.request, "Encontro clínico iniciado com sucesso.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("pep:encounter_detail", kwargs={"pk": self.object.pk})


class EncounterDetailView(LoginRequiredMixin, DetailView):
    model = Encounter
    template_name = "clinical/pep/encounter_detail.html"
    context_object_name = "encounter"

    def get_queryset(self):
        return Encounter.objects.filter(
            patient__in=accessible_patients(self.request.user)
        ).select_related("patient", "responsible_professional", "created_by")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["patient"] = self.object.patient
        context["evolutions"] = self.object.evolutions.select_related(
            "author",
            "amendment_of",
        ).all()
        context["can_create_evolution"] = can_create_evolution(
            self.request.user,
            self.object,
        )
        return context


class EncounterEvolutionMixin:
    encounter_url_kwarg = "encounter_id"

    def get_encounter(self):
        if not hasattr(self, "_encounter"):
            self._encounter = get_object_or_404(
                Encounter.objects.filter(
                    patient__in=accessible_patients(self.request.user)
                ).select_related("patient", "responsible_professional"),
                pk=self.kwargs[self.encounter_url_kwarg],
            )
        return self._encounter

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["encounter"] = self.get_encounter()
        context["patient"] = self.get_encounter().patient
        return context


class ClinicalEvolutionCreateView(
    LoginRequiredMixin,
    EncounterEvolutionMixin,
    CreateView,
):
    model = ClinicalEvolution
    form_class = ClinicalEvolutionForm
    template_name = "clinical/pep/evolution_form.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            encounter = self.get_encounter()
            if not can_create_evolution(request.user, encounter):
                raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.encounter = self.get_encounter()
        form.instance.author = self.request.user
        messages.success(self.request, "Evolução clínica registrada com sucesso.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("pep:evolution_detail", kwargs={"pk": self.object.pk})


class ClinicalEvolutionDetailView(LoginRequiredMixin, DetailView):
    model = ClinicalEvolution
    template_name = "clinical/pep/evolution_detail.html"
    context_object_name = "evolution"

    def get_queryset(self):
        return ClinicalEvolution.objects.filter(
            encounter__patient__in=accessible_patients(self.request.user)
        ).select_related(
            "encounter",
            "encounter__patient",
            "author",
            "amendment_of",
            "amendment_of__author",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["encounter"] = self.object.encounter
        context["patient"] = self.object.encounter.patient
        context["amendments"] = self.object.amendments.select_related("author").all()
        context["can_amend"] = can_create_evolution(
            self.request.user,
            self.object.encounter,
        )
        return context


class ClinicalEvolutionAmendmentCreateView(LoginRequiredMixin, CreateView):
    model = ClinicalEvolution
    form_class = ClinicalEvolutionAmendmentForm
    template_name = "clinical/pep/evolution_form.html"

    def get_original(self):
        if not hasattr(self, "_original"):
            self._original = get_object_or_404(
                ClinicalEvolution.objects.filter(
                    encounter__patient__in=accessible_patients(self.request.user)
                ).select_related("encounter", "encounter__patient", "author"),
                pk=self.kwargs["pk"],
            )
        return self._original

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            original = self.get_original()
            if not can_create_evolution(request.user, original.encounter):
                raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        original = self.get_original()
        form.instance.encounter = original.encounter
        form.instance.author = self.request.user
        form.instance.amendment_of = original
        messages.success(self.request, "Adendo registrado sem alterar a evolução original.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        original = self.get_original()
        context["original_evolution"] = original
        context["encounter"] = original.encounter
        context["patient"] = original.encounter.patient
        context["is_amendment"] = True
        return context

    def get_success_url(self):
        return reverse("pep:evolution_detail", kwargs={"pk": self.object.pk})
