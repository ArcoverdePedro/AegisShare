import uuid

from django import forms

from .models import Procedure


class SurgicalCaseForm(forms.Form):
    procedure = forms.ModelChoiceField(
        label="Procedimento",
        queryset=Procedure.objects.filter(active=True),
        empty_label="Selecione um procedimento",
        error_messages={"invalid_choice": "Selecione um procedimento disponível."},
    )
    operation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["procedure"].label_from_instance = lambda procedure: (
            f"{procedure.code} · {procedure.name}"
        )
        # O serviço valida catálogo ativo para solicitações novas. Retry pode usar procedimento desativado.
        if self.is_bound:
            self.fields["procedure"].queryset = Procedure.objects.all()
