import uuid
from decimal import Decimal

from django import forms


class AccountOpenForm(forms.Form):
    operation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    confirmed = forms.BooleanField(
        label="Confirmo a abertura em preparação, sem emissão de cobrança"
    )


class BillingItemForm(forms.Form):
    description = forms.CharField(
        label="Descrição administrativa",
        max_length=200,
        help_text="Não inclua identificação de paciente ou justificativa clínica.",
    )
    quantity = forms.IntegerField(label="Quantidade inteira", min_value=1, max_value=999999)
    unit_price = forms.DecimalField(
        label="Valor unitário (BRL)",
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("9999999999.99"),
        localize=False,
        help_text="Use ponto como separador decimal, por exemplo 12.50; sem símbolo ou separador de milhares.",
    )
    operation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    confirmed = forms.BooleanField(
        label="Confirme os dados manuais; este lançamento não emite cobrança"
    )
