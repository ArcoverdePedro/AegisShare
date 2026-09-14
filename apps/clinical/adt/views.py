from auditlog.signals import accessed
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.cache import patch_vary_headers
from django.views.generic import FormView, ListView, TemplateView

from .forms import AdmissionForm, DischargeForm, TransferForm
from .lifecycle import discharge_patient, transfer_patient
from .permissions import (
    can_admit,
    can_discharge,
    can_transfer,
    can_view_admissions,
    can_view_bed_map,
)
from .selectors import admissions_for_user, bed_map_groups
from .services import AdtConflictError, admit_patient


class NoStoreResponseMixin:
    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        response["Cache-Control"] = "private, no-store, max-age=0"
        patch_vary_headers(response, ("Cookie", "HX-Request"))
        return response


def _success_url(user, admission):
    if can_view_bed_map(user):
        return reverse("adt:bed_map")
    if can_view_admissions(user):
        return reverse("adt:admission_list")
    return reverse(
        "pep:patient_detail",
        kwargs={"pk": admission.encounter.patient_id},
    )


def _audit_access(instance):
    accessed.send(instance.__class__, instance=instance)


def _audit_patient_once(patient, seen):
    if patient.pk in seen:
        return
    seen.add(patient.pk)
    _audit_access(patient)


class AdmissionListView(LoginRequiredMixin, NoStoreResponseMixin, ListView):
    template_name = "clinical/adt/admission_list.html"
    context_object_name = "admissions"
    paginate_by = 25

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_view_admissions(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return admissions_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_transfer"] = can_transfer(self.request.user)
        context["can_discharge"] = can_discharge(self.request.user)

        seen_patients = set()
        for admission in context["admissions"]:
            _audit_access(admission)
            _audit_patient_once(admission.encounter.patient, seen_patients)
        return context


class AdmissionCreateView(LoginRequiredMixin, NoStoreResponseMixin, FormView):
    template_name = "clinical/adt/admission_form.html"
    form_class = AdmissionForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_admit(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        try:
            admission = admit_patient(
                encounter_id=form.cleaned_data["encounter"].pk,
                bed_id=form.cleaned_data["bed"].pk,
                actor=self.request.user,
                operation_key=form.cleaned_data["operation_key"],
                admitted_at=form.cleaned_data["admitted_at"],
            )
        except AdtConflictError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        self.admission = admission
        messages.success(self.request, "Admissão registrada com sucesso.")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return _success_url(self.request.user, self.admission)


class TransferCreateView(LoginRequiredMixin, NoStoreResponseMixin, FormView):
    template_name = "clinical/adt/transfer_form.html"
    form_class = TransferForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_transfer(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        try:
            transfer = transfer_patient(
                admission_id=form.cleaned_data["admission"].pk,
                destination_bed_id=form.cleaned_data["destination_bed"].pk,
                actor=self.request.user,
                operation_key=form.cleaned_data["operation_key"],
                transferred_at=form.cleaned_data["transferred_at"],
                reason=form.cleaned_data["reason"],
            )
        except AdtConflictError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        self.admission = transfer.admission
        messages.success(self.request, "Transferência registrada com sucesso.")
        return HttpResponseRedirect(_success_url(self.request.user, self.admission))


class DischargeCreateView(LoginRequiredMixin, NoStoreResponseMixin, FormView):
    template_name = "clinical/adt/discharge_form.html"
    form_class = DischargeForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_discharge(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        try:
            discharge = discharge_patient(
                admission_id=form.cleaned_data["admission"].pk,
                disposition=form.cleaned_data["disposition"],
                actor=self.request.user,
                operation_key=form.cleaned_data["operation_key"],
                discharged_at=form.cleaned_data["discharged_at"],
                reason=form.cleaned_data["reason"],
            )
        except AdtConflictError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        self.admission = discharge.admission
        messages.success(self.request, "Alta registrada com sucesso.")
        return HttpResponseRedirect(_success_url(self.request.user, self.admission))


class BedMapView(LoginRequiredMixin, NoStoreResponseMixin, TemplateView):
    template_name = "clinical/adt/bed_map.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_view_bed_map(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        groups = bed_map_groups(self.request.user)
        context["bed_groups"] = groups
        context["can_admit"] = can_admit(self.request.user)
        context["can_transfer"] = can_transfer(self.request.user)
        context["can_discharge"] = can_discharge(self.request.user)

        seen_patients = set()
        for _location, rows in groups:
            for row in rows:
                occupancy = row["occupancy"]
                if occupancy is not None:
                    _audit_access(occupancy)
                patient = row["patient"]
                if row["show_phi"] and patient is not None:
                    _audit_patient_once(patient, seen_patients)
        return context


class BedMapPartialView(BedMapView):
    template_name = "clinical/adt/_bed_map.html"
