import uuid

from django import forms

from .models import InventoryItem, Requisition, StockLocation


def material_label(item):
    return f"{item.code} · {item.name} · {item.unit}"


class RequisitionForm(forms.Form):
    item = forms.ModelChoiceField(
        label="Material não medicamentoso",
        queryset=InventoryItem.objects.filter(active=True),
        empty_label="Selecione um material",
        error_messages={"invalid_choice": "Selecione um material disponível."},
    )
    quantity = forms.IntegerField(label="Quantidade inteira", min_value=1, max_value=999999)
    operation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    confirmed = forms.BooleanField(
        label="Confirmo a requisição interna, sem reserva, compra ou entrega confirmada"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].label_from_instance = material_label
        # Retry pode usar identidade inativa; operação nova valida active sob lock.
        if self.is_bound:
            self.fields["item"].queryset = InventoryItem.objects.all()


class MovementForm(forms.Form):
    KIND_CHOICES = [
        ("RECEIPT", "Entrada"),
        ("ISSUE", "Saída/entrega"),
        ("RETURN", "Devolução ao estoque"),
        ("TRANSFER", "Transferência entre locais"),
        ("ADJUSTMENT", "Ajuste de inventário (quantidade contada)"),
    ]

    kind = forms.ChoiceField(label="Tipo de movimento", choices=KIND_CHOICES)
    item = forms.ModelChoiceField(
        label="Material",
        queryset=InventoryItem.objects.filter(active=True),
        error_messages={"invalid_choice": "Selecione um material disponível."},
    )
    location = forms.ModelChoiceField(
        label="Local", queryset=StockLocation.objects.filter(active=True)
    )
    to_location = forms.ModelChoiceField(
        label="Local de destino (transferência)",
        queryset=StockLocation.objects.filter(active=True),
        required=False,
    )
    lot = forms.CharField(label="Lote", max_length=120, required=False)
    expires_on = forms.DateField(
        label="Validade (entrada)", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    quantity = forms.IntegerField(
        label="Quantidade inteira (no ajuste, a quantidade contada)",
        min_value=0,
        max_value=999999,
    )
    requisition = forms.ModelChoiceField(
        label="Requisição atendida (saída/devolução)",
        queryset=Requisition.objects.all(),
        required=False,
        to_field_name="pk",
        widget=forms.TextInput,
    )
    reason = forms.CharField(label="Motivo", max_length=255, required=False)
    operation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    confirmed = forms.BooleanField(label="Confirmo a movimentação física do material")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].label_from_instance = material_label

    def clean_lot(self):
        return " ".join(self.cleaned_data["lot"].split())

    def clean(self):
        data = super().clean()
        kind = data.get("kind")
        if kind != "ADJUSTMENT" and data.get("quantity") == 0:
            self.add_error("quantity", "Informe quantidade maior que zero.")
        if kind == "TRANSFER" and (
            not data.get("to_location") or data.get("to_location") == data.get("location")
        ):
            self.add_error("to_location", "Informe um destino diferente da origem.")
        if kind != "TRANSFER":
            data["to_location"] = None
        if kind in {"ADJUSTMENT", "RETURN"} and not data.get("reason", "").strip():
            self.add_error("reason", "Informe o motivo.")
        if kind not in {"ISSUE", "RETURN"}:
            data["requisition"] = None
        requisition = data.get("requisition")
        if requisition and data.get("item") and requisition.item_id != data["item"].pk:
            self.add_error("requisition", "A requisição é de outro material.")
        if kind != "RECEIPT":
            data["expires_on"] = None
        return data


class ReversalForm(forms.Form):
    reason = forms.CharField(label="Motivo do estorno", max_length=255)
    operation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
