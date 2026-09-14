from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.cache import patch_vary_headers
from django.views.generic import FormView, ListView, TemplateView

from .forms import AdmissionForm
from .permissions import can_admit, can_view_admissions, can_view_bed_map
from .selectors import admissions_for_user, bed_map_groups
from .services import AdtConflictError, admit_patient


class NoStoreResponseMixin:
    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        response["Cache-Control"] = "private, no-store, max-age=0"
        patch_vary_headers(response, ("Cookie", "HX-Request"))
        return response


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
        if can_view_bed_map(self.request.user):
            return reverse("adt:bed_map")
        if can_view_admissions(self.request.user):
            return reverse("adt:admission_list")
        return reverse(
            "pep:patient_detail",
            kwargs={"pk": self.admission.encounter.patient_id},
        )


class BedMapView(LoginRequiredMixin, NoStoreResponseMixin, TemplateView):
    template_name = "clinical/adt/bed_map.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_view_bed_map(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["bed_groups"] = bed_map_groups(self.request.user)
        context["can_admit"] = can_admit(self.request.user)
        return context


class BedMapPartialView(BedMapView):
    template_name = "clinical/adt/_bed_map.html"
