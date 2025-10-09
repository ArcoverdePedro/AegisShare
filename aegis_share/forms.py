from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, IPFSFile


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

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("username", "email", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
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
        widget=forms.TextInput(attrs={"placeholder": "999.999.999-99"}),
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
        widget=forms.TextInput(attrs={"placeholder": "999.999.999-99"}),
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


class FileInputIPFSForm(forms.ModelForm):
    """Form para upload ou registro de arquivos IPFS."""

    class Meta:
        model = IPFSFile
        fields = ["cid", "nome_arquivo", "tamanho_arquivo"]
