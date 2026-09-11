from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView

from .forms import PatientForm
from .models import Patient, PatientAccessGrant
from .permissions import accessible_patients, can_create_patient, is_internal_professional


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
        return super(CreateView, self).form_valid(form)

    def get_success_url(self):
        return reverse("pep:patient_detail", kwargs={"pk": self.object.pk})


class PatientDetailView(LoginRequiredMixin, DetailView):
    model = Patient
    template_name = "clinical/pep/patient_detail.html"
    context_object_name = "patient"

    def get_queryset(self):
        return accessible_patients(self.request.user)
