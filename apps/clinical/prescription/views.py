from decimal import Decimal

from auditlog.signals import accessed
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import DecimalField, Prefetch, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import patch_vary_headers
from django.views.decorators.http import require_http_methods, require_POST
from django.views.generic import FormView, ListView

from apps.clinical.pep.permissions import accessible_patients

from .catalog_services import CatalogStateError, create_drug, update_drug
from .dispense_services import DispenseStateError, dispense_medication
from .forms import (
    DrugForm,
    MedicationDispenseHeaderForm,
    MedicationDispenseItemFormSet,
    MedicationRequestCancelForm,
    MedicationRequestCreateForm,
    MedicationRequestItemFormSet,
    MedicationRequestSubmitForm,
    MedicationRequestValidateForm,
)
from .models import Drug, Lot, MedicationDispense, MedicationRequest, MedicationSafetyReview, StockItem
from .permissions import (
    PERM_DISPENSE,
    PERM_PRESCRIBE,
    PERM_VALIDATE,
    PERM_VIEW,
    PERM_VIEW_DISPENSE,
    can_dispense_prescription,
    can_manage_reference_data,
    can_manage_stock,
    can_validate_prescription,
    can_view_dispense,
    can_view_drug_catalog,
    can_view_prescription,
    can_view_stock,
    has_rx_permission,
)
from .safety import SafetyStateError, evaluate_medication_safety
from .selectors import visible_medication_requests
from .services import (
    PrescriptionStateError,
    PrescriptionValidationError,
    add_medication_request_item,
    cancel_medication_request,
    create_medication_request,
    submit_medication_request,
    validate_medication_request,
)


def _no_store(response):
    response["Cache-Control"] = "private, no-store, max-age=0"
    patch_vary_headers(response, ("Cookie", "HX-Request"))
    return response


def _scoped_request_or_404(user, pk):
    return get_object_or_404(
        MedicationRequest.objects.select_related("encounter__patient", "authored_by", "validated_by").filter(
            encounter__patient__in=accessible_patients(user)
        ),
        pk=pk,
    )


def _scoped_dispense_or_404(user, pk):
    return get_object_or_404(
        MedicationDispense.objects.select_related(
            "medication_request__encounter__patient",
            "dispensed_by",
        ).filter(medication_request__encounter__patient__in=accessible_patients(user)),
        pk=pk,
    )


class NoStoreResponseMixin:
    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        return _no_store(response)


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
        for drug in context["drugs"]:
            accessed.send(drug.__class__, instance=drug)
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
        accessed.send(self.drug.__class__, instance=self.drug)
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


