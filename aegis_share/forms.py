from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

# Obtém o modelo de usuário ativo (geralmente o padrão do Django)
User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    # O email field precisa ser definido aqui, mas sem a classe CSS
    email = forms.EmailField(
        label='Email',
        max_length=300,
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'seu.email@exemplo.com',
                                       'autocomplete': 'email'})
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'password1', 'password2')
