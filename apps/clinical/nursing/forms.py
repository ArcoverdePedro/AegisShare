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
