from django import forms

from .models import Drug


class DrugForm(forms.ModelForm):
    class Meta:
        model = Drug
        fields = [
            "code",
            "name",
            "presentation",
            "strength_text",
            "route_hint",
            "dispense_unit",
            "active",
        ]
        labels = {
            "code": "Código interno",
            "name": "Medicamento",
            "presentation": "Apresentação",
            "strength_text": "Concentração / força",
            "route_hint": "Via sugerida (informativa)",
            "dispense_unit": "Unidade de dispensação",
            "active": "Ativo para novas prescrições",
        }
        help_texts = {
            "route_hint": "Campo informativo; não seleciona via automaticamente na prescrição.",
            "active": "Prefira desativar um medicamento já utilizado em vez de reescrever seu histórico.",
        }
        widgets = {
            "code": forms.TextInput(attrs={"class": "input", "autocomplete": "off"}),
            "name": forms.TextInput(attrs={"class": "input", "autocomplete": "off"}),
            "presentation": forms.TextInput(attrs={"class": "input", "autocomplete": "off"}),
            "strength_text": forms.TextInput(attrs={"class": "input", "autocomplete": "off"}),
            "route_hint": forms.TextInput(attrs={"class": "input", "autocomplete": "off"}),
            "dispense_unit": forms.TextInput(attrs={"class": "input", "autocomplete": "off"}),
            "active": forms.CheckboxInput(),
        }
