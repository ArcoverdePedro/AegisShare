import uuid

from django import forms
from django.utils import timezone

from .models import LabTest


class OrderForm(forms.Form):
    lab_test = forms.ModelChoiceField(
        label="Exame",
        queryset=LabTest.objects.filter(active=True),
        empty_label="Selecione um exame",
        error_messages={"invalid_choice": "Selecione um exame disponível."},
    )
    operation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["lab_test"].label_from_instance = lambda test: (
            f"{test.code} · {test.name} · {test.specimen_type}"
        )
        # O serviço valida catálogo ativo para pedidos novos. Retry pode usar exame desativado.
        if self.is_bound:
            self.fields["lab_test"].queryset = LabTest.objects.all()


class SpecimenForm(forms.Form):
    accession_code = forms.CharField(
        label="Código da amostra",
        max_length=64,
        widget=forms.TextInput(attrs={"class": "input", "autocomplete": "off"}),
    )
    collected_at = forms.DateTimeField(
        label="Data e hora da coleta",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "input", "step": "1"}),
    )
    confirmed = forms.BooleanField(
        label="Confirme que conferiu o paciente, o pedido e a identificação da amostra"
    )
    operation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)

    def __init__(self, *args, order, **kwargs):
        super().__init__(*args, **kwargs)
        self.order = order

    def clean_collected_at(self):
        value = self.cleaned_data["collected_at"]
        if value < self.order.requested_at or value > timezone.now():
            raise forms.ValidationError("Informe uma coleta entre o pedido e o momento atual.")
        return value


class OrderFilterForm(forms.Form):
    status = forms.ChoiceField(
        label="Situação",
        required=False,
        choices=[
            ("", "Todos"),
            ("requested", "Solicitado"),
            ("collected", "Coleta registrada"),
        ],
    )
