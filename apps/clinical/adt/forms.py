import uuid

from django import forms
from django.utils import timezone

from .models import Bed
from .selectors import admissible_encounters_for_user, available_beds_for_user


class EncounterChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, encounter):
        patient = encounter.patient
        return f"{patient.full_name} — {encounter.get_encounter_type_display()} — {encounter.started_at:%d/%m/%Y %H:%M}"


class BedChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, bed):
        return f"{bed.location.name} — {bed.label} ({bed.code})"


class AdmissionForm(forms.Form):
    encounter = EncounterChoiceField(queryset=None, label="Encontro de internação")
    bed = BedChoiceField(queryset=None, label="Leito disponível")
    admitted_at = forms.DateTimeField(
        label="Data e hora da admissão",
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "input"},
            format="%Y-%m-%dT%H:%M",
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    operation_key = forms.UUIDField(widget=forms.HiddenInput())

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["encounter"].queryset = admissible_encounters_for_user(user)
        self.fields["bed"].queryset = available_beds_for_user(user)
        self.fields["encounter"].widget.attrs.update({"class": "select"})
        self.fields["bed"].widget.attrs.update({"class": "select"})
        if not self.is_bound:
            self.initial.setdefault(
                "admitted_at",
                timezone.localtime().replace(second=0, microsecond=0),
            )
            self.initial.setdefault("operation_key", uuid.uuid4())

    def clean_admitted_at(self):
        admitted_at = self.cleaned_data["admitted_at"]
        encounter = self.cleaned_data.get("encounter")
        if encounter and admitted_at < encounter.started_at:
            raise forms.ValidationError(
                "A admissão não pode ser anterior ao início do encontro."
            )
        return admitted_at
