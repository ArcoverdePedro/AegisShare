from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.cache import patch_vary_headers
from django.views.generic import FormView, ListView

from .catalog_services import CatalogStateError, create_drug, update_drug
from .forms import DrugForm
from .models import Drug
from .permissions import can_manage_reference_data, can_view_drug_catalog


class NoStoreResponseMixin:
    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        response["Cache-Control"] = "private, no-store, max-age=0"
        patch_vary_headers(response, ("Cookie", "HX-Request"))
        return response


class DrugCatalogView(LoginRequiredMixin, NoStoreResponseMixin, ListView):
    template_name = "clinical/prescription/drug_catalog.html"
    context_object_name = "drugs"
    paginate_by = 30

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_view_drug_catalog(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Drug.objects.order_by("name", "presentation", "code")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_manage_catalog"] = can_manage_reference_data(self.request.user)
        return context


class DrugCreateView(LoginRequiredMixin, NoStoreResponseMixin, FormView):
    template_name = "clinical/prescription/drug_form.html"
    form_class = DrugForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_manage_reference_data(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            create_drug(actor=self.request.user, **form.cleaned_data)
        except (CatalogStateError, ValidationError) as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        messages.success(self.request, "Medicamento cadastrado com sucesso.")
        return HttpResponseRedirect(reverse("prescription:drug_catalog"))


class DrugUpdateView(LoginRequiredMixin, NoStoreResponseMixin, FormView):
    template_name = "clinical/prescription/drug_form.html"
    form_class = DrugForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_manage_reference_data(request.user):
            raise PermissionDenied
        self.drug = get_object_or_404(Drug, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.drug
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["drug"] = self.drug
        return context

    def form_valid(self, form):
        try:
            update_drug(
                drug_id=self.drug.pk,
                actor=self.request.user,
                **form.cleaned_data,
            )
        except (CatalogStateError, ValidationError) as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        messages.success(self.request, "Medicamento atualizado com sucesso.")
        return HttpResponseRedirect(reverse("prescription:drug_catalog"))
