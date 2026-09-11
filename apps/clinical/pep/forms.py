from django import forms

from .models import Patient


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
