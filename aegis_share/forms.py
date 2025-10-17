from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, IPFSFile
from crispy_bulma.widgets import FileUploadInput


class FirstUserForm(UserCreationForm):
    """Form para criar o primeiro usuário (superusuário)."""

    email = forms.EmailField(
        label="Email",
        max_length=300,
        required=True,
        widget=forms.EmailInput(
            attrs={"placeholder": "email@exemplo.com", "autocomplete": "email"}
        ),
    )

    cpf = forms.CharField(
        label="CPF",
        max_length=14,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "cpf input",
                "placeholder": "999.999.999-99",
            }
        ),
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("username", "email", "cpf", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.cpf = self.cleaned_data["cpf"]
        user.is_staff = True
        user.is_superuser = True
        user.nivel_permissao = "ADM"
        if commit:
            user.save()
        return user


class FormUserADM(UserCreationForm):
    """Form para administradores criarem novos usuários."""

    email = forms.EmailField(
        label="Email",
        max_length=300,
        required=True,
        widget=forms.EmailInput(
            attrs={"placeholder": "email@exemplo.com", "autocomplete": "email"}
        ),
    )

    cpf = forms.CharField(
        label="CPF",
        max_length=14,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "cpf input",
                "placeholder": "999.999.999-99",
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
            "username",
            "email",
            "cpf",
            "nivel_permissao",
            "password1",
            "password2",
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.cpf = self.cleaned_data["cpf"]
        user.nivel_permissao = self.cleaned_data["nivel_permissao"]
        if self.cleaned_data["nivel_permissao"] == "ADM":
            user.is_staff = True
            user.is_superuser = True
        if commit:
            user.save()
        return user


class ClienteForm(UserCreationForm):
    """Form para cadastro de clientes comuns."""

    email = forms.EmailField(
        label="Email",
        max_length=300,
        required=True,
        widget=forms.EmailInput(
            attrs={"placeholder": "email@exemplo.com", "autocomplete": "email"}
        ),
    )

    cpf = forms.CharField(
        label="CPF",
        max_length=14,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "cpf input",
                "placeholder": "999.999.999-99",
            }
        ),
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("username", "email", "cpf", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.cpf = self.cleaned_data["cpf"]
        user.nivel_permissao = "CLI"
        if commit:
            user.save()
        return user


class IPFSForm(forms.Form):
    cliente = forms.CharField(
        label="Buscar cliente (nome ou CPF)",
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Digite o nome ou CPF do cliente",
                "id": "cliente_input",
                "class": "input is-rounded"
            }
        ),
    )
    
    arquivo = forms.FileField(
        label="Selecione o arquivo",
        required=False,
        widget=FileUploadInput(attrs={'id': 'id_arquivo'})
    )

    def clean_arquivo(self):
        arquivo = self.cleaned_data.get("arquivo")
        
        if not arquivo:
            raise forms.ValidationError("Este campo é obrigatório.")

        max_size = 10 * 1024 * 1024  # 10MB
        if arquivo.size > max_size:
            raise forms.ValidationError("O arquivo excede o limite de 10MB.")

        allowed_types = ["application/pdf", "image/png", "image/jpeg"]
        if arquivo.content_type not in allowed_types:
            raise forms.ValidationError("Tipo de arquivo não permitido. Apenas PDF, PNG e JPEG são aceitos.")

        return arquivo