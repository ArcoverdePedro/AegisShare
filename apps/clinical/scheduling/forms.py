import uuid
from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import AgendaSlot


def slot_label(slot):
    when = timezone.localtime(slot.starts_at).strftime("%d/%m %H:%M")
    return f"{when} · {slot.professional.get_full_name() or slot.professional.username} · {slot.location}"


class SlotBatchForm(forms.Form):
    professional = forms.ModelChoiceField(
        label="Profissional",
        queryset=get_user_model().objects.filter(
            is_active=True, nivel_permissao__in=["FUNC", "ADM"]
        ),
    )
    day = forms.DateField(label="Data", widget=forms.DateInput(attrs={"type": "date"}))
    start = forms.TimeField(label="Início", widget=forms.TimeInput(attrs={"type": "time"}))
    end = forms.TimeField(label="Fim", widget=forms.TimeInput(attrs={"type": "time"}))
    minutes = forms.IntegerField(label="Duração (min)", min_value=5, max_value=240, initial=20)
    capacity = forms.IntegerField(
        label="Pacientes por horário", min_value=1, max_value=20, initial=1
    )
    location = forms.CharField(label="Unidade/consultório", max_length=160)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["professional"].label_from_instance = lambda u: u.get_full_name() or u.username

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("end") and data["end"] <= data["start"]:
            self.add_error("end", "O fim deve ser posterior ao início.")
        if data.get("day") and data["day"] < timezone.localdate():
            self.add_error("day", "Não abra horários no passado.")
        return data


class BookingForm(forms.Form):
    slot = forms.ModelChoiceField(label="Horário", queryset=AgendaSlot.objects.none())
    overbook = forms.BooleanField(label="Encaixe acima da capacidade", required=False)
    reason = forms.CharField(label="Justificativa do encaixe", max_length=255, required=False)
    operation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        now = timezone.now()
        self.fields["slot"].queryset = AgendaSlot.objects.filter(
            starts_at__gt=now, starts_at__lte=now + timedelta(days=60), blocked_reason=""
        ).select_related("professional")
        self.fields["slot"].label_from_instance = slot_label


class ReasonForm(forms.Form):
    reason = forms.CharField(label="Motivo", max_length=255)
