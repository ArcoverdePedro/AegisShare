import uuid

from django import forms

from .models import InventoryItem


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
