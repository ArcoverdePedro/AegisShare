from django import forms

from apps.clinical.pep.permissions import accessible_patients

from .models import NEXT_STATUS, DataSubjectRequest

CONFLICT_MESSAGE = "Esta solicitação foi atualizada. Consulte o histórico antes de continuar."


class DataSubjectRequestForm(forms.ModelForm):
    class Meta:
        model = DataSubjectRequest
        fields = ["patient", "category", "summary"]
        labels = {
            "patient": "Paciente",
            "category": "Categoria",
            "summary": "Resumo da solicitação",
        }
        widgets = {"summary": forms.Textarea(attrs={"class": "textarea", "rows": 4})}
        error_messages = {"patient": {"invalid_choice": "Selecione um paciente disponível."}}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["patient"].queryset = accessible_patients(user)
        self.fields["patient"].empty_label = "Selecione um paciente"
        self.fields["patient"].label_from_instance = lambda patient: (
            f"{patient.full_name} · {patient.pk}"
        )


class RequestTransitionForm(forms.Form):
    expected_status = forms.ChoiceField(
        choices=DataSubjectRequest.Status.choices, widget=forms.HiddenInput
    )
    target_status = forms.ChoiceField(
        label="Próximo estado", choices=DataSubjectRequest.Status.choices
    )
    note = forms.CharField(
        label="Nota de atendimento",
        max_length=2000,
        required=False,
        widget=forms.Textarea(attrs={"class": "textarea", "rows": 4}),
    )

    def __init__(self, *args, current_status, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_status = current_status
        next_status = NEXT_STATUS.get(current_status)
        self.fields["expected_status"].initial = current_status
        self.fields["target_status"].choices = [
            (value, label)
            for value, label in DataSubjectRequest.Status.choices
            if value == next_status
        ]
        self.fields["target_status"].initial = next_status

    def clean(self):
        data = super().clean()
        if data.get("expected_status") and data["expected_status"] != self.current_status:
            raise forms.ValidationError(CONFLICT_MESSAGE, code="conflict")
        if data.get("target_status") == DataSubjectRequest.Status.CLOSED and not data.get("note"):
            self.add_error("note", "Registre uma nota de atendimento para encerrar a solicitação.")
        return data

    @property
    def is_conflict(self):
        return self.has_error("__all__", "conflict") or self.has_error(
            "target_status", "invalid_choice"
        )


class RequestFilterForm(forms.Form):
    status = forms.ChoiceField(
        label="Estado",
        required=False,
        choices=[("", "Todos os estados"), *DataSubjectRequest.Status.choices],
    )
