from django import forms
from django.utils import timezone

from .models import ClinicalEvolution, Encounter, Patient


class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = [
            "identifier_type",
            "identifier",
            "full_name",
            "birth_date",
            "sex",
            "phone",
            "email",
        ]
        widgets = {
            "identifier_type": forms.Select(attrs={"class": "select"}),
            "identifier": forms.TextInput(
                attrs={"class": "input", "autocomplete": "off", "maxlength": "64"}
            ),
            "full_name": forms.TextInput(
                attrs={"class": "input", "autocomplete": "name", "maxlength": "255"}
            ),
            "birth_date": forms.DateInput(attrs={"class": "input", "type": "date"}),
            "sex": forms.Select(attrs={"class": "select"}),
            "phone": forms.TextInput(
                attrs={"class": "input", "autocomplete": "tel", "maxlength": "32"}
            ),
            "email": forms.EmailInput(attrs={"class": "input", "autocomplete": "email"}),
        }
        labels = {
            "identifier_type": "Tipo de identificador",
            "identifier": "CPF ou identificador",
            "full_name": "Nome completo",
            "birth_date": "Data de nascimento",
            "sex": "Sexo",
            "phone": "Telefone",
            "email": "E-mail",
        }


class EncounterForm(forms.ModelForm):
    class Meta:
        model = Encounter
        fields = ["encounter_type", "started_at", "location", "reason"]
        widgets = {
            "encounter_type": forms.Select(attrs={"class": "select"}),
            "started_at": forms.DateTimeInput(
                attrs={"class": "input", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "location": forms.TextInput(
                attrs={"class": "input", "maxlength": "160", "autocomplete": "off"}
            ),
            "reason": forms.Textarea(
                attrs={"class": "textarea", "rows": "4", "maxlength": "2000"}
            ),
        }
        labels = {
            "encounter_type": "Tipo de encontro",
            "started_at": "Início do atendimento",
            "location": "Local",
            "reason": "Motivo do atendimento",
        }
        help_texts = {
            "reason": "Registre apenas o contexto necessário para identificar o encontro.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["started_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        if not self.is_bound and self.instance._state.adding:
            self.fields["started_at"].initial = timezone.localtime().replace(
                second=0,
                microsecond=0,
            )


class ClinicalEvolutionForm(forms.ModelForm):
    class Meta:
        model = ClinicalEvolution
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "textarea",
                    "rows": "10",
                    "autocomplete": "off",
                    "spellcheck": "true",
                }
            )
        }
        labels = {"content": "Evolução clínica"}
        help_texts = {
            "content": (
                "Após salvar, o conteúdo não poderá ser alterado. Correções devem ser "
                "registradas como adendo."
            )
        }


class ClinicalEvolutionAmendmentForm(forms.ModelForm):
    class Meta:
        model = ClinicalEvolution
        fields = ["amendment_reason", "content"]
        widgets = {
            "amendment_reason": forms.TextInput(
                attrs={"class": "input", "maxlength": "255", "autocomplete": "off"}
            ),
            "content": forms.Textarea(
                attrs={
                    "class": "textarea",
                    "rows": "10",
                    "autocomplete": "off",
                    "spellcheck": "true",
                }
            ),
        }
        labels = {
            "amendment_reason": "Motivo do adendo",
            "content": "Conteúdo do adendo",
        }
