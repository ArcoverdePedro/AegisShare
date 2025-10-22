from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, IPFSFile
from uuid import UUID
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
                "class": "cpf",
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
                "class": "cpf",
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
        label="Buscar cliente",
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Buscar Cliente",
                "id": "cliente_input",
                "class": "input"
            }
        ),
        error_messages={
            'required': 'Campo Cliente é obrigatório.'
        }
    )
    
    cliente_id = forms.CharField(
        required=True,
        widget=forms.HiddenInput(attrs={"id": "cliente_id"}),
        error_messages={'required': 'Cliente inválido ou não selecionado.'}
    )

    arquivo = forms.FileField(
        label="Selecione o arquivo",
        required=True,
        widget=forms.FileInput(attrs={
            'id': 'id_arquivo',
            'class': 'file-input'
        }),
        error_messages={
            'required': 'Campo Arquivo é obrigatório.'
        }
    )

    def clean_cliente_id(self):
        from uuid import UUID
        cliente_id = self.cleaned_data.get("cliente_id")

        if not cliente_id:
            raise forms.ValidationError("Cliente não selecionado.")

        try:
            UUID(cliente_id)
        except ValueError:
            raise forms.ValidationError("Identificador de cliente inválido.")

        if not CustomUser.objects.filter(id=cliente_id).exists():
            raise forms.ValidationError("Cliente inexistente.")

        return cliente_id
    
    def clean_arquivo(self):
        arquivo = self.cleaned_data.get("arquivo")
        
        if arquivo:
            max_size = 10 * 1024 * 1024  # 10MB
            if arquivo.size > max_size:
                raise forms.ValidationError("O arquivo excede o limite de 10MB.")
            
            allowed_types = ["application/pdf", "image/png", "image/jpeg"]
            if arquivo.content_type not in allowed_types:
                raise forms.ValidationError("Tipo de arquivo não permitido. Apenas PDF, PNG e JPEG são aceitos.")
        
        return arquivo
