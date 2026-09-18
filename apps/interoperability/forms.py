from django import forms

from apps.clinical.pep.models import Patient
from apps.clinical.pep.permissions import accessible_patients


class PatientExportForm(forms.Form):
    patient = forms.ModelChoiceField(
        label="Paciente",
        empty_label="Selecione um paciente",
        queryset=Patient.objects.none(),
        error_messages={"invalid_choice": "Selecione um paciente disponível."},
    )
    confirm = forms.BooleanField(
        label="Confirmo a exportação dos dados selecionados",
        error_messages={"required": "Confirme a exportação dos dados selecionados."},
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["patient"].queryset = accessible_patients(user)
        self.fields["patient"].label_from_instance = lambda patient: (
            f"{patient.full_name} · {patient.pk}"
        )


class LaboratoryInboxForm(forms.Form):
    source = forms.ModelChoiceField(
        label="Origem", queryset=None, empty_label="Selecione uma origem"
    )
    file = forms.FileField(label="Arquivo para quarentena")
    confirmed = forms.BooleanField(
        label="Confirmo o depósito em quarentena; este arquivo não será interpretado nem liberado como resultado"
    )

    def __init__(self, *args, user, **kwargs):
        from .lab_inbox import accessible_sources

        super().__init__(*args, **kwargs)
        self.fields["source"].queryset = accessible_sources(user).filter(active=True)
        self.fields["source"].label_from_instance = lambda source: source.code
        self.fields["source"].error_messages["invalid_choice"] = "Selecione uma origem disponível."


class LaboratoryInboxFilterForm(forms.Form):
    source = forms.ModelChoiceField(
        label="Origem", queryset=None, required=False, empty_label="Todas"
    )

    def __init__(self, *args, user, **kwargs):
        from .lab_inbox import accessible_sources

        super().__init__(*args, **kwargs)
        self.fields["source"].queryset = accessible_sources(user)
        self.fields["source"].label_from_instance = lambda source: source.code
