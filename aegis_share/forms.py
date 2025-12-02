from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import CustomUser
from .utils import clear_strings


class FirstUserForm(UserCreationForm):
    email = forms.EmailField(
        label="Email",
        max_length=300,
        required=True,
        widget=forms.EmailInput(
            attrs={"placeholder": "email@exemplo.com", "autocomplete": "email"}
        ),
    )

    telefone = forms.CharField(
        label="Telefone",
        max_length=15,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "tel",
                "placeholder": "(99) 99999-9999",
            }
        ),
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = (
            "first_name",
            "last_name",
            "username",
            "email",
            "telefone",
            "password1",
            "password2",
        )

    def clean_telefone(self):
        telefone_formatado = self.cleaned_data.get("telefone")
        telefone_limpo = clear_strings(telefone_formatado)

        if not (10 <= len(telefone_limpo) <= 11):
            raise forms.ValidationError("Telefone inválido (DDD + 8 ou 9 dígitos).")

        return telefone_limpo

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.telefone = self.cleaned_data["telefone"]
        user.is_staff = True
        user.is_superuser = True
        user.nivel_permissao = "ADM"
        if commit:
            user.save()
        return user


class FormUserADM(UserCreationForm):

    email = forms.EmailField(
        label="Email",
        max_length=300,
        required=True,
        widget=forms.EmailInput(
            attrs={"placeholder": "email@exemplo.com", "autocomplete": "email"}
        ),
    )

    telefone = forms.CharField(
        label="Telefone",
        max_length=15,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "tel",
                "placeholder": "(99) 99999-9999",
            }
        ),
    )

    nivel_permissao = forms.ChoiceField(
        label="Nível de Permissão",
        choices=CustomUser.NIVEL_PERMISSAO_CHOICES,
        initial="CLI",
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = (
            "first_name",
            "last_name",
            "username",
            "email",
            "telefone",
            "nivel_permissao",
            "password1",
            "password2",
        )

    def clean_telefone(self):
        telefone_formatado = self.cleaned_data.get("telefone")
        telefone_limpo = clear_strings(telefone_formatado)

        if not (10 <= len(telefone_limpo) <= 11):
            raise forms.ValidationError("Telefone inválido (DDD + 8 ou 9 dígitos).")

        return telefone_formatado

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.telefone = self.cleaned_data["telefone"]
        user.nivel_permissao = self.cleaned_data["nivel_permissao"]
        if self.cleaned_data["nivel_permissao"] == "ADM":
            user.is_staff = True
            user.is_superuser = True
        if commit:
            user.save()
        return user


class ClienteForm(UserCreationForm):

    email = forms.EmailField(
        label="Email",
        max_length=300,
        required=True,
        widget=forms.EmailInput(
            attrs={"placeholder": "email@exemplo.com", "autocomplete": "email"}
        ),
    )

    telefone = forms.CharField(
        label="Telefone",
        max_length=15,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "tel",
                "placeholder": "(99) 99999-9999",
            }
        ),
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = (
            "first_name",
            "last_name",
            "username",
            "email",
            "telefone",
            "nivel_permissao",
            "password1",
            "password2",
        )

    def clean_telefone(self):
        telefone_formatado = self.cleaned_data.get("telefone")
        telefone_limpo = clear_strings(telefone_formatado)

        if not (10 <= len(telefone_limpo) <= 11):
            raise forms.ValidationError("Telefone inválido (DDD + 8 ou 9 dígitos).")

        return telefone_formatado

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.telefone = self.cleaned_data["telefone"]
        user.nivel_permissao = "CLI"
        if commit:
            user.save()
        return user


class IPFSForm(forms.Form):
    cliente = forms.CharField(
        label="Buscar cliente",
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Buscar Cliente",
                "id": "cliente_input",
                "class": "input",
            }
        ),
        error_messages={"required": "Campo Cliente é obrigatório."},
    )

    cliente_id = forms.CharField(
        required=True,
        widget=forms.HiddenInput(attrs={"id": "cliente_id"}),
        error_messages={"required": "Cliente inválido ou não selecionado."},
    )

    arquivo = forms.FileField(
        label="Selecione o arquivo",
        required=True,
        widget=forms.FileInput(attrs={"id": "id_arquivo", "class": "file-input"}),
        error_messages={"required": "Campo Arquivo é obrigatório."},
    )

    def clean_cliente_id(self):
        from uuid import UUID

        cliente_id = self.cleaned_data.get("cliente_id")

        if not cliente_id:
            raise forms.ValidationError("Cliente não selecionado.")

        try:
            UUID(cliente_id)
        except:
            raise forms.ValidationError("Identificador de cliente inválido.")

        if not CustomUser.objects.filter(id=cliente_id).exists():
            raise forms.ValidationError("Cliente inexistente.")

        return cliente_id

    def clean_arquivo(self):
        arquivo = self.cleaned_data.get("arquivo")

        if arquivo:
            max_size = 10 * 1024 * 1024
            if arquivo.size > max_size:
                raise forms.ValidationError("O arquivo excede o limite de 10MB.")

            allowed_types = ["application/pdf", "image/png","image/jpeg","image/jpg","image/webp"]
            if arquivo.content_type not in allowed_types:
                raise forms.ValidationError(
                    "Tipo de arquivo não permitido. Apenas PDF ou Imagens são aceitos."
                )

        return arquivo


class FotoForm(forms.Form):
    arquivo = forms.FileField(
        label="Selecione a Foto",
        required=True,
        widget=forms.FileInput(attrs={"id": "id_foto", "class": "file-input"}),
    )

    def clean_arquivo(self):
        arquivo = self.cleaned_data.get("arquivo")

        if arquivo:
            max_size = 10 * 1024 * 1024
            if arquivo.size > max_size:
                raise forms.ValidationError("O arquivo excede o limite de 10MB.")
            
            allowed_types = ["image/png","image/jpeg","image/jpg","image/webp"]
            if arquivo.content_type not in allowed_types:
                raise forms.ValidationError(
                    "Tipo de arquivo não permitido. Apenas Imagens são aceitas."
                )

        return arquivo
