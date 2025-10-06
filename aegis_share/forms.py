from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UsersInfos


class FirstUserForm(UserCreationForm):
    NIVEL_PERMISSAO_CHOICES = UsersInfos.NIVEL_PERMISSAO_CHOICES

    email = forms.EmailField(
        label="Email",
        max_length=300,
        required=True,
        widget=forms.EmailInput(
            attrs={"placeholder": "email@exemplo.com", "autocomplete": "email"}
        ),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "username", "email",
            "password1", "password2"
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            UsersInfos.objects.create(
                user=user,
                nivel_permissao='ADM'
            )
        return user


class CustomUserCreationForm(UserCreationForm):
    NIVEL_PERMISSAO_CHOICES = UsersInfos.NIVEL_PERMISSAO_CHOICES

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
            attrs={"placeholder": "999.999.999-99"}
        )
    )

    nivel_permissao = forms.ChoiceField(
        label="Nível de Permissão",
        choices=NIVEL_PERMISSAO_CHOICES,
        initial='CLI'
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "username", "email",
            "cpf", "nivel_permissao",
            "password1", "password2"
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            UsersInfos.objects.create(
                user=user,
                cpf=self.cleaned_data["cpf"],
                nivel_permissao=self.cleaned_data["nivel_permissao"]
            )
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

    cpf = forms.CharField(
        label="CPF",
        max_length=14,
        required=True,
        widget=forms.TextInput(
            attrs={"placeholder": "999.999.999-99"}
        )
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "username", "email",
            "cpf",
            "password1", "password2"
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            UsersInfos.objects.create(
                user=user,
                cpf=self.cleaned_data["cpf"],
                nivel_permissao='CLI'
            )
        return user


class FileInputIPFSForm(forms.Form):
    ...