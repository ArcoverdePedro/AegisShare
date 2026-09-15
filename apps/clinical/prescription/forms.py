import uuid

from django import forms
from django.forms import formset_factory

from apps.clinical.pep.models import Encounter
from apps.clinical.pep.permissions import accessible_patients

from .models import Drug, Lot, MedicationRequestItem
from .permissions import PERM_PRESCRIBE, has_rx_permission


def _encounter_label(encounter):
    return (
        f"{encounter.patient.full_name} — {encounter.get_encounter_type_display()} — "
        f"{encounter.started_at:%d/%m/%Y %H:%M}"
    )


def _drug_label(drug):
    return f"{drug.name} — {drug.presentation} ({drug.code})"


def _request_item_label(item):
    return (
        f"{item.drug.name} — {item.dose} {item.dose_unit} — "
        f"{item.route} — {item.frequency}"
    )


def _lot_label(lot):
    return (
        f"{lot.lot_number} — validade {lot.expires_on:%d/%m/%Y} — "
        f"saldo {lot.quantity_available} {lot.stock_item.drug.dispense_unit}"
    )


class DrugForm(forms.ModelForm):
    class Meta:
        model = Drug
        fields = [
            "code",
            "name",
            "presentation",
            "strength_text",
            "route_hint",
            "dispense_unit",
            "active",
        ]
        labels = {
            "code": "Código interno",
            "name": "Medicamento",
            "presentation": "Apresentação",
            "strength_text": "Concentração / força",
            "route_hint": "Via sugerida (informativa)",
            "dispense_unit": "Unidade de dispensação",
            "active": "Ativo para novas prescrições",
        }
        help_texts = {
            "route_hint": "Campo informativo; não seleciona via automaticamente na prescrição.",
            "active": "Prefira desativar um medicamento já utilizado em vez de reescrever seu histórico.",
        }
        widgets = {
            "code": forms.TextInput(attrs={"class": "input", "autocomplete": "off"}),
            "name": forms.TextInput(attrs={"class": "input", "autocomplete": "off"}),
            "presentation": forms.TextInput(attrs={"class": "input", "autocomplete": "off"}),
            "strength_text": forms.TextInput(attrs={"class": "input", "autocomplete": "off"}),
            "route_hint": forms.TextInput(attrs={"class": "input", "autocomplete": "off"}),
            "dispense_unit": forms.TextInput(attrs={"class": "input", "autocomplete": "off"}),
            "active": forms.CheckboxInput(),
        }


class MedicationRequestCreateForm(forms.Form):
    encounter = forms.ModelChoiceField(queryset=Encounter.objects.none(), label="Encontro")
    replaces = forms.UUIDField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["encounter"].label_from_instance = _encounter_label
        if actor and has_rx_permission(actor, PERM_PRESCRIBE):
            self.fields["encounter"].queryset = (
                Encounter.objects.select_related("patient")
                .filter(
                    status=Encounter.Status.OPEN,
                    patient__in=accessible_patients(actor),
                )
                .order_by("-started_at")
                .distinct()
            )


class MedicationRequestItemForm(forms.Form):
    drug = forms.ModelChoiceField(
        queryset=Drug.objects.filter(active=True).order_by("name", "presentation"),
        label="Medicamento",
    )
    dose = forms.DecimalField(min_value=0.0001, max_digits=12, decimal_places=4, label="Dose")
    dose_unit = forms.CharField(max_length=40, label="Unidade da dose")
    route = forms.CharField(max_length=80, label="Via")
    frequency = forms.CharField(max_length=120, label="Frequência")
    duration_value = forms.DecimalField(
        required=False,
        min_value=0.01,
        max_digits=10,
        decimal_places=2,
        label="Duração",
    )
    duration_unit = forms.CharField(required=False, max_length=40, label="Unidade da duração")
    instructions = forms.CharField(
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Instruções",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["drug"].label_from_instance = _drug_label

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("duration_value") is not None and not (
            cleaned.get("duration_unit") or ""
        ).strip():
            self.add_error("duration_unit", "Informe a unidade da duração.")
        return cleaned


MedicationRequestItemFormSet = formset_factory(
    MedicationRequestItemForm,
    extra=0,
    min_num=1,
    validate_min=True,
    max_num=50,
    validate_max=True,
)


class MedicationRequestSubmitForm(forms.Form):
    confirm = forms.BooleanField(label="Confirmo a submissão da prescrição")


class MedicationRequestValidateForm(forms.Form):
    manual_allergy_review_confirmed = forms.BooleanField(
        required=False,
        label=(
            "Revisei manualmente a situação de alergias devido à indisponibilidade "
            "da fonte estruturada"
        ),
    )
    confirm_validation = forms.BooleanField(label="Confirmo a validação farmacêutica")


class MedicationRequestCancelForm(forms.Form):
    reason = forms.CharField(
        max_length=255,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Motivo",
    )
    confirm = forms.BooleanField(label="Confirmo o cancelamento")


class MedicationDispenseHeaderForm(forms.Form):
    operation_key = forms.UUIDField(widget=forms.HiddenInput())
    confirm = forms.BooleanField(label="Confirmo a dispensação e a baixa de estoque")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.setdefault("operation_key", uuid.uuid4())


class MedicationDispenseItemForm(forms.Form):
    request_item = forms.ModelChoiceField(
        queryset=MedicationRequestItem.objects.none(),
        label="Item prescrito",
    )
    lot = forms.ModelChoiceField(queryset=Lot.objects.none(), label="Lote")
    quantity = forms.DecimalField(
        min_value=0.0001,
        max_digits=14,
        decimal_places=4,
        label="Quantidade",
    )

    def __init__(self, *args, medication_request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["request_item"].label_from_instance = _request_item_label
        self.fields["lot"].label_from_instance = _lot_label
        if medication_request is None:
            return
        self.fields["request_item"].queryset = medication_request.items.select_related("drug").order_by(
            "sequence"
        )
        drug_ids = medication_request.items.values_list("drug_id", flat=True)
        self.fields["lot"].queryset = (
            Lot.objects.select_related("stock_item", "stock_item__drug")
            .filter(
                stock_item__drug_id__in=drug_ids,
                stock_item__active=True,
                active=True,
                quantity_available__gt=0,
            )
            .order_by("expires_on", "lot_number")
        )


MedicationDispenseItemFormSet = formset_factory(
    MedicationDispenseItemForm,
    extra=0,
    min_num=1,
    validate_min=True,
    max_num=50,
    validate_max=True,
)
