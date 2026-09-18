import uuid

from django import forms

from .models import ImagingExam


class ImagingOrderForm(forms.Form):
    exam = forms.ModelChoiceField(
        label="Exame de imagem",
        queryset=ImagingExam.objects.filter(active=True),
        empty_label="Selecione um exame",
        error_messages={"invalid_choice": "Selecione um exame disponível."},
    )
    operation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["exam"].label_from_instance = lambda test: f"{test.code} · {test.name}"
        # O serviço valida catálogo ativo para pedidos novos. Retry pode usar exame desativado.
        if self.is_bound:
            self.fields["exam"].queryset = ImagingExam.objects.all()
