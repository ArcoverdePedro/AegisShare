import uuid

from django import forms
from django.utils import timezone

from apps.clinical.pep.models import Encounter

from .models import Admission, Bed, Discharge
from .selectors import (
    admissible_encounters_for_user,
    available_beds_for_user,
    dischargeable_admissions_for_user,
    transferable_admissions_for_user,
)


class EncounterChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, encounter):
        patient = encounter.patient
        return (
            f"{patient.full_name} — {encounter.get_encounter_type_display()} — "
            f"{encounter.started_at:%d/%m/%Y %H:%M}"
        )


class BedChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, bed):
        return f"{bed.location.name} — {bed.label} ({bed.code})"


class AdmissionChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, admission):
        patient = admission.encounter.patient
        return f"{patient.full_name} — admissão {admission.admitted_at:%d/%m/%Y %H:%M}"


class AdmissionForm(forms.Form):
    encounter = EncounterChoiceField(
        queryset=Encounter.objects.none(),
        label="Encontro de internação",
    )
    bed = BedChoiceField(queryset=Bed.objects.none(), label="Leito disponível")
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


class TransferForm(forms.Form):
    admission = AdmissionChoiceField(
        queryset=Admission.objects.none(),
        label="Internação ativa",
    )
    destination_bed = BedChoiceField(
        queryset=Bed.objects.none(),
        label="Leito de destino",
    )
    transferred_at = forms.DateTimeField(
        label="Data e hora da transferência",
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "input"},
            format="%Y-%m-%dT%H:%M",
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    reason = forms.CharField(
        label="Motivo",
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"class": "input", "autocomplete": "off"}),
    )
    operation_key = forms.UUIDField(widget=forms.HiddenInput())

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["admission"].queryset = transferable_admissions_for_user(user)
        self.fields["destination_bed"].queryset = available_beds_for_user(user)
        self.fields["admission"].widget.attrs.update({"class": "select"})
        self.fields["destination_bed"].widget.attrs.update({"class": "select"})
        if not self.is_bound:
            self.initial.setdefault(
                "transferred_at",
                timezone.localtime().replace(second=0, microsecond=0),
            )
            self.initial.setdefault("operation_key", uuid.uuid4())

    def clean(self):
        cleaned = super().clean()
        admission = cleaned.get("admission")
        destination = cleaned.get("destination_bed")
        transferred_at = cleaned.get("transferred_at")
        if not admission:
            return cleaned
        current = admission.occupancies.filter(ended_at__isnull=True).first()
        if not current:
            raise forms.ValidationError("A internação não possui ocupação ativa.")
        if destination and destination.pk == current.bed_id:
            self.add_error("destination_bed", "Selecione um leito diferente do atual.")
        if transferred_at and transferred_at < current.started_at:
            self.add_error(
                "transferred_at",
                "A transferência não pode anteceder o início da ocupação atual.",
            )
        return cleaned


class DischargeForm(forms.Form):
    admission = AdmissionChoiceField(
        queryset=Admission.objects.none(),
        label="Internação ativa",
    )
    discharged_at = forms.DateTimeField(
        label="Data e hora da alta",
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "input"},
            format="%Y-%m-%dT%H:%M",
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    disposition = forms.ChoiceField(
        label="Destino da alta",
        choices=Discharge.Disposition.choices,
        widget=forms.Select(attrs={"class": "select"}),
    )
    reason = forms.CharField(
        label="Observação da alta",
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"class": "input", "autocomplete": "off"}),
    )
    operation_key = forms.UUIDField(widget=forms.HiddenInput())

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["admission"].queryset = dischargeable_admissions_for_user(user)
        self.fields["admission"].widget.attrs.update({"class": "select"})
        if not self.is_bound:
            self.initial.setdefault(
                "discharged_at",
                timezone.localtime().replace(second=0, microsecond=0),
            )
            self.initial.setdefault("operation_key", uuid.uuid4())

    def clean(self):
        cleaned = super().clean()
        admission = cleaned.get("admission")
        discharged_at = cleaned.get("discharged_at")
        if not admission or not discharged_at:
            return cleaned
        current = admission.occupancies.filter(ended_at__isnull=True).first()
        if not current:
            raise forms.ValidationError("A internação não possui ocupação ativa.")
        if discharged_at < admission.admitted_at or discharged_at < current.started_at:
            self.add_error(
                "discharged_at",
                "A alta não pode anteceder a admissão ou a ocupação atual.",
            )
        return cleaned
