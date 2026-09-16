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