class PharmacyStockView(LoginRequiredMixin, NoStoreResponseMixin, ListView):
    template_name = "clinical/prescription/pharmacy_stock.html"
    context_object_name = "stock_items"
    paginate_by = 30

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_view_stock(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        today = timezone.localdate()
        quantity_field = DecimalField(max_digits=14, decimal_places=4)
        lots = Lot.objects.select_related("stock_item").order_by("expires_on", "lot_number")
        return (
            StockItem.objects.select_related("drug")
            .prefetch_related(Prefetch("lots", queryset=lots))
            .annotate(
                eligible_quantity=Coalesce(
                    Sum(
                        "lots__quantity_available",
                        filter=Q(lots__active=True, lots__expires_on__gte=today),
                    ),
                    Value(Decimal("0"), output_field=quantity_field),
                    output_field=quantity_field,
                )
            )
            .order_by("drug__name", "storage_location")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        for stock_item in context["stock_items"]:
            accessed.send(stock_item.__class__, instance=stock_item)
            stock_item.is_low = stock_item.eligible_quantity <= stock_item.minimum_level
            for lot in stock_item.lots.all():
                accessed.send(lot.__class__, instance=lot)
                lot.is_expired = lot.expires_on < today
        context["can_manage_stock"] = can_manage_stock(self.request.user)
        return context


@login_required
@require_http_methods(["GET"])
def prescription_list(request):
    if not has_rx_permission(request.user, PERM_VIEW):
        raise PermissionDenied
    page = Paginator(visible_medication_requests(request.user), 30).get_page(request.GET.get("page"))
    for medication_request in page.object_list:
        accessed.send(medication_request.__class__, instance=medication_request)
    return _no_store(
        render(
            request,
            "clinical/prescription/prescription_list.html",
            {"page_obj": page, "prescriptions": page.object_list},
        )
    )


@login_required
@require_http_methods(["GET", "POST"])
def prescription_create(request):
    if not has_rx_permission(request.user, PERM_PRESCRIBE):
        raise PermissionDenied

    form = MedicationRequestCreateForm(
        request.POST or None,
        actor=request.user,
    )
    formset = MedicationRequestItemFormSet(request.POST or None, prefix="items")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        try:
            with transaction.atomic():
                medication_request = create_medication_request(
                    encounter_id=form.cleaned_data["encounter"].pk,
                    actor=request.user,
                    replaces_id=form.cleaned_data.get("replaces"),
                )
                for sequence, item_form in enumerate(formset.forms, start=1):
                    add_medication_request_item(
                        request_id=medication_request.pk,
                        actor=request.user,
                        drug_id=item_form.cleaned_data["drug"].pk,
                        dose=item_form.cleaned_data["dose"],
                        dose_unit=item_form.cleaned_data["dose_unit"],
                        route=item_form.cleaned_data["route"],
                        frequency=item_form.cleaned_data["frequency"],
                        duration_value=item_form.cleaned_data.get("duration_value"),
                        duration_unit=item_form.cleaned_data.get("duration_unit", ""),
                        instructions=item_form.cleaned_data.get("instructions", ""),
                        sequence=sequence,
                    )
        except (PrescriptionStateError, ValidationError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Prescrição criada como rascunho.")
            return redirect("prescription:prescription_detail", pk=medication_request.pk)

    return _no_store(
        render(
            request,
            "clinical/prescription/new.html",
            {"form": form, "item_formset": formset},
        )
    )


@login_required
@require_http_methods(["GET"])
def prescription_detail(request, pk):
    medication_request = _scoped_request_or_404(request.user, pk)
    if not can_view_prescription(request.user, medication_request):
        raise PermissionDenied
    accessed.send(medication_request.__class__, instance=medication_request)
    items = list(medication_request.items.select_related("drug").order_by("sequence"))
    for item in items:
        accessed.send(item.__class__, instance=item)
    reviews = medication_request.safety_reviews.prefetch_related(
        "findings__interaction", "findings__dose_rule", "findings__request_item"
    ).order_by("-created_at")
    return _no_store(
        render(
            request,
            "clinical/prescription/detail.html",
            {
                "prescription": medication_request,
                "items": items,
                "reviews": reviews,
                "submit_form": MedicationRequestSubmitForm(),
                "cancel_form": MedicationRequestCancelForm(),
            },
        )
    )


@login_required
@require_POST
def prescription_submit(request, pk):
    medication_request = _scoped_request_or_404(request.user, pk)
    if not has_rx_permission(request.user, PERM_PRESCRIBE):
        raise PermissionDenied
    form = MedicationRequestSubmitForm(request.POST)
    if form.is_valid():
        try:
            submit_medication_request(request_id=medication_request.pk, actor=request.user)
        except (PrescriptionStateError, PermissionDenied) as exc:
            messages.error(request, str(exc) or "Não foi possível submeter a prescrição.")
        else:
            messages.success(request, "Prescrição submetida para validação farmacêutica.")
    return redirect("prescription:prescription_detail", pk=medication_request.pk)


@login_required
@require_http_methods(["GET", "POST"])
def prescription_validate(request, pk):
    medication_request = _scoped_request_or_404(request.user, pk)
    if not has_rx_permission(request.user, PERM_VALIDATE) or not can_validate_prescription(
        request.user, medication_request
    ):
        raise PermissionDenied

    form = MedicationRequestValidateForm(request.POST or None)
    blocked_review = None
    if request.method == "POST" and form.is_valid():
        try:
            validate_medication_request(
                request_id=medication_request.pk,
                actor=request.user,
                manual_allergy_review_confirmed=form.cleaned_data[
                    "manual_allergy_review_confirmed"
                ],
            )
        except PrescriptionValidationError as exc:
            form.add_error(None, str(exc))
            if exc.review_id:
                blocked_review = MedicationSafetyReview.objects.prefetch_related(
                    "findings__interaction", "findings__dose_rule", "findings__request_item"
                ).filter(pk=exc.review_id).first()
        except (PrescriptionStateError, SafetyStateError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Prescrição validada com sucesso.")
            return redirect("prescription:prescription_detail", pk=medication_request.pk)

    snapshot = None
    if medication_request.status == MedicationRequest.Status.SUBMITTED:
        snapshot = evaluate_medication_safety(medication_request)
    return _no_store(
        render(
            request,
            "clinical/prescription/validate.html",
            {
                "prescription": medication_request,
                "form": form,
                "safety": snapshot,
                "blocked_review": blocked_review,
            },
        )
    )


@login_required
@require_POST
def prescription_cancel(request, pk):
    medication_request = _scoped_request_or_404(request.user, pk)
    form = MedicationRequestCancelForm(request.POST)
    if form.is_valid():
        try:
            cancel_medication_request(
                request_id=medication_request.pk,
                actor=request.user,
                reason=form.cleaned_data["reason"],
            )
        except (PrescriptionStateError, PermissionDenied) as exc:
            messages.error(request, str(exc) or "Não foi possível cancelar a prescrição.")
        else:
            messages.success(request, "Prescrição cancelada sem apagar o histórico.")
    return redirect("prescription:prescription_detail", pk=medication_request.pk)


@login_required
@require_http_methods(["GET", "POST"])
def dispense_create(request, pk):
    medication_request = _scoped_request_or_404(request.user, pk)
    if not has_rx_permission(request.user, PERM_DISPENSE) or not can_dispense_prescription(
        request.user, medication_request
    ):
        raise PermissionDenied

    header_form = MedicationDispenseHeaderForm(request.POST or None)
    item_formset = MedicationDispenseItemFormSet(
        request.POST or None,
        prefix="items",
        form_kwargs={"medication_request": medication_request},
    )
    if request.method == "POST" and header_form.is_valid() and item_formset.is_valid():
        allocations = [
            {
                "request_item_id": form.cleaned_data["request_item"].pk,
                "lot_id": form.cleaned_data["lot"].pk,
                "quantity": form.cleaned_data["quantity"],
            }
            for form in item_formset.forms
        ]
        try:
            dispense = dispense_medication(
                request_id=medication_request.pk,
                actor=request.user,
                operation_key=header_form.cleaned_data["operation_key"],
                allocations=allocations,
            )
        except (DispenseStateError, ValidationError) as exc:
            header_form.add_error(None, str(exc))
        else:
            messages.success(request, "Dispensação concluída e estoque atualizado.")
            return redirect("prescription:dispense_detail", pk=dispense.pk)

    return _no_store(
        render(
            request,
            "clinical/prescription/dispense.html",
            {
                "prescription": medication_request,
                "form": header_form,
                "item_formset": item_formset,
            },
        )
    )


@login_required
@require_http_methods(["GET"])
def dispense_list(request):
    if not has_rx_permission(request.user, PERM_VIEW_DISPENSE):
        raise PermissionDenied
    queryset = (
        MedicationDispense.objects.select_related(
            "medication_request__encounter__patient", "dispensed_by"
        )
        .filter(medication_request__encounter__patient__in=accessible_patients(request.user))
        .order_by("-dispensed_at")
        .distinct()
    )
    page = Paginator(queryset, 30).get_page(request.GET.get("page"))
    for dispense in page.object_list:
        accessed.send(dispense.__class__, instance=dispense)
    return _no_store(
        render(
            request,
            "clinical/prescription/dispense_list.html",
            {"page_obj": page, "dispenses": page.object_list},
        )
    )


@login_required
@require_http_methods(["GET"])
def dispense_detail(request, pk):
    dispense = _scoped_dispense_or_404(request.user, pk)
    if not can_view_dispense(request.user, dispense):
        raise PermissionDenied
    accessed.send(dispense.__class__, instance=dispense)
    items = list(
        dispense.items.select_related(
            "request_item__drug", "lot__stock_item__drug"
        ).order_by("created_at")
    )
    for item in items:
        accessed.send(item.__class__, instance=item)
    return _no_store(
        render(
            request,
            "clinical/prescription/dispense_detail.html",
            {"dispense": dispense, "items": items},
        )
    )
