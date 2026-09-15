import uuid

from django import forms
from django.utils import timezone

from .models import VitalSignsRecord


class VitalSignsRecordForm(forms.ModelForm):
    recorded_at = forms.DateTimeField(
        label="Momento da aferição",
        input_formats=["%Y-%m-%dT%H:%M:%S"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M:%S",
            attrs={"class": "input", "type": "datetime-local", "step": "1"},
        ),
    )

    class Meta:
        model = VitalSignsRecord
        fields = [
            "recorded_at",
            "temperature_c",
            "heart_rate_bpm",
            "respiratory_rate_irpm",
            "systolic_bp_mmhg",
            "diastolic_bp_mmhg",
            "oxygen_saturation_pct",
            "weight_kg",
        ]
        labels = {
            "temperature_c": "Temperatura (°C)",
            "heart_rate_bpm": "Frequência cardíaca (bpm)",
            "respiratory_rate_irpm": "Frequência respiratória (irpm)",
            "systolic_bp_mmhg": "Pressão sistólica (mmHg)",
            "diastolic_bp_mmhg": "Pressão diastólica (mmHg)",
            "oxygen_saturation_pct": "Saturação de oxigênio (%)",
            "weight_kg": "Peso (kg)",
        }
        help_texts = {
            "weight_kg": (
                "O peso é registrado como fato clínico. O RX não o usa automaticamente "
                "até aprovação da política institucional de origem/atualidade."
            ),
        }
        widgets = {
            "temperature_c": forms.NumberInput(attrs={"class": "input", "step": "0.01"}),
            "heart_rate_bpm": forms.NumberInput(attrs={"class": "input", "step": "1"}),
            "respiratory_rate_irpm": forms.NumberInput(attrs={"class": "input", "step": "1"}),
            "systolic_bp_mmhg": forms.NumberInput(attrs={"class": "input", "step": "1"}),
            "diastolic_bp_mmhg": forms.NumberInput(attrs={"class": "input", "step": "1"}),
            "oxygen_saturation_pct": forms.NumberInput(
                attrs={"class": "input", "step": "0.01"}
            ),
            "weight_kg": forms.NumberInput(attrs={"class": "input", "step": "0.001"}),
        }

    def __init__(self, *args, encounter=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.encounter = encounter
        if not self.is_bound:
            self.initial.setdefault(
                "recorded_at",
                timezone.localtime().replace(microsecond=0),
            )

    def clean(self):
        cleaned = super().clean()
        measures = (
            "temperature_c",
            "heart_rate_bpm",
            "respiratory_rate_irpm",
            "systolic_bp_mmhg",
            "diastolic_bp_mmhg",
            "oxygen_saturation_pct",
            "weight_kg",
        )
        if not any(cleaned.get(name) is not None for name in measures):
            raise forms.ValidationError("Informe ao menos uma medida clínica.")

        recorded_at = cleaned.get("recorded_at")
        if recorded_at is None:
            return cleaned
        if recorded_at > timezone.now():
            self.add_error("recorded_at", "O momento da aferição não pode estar no futuro.")
        if self.encounter is not None:
            if recorded_at < self.encounter.started_at:
                self.add_error(
                    "recorded_at",
                    "O momento da aferição não pode ser anterior ao início do encontro.",
                )
            if self.encounter.ended_at and recorded_at > self.encounter.ended_at:
                self.add_error(
                    "recorded_at",
                    "O momento da aferição não pode ser posterior ao encerramento do encontro.",
                )
        return cleaned


class MedicationAdministrationForm(forms.Form):
    operation_key = forms.UUIDField(widget=forms.HiddenInput())
    administered_at = forms.DateTimeField(
        label="Momento da administração",
        input_formats=["%Y-%m-%dT%H:%M:%S"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M:%S",
            attrs={"class": "input", "type": "datetime-local", "step": "1"},
        ),
    )
    administered_dose = forms.DecimalField(
        label="Dose efetivamente administrada",
        max_digits=12,
        decimal_places=4,
        min_value=0.0001,
        widget=forms.NumberInput(attrs={"class": "input", "step": "0.0001"}),
    )
    administered_dose_unit = forms.CharField(
        label="Unidade da dose administrada",
        max_length=40,
        widget=forms.TextInput(attrs={"class": "input", "autocomplete": "off"}),
    )

    def __init__(self, *args, dispense_item=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.dispense_item = dispense_item
        if not self.is_bound:
            self.initial.setdefault("operation_key", uuid.uuid4())
            self.initial.setdefault(
                "administered_at",
                timezone.localtime().replace(microsecond=0),
            )

    def clean_administered_dose_unit(self):
        value = " ".join((self.cleaned_data.get("administered_dose_unit") or "").split())
        if not value:
            raise forms.ValidationError("Informe a unidade da dose administrada.")
        return value

    def clean(self):
        cleaned = super().clean()
        administered_at = cleaned.get("administered_at")
        if administered_at is None:
            return cleaned

        if administered_at > timezone.now():
            self.add_error(
                "administered_at",
                "O momento da administração não pode estar no futuro.",
            )
        if self.dispense_item is not None:
            encounter = self.dispense_item.dispense.medication_request.encounter
            encounter_started_at = encounter.started_at.replace(microsecond=0)
            dispensed_at = self.dispense_item.dispense.dispensed_at.replace(microsecond=0)
            if administered_at < encounter_started_at:
                self.add_error(
                    "administered_at",
                    "O momento da administração não pode ser anterior ao início do encontro.",
                )
            if administered_at < dispensed_at:
                self.add_error(
                    "administered_at",
                    "O momento da administração não pode ser anterior à dispensação.",
                )
        return cleaned
