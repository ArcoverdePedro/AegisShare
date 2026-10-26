import uuid
from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model

from .models import OperatingRoom, Procedure


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


class ScheduleForm(forms.Form):
    room = forms.ModelChoiceField(label="Sala", queryset=OperatingRoom.objects.filter(active=True))
    surgeon = forms.ModelChoiceField(
        label="Cirurgião responsável",
        queryset=get_user_model().objects.filter(
            is_active=True, nivel_permissao__in=["FUNC", "ADM"]
        ),
    )
    starts_at = forms.DateTimeField(
        label="Início", widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )
    minutes = forms.IntegerField(label="Duração prevista (min)", min_value=15, max_value=1440)
    operation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["surgeon"].label_from_instance = lambda u: u.get_full_name() or u.username

    def clean(self):
        data = super().clean()
        if data.get("starts_at") and data.get("minutes"):
            data["ends_at"] = data["starts_at"] + timedelta(minutes=data.pop("minutes"))
        return data
