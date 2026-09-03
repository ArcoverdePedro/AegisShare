from uuid import UUID

from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm

from .models import CustomUser, Folder, Workspace
from .utils import clear_strings


SAFE_FILE_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "text/plain",
    "text/csv",
    "application/zip",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/msword",
    "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
    "audio/mpeg",
    "audio/ogg",
    "video/mp4",
    "video/webm",
}


def validate_business_file(arquivo):
    if not arquivo:
        return arquivo
    max_size = settings.FILE_MAX_UPLOAD_MB * 1024 * 1024
    if arquivo.size > max_size:
        raise forms.ValidationError(
            f"O arquivo excede o limite de {settings.FILE_MAX_UPLOAD_MB} MB."
        )
    if arquivo.content_type not in SAFE_FILE_TYPES:
        raise forms.ValidationError(
            "Tipo de arquivo nao permitido. Envie documentos, imagens, ZIP, audio ou video suportados."
        )
    return arquivo


class PhoneUserCreationMixin:
    def clean_telefone(self):
        telefone = clear_strings(self.cleaned_data.get("telefone"))
        if not (10 <= len(telefone) <= 11):
            raise forms.ValidationError("Telefone invalido (DDD + 8 ou 9 digitos).")
        return telefone


class FirstUserForm(PhoneUserCreationMixin, UserCreationForm):
    email = forms.EmailField(label="Email", max_length=300, required=True)
    telefone = forms.CharField(label="Telefone", max_length=15, required=True, widget=forms.TextInput(attrs={"class": "tel"}))

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("first_name", "last_name", "username", "email", "telefone", "password1", "password2")

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


class FormUserADM(PhoneUserCreationMixin, UserCreationForm):
    email = forms.EmailField(label="Email", max_length=300, required=True)
    telefone = forms.CharField(label="Telefone", max_length=15, required=True, widget=forms.TextInput(attrs={"class": "tel"}))
    nivel_permissao = forms.ChoiceField(
        label="Nivel de Permissao", choices=CustomUser.NIVEL_PERMISSAO_CHOICES, initial="CLI"
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = (
            "first_name", "last_name", "username", "email", "telefone",
            "nivel_permissao", "password1", "password2",
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.telefone = self.cleaned_data["telefone"]
        user.nivel_permissao = self.cleaned_data["nivel_permissao"]
        user.is_staff = user.nivel_permissao == "ADM"
        user.is_superuser = user.nivel_permissao == "ADM"
        if commit:
            user.save()
        return user


class ClienteForm(PhoneUserCreationMixin, UserCreationForm):
    email = forms.EmailField(label="Email", max_length=300, required=True)
    telefone = forms.CharField(label="Telefone", max_length=15, required=True, widget=forms.TextInput(attrs={"class": "tel"}))

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("first_name", "last_name", "username", "email", "telefone", "password1", "password2")

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
        widget=forms.TextInput(attrs={"placeholder": "Buscar Cliente", "id": "cliente_input", "class": "input"}),
    )
    cliente_id = forms.CharField(required=True, widget=forms.HiddenInput(attrs={"id": "cliente_id"}))
    arquivo = forms.FileField(
        label="Selecione o arquivo",
        required=True,
        widget=forms.FileInput(attrs={"id": "id_arquivo", "class": "file-input"}),
    )
    description = forms.CharField(label="Descricao", required=False, widget=forms.Textarea(attrs={"rows": 2}))
    workspace = forms.ModelChoiceField(queryset=Workspace.objects.none(), required=False)
    folder = forms.ModelChoiceField(queryset=Folder.objects.none(), required=False)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            if user.is_admin():
                self.fields["workspace"].queryset = Workspace.objects.all()
            else:
                self.fields["workspace"].queryset = Workspace.objects.filter(members=user)
        workspace_id = self.data.get("workspace") if self.is_bound else None
        if workspace_id:
            self.fields["folder"].queryset = Folder.objects.filter(workspace_id=workspace_id)

    def clean_cliente_id(self):
        cliente_id = self.cleaned_data.get("cliente_id")
        try:
            UUID(cliente_id)
        except Exception as exc:
            raise forms.ValidationError("Identificador de cliente invalido.") from exc
        if not CustomUser.objects.filter(id=cliente_id, nivel_permissao="CLI").exists():
            raise forms.ValidationError("Cliente inexistente.")
        return cliente_id

    def clean_arquivo(self):
        return validate_business_file(self.cleaned_data.get("arquivo"))

    def clean(self):
        cleaned = super().clean()
        workspace = cleaned.get("workspace")
        folder = cleaned.get("folder")
        if folder and (not workspace or folder.workspace_id != workspace.id):
            self.add_error("folder", "A pasta selecionada nao pertence ao workspace.")
        return cleaned


class VersionUploadForm(forms.Form):
    arquivo = forms.FileField(label="Nova versao")

    def clean_arquivo(self):
        return validate_business_file(self.cleaned_data.get("arquivo"))


class SharedLinkForm(forms.Form):
    EXPIRATION_CHOICES = [
        ("1", "1 hora"),
        ("24", "24 horas"),
        ("168", "7 dias"),
        ("720", "30 dias"),
        ("", "Sem expiracao"),
    ]
    expires_in_hours = forms.ChoiceField(label="Validade", choices=EXPIRATION_CHOICES, required=False, initial="24")
    password = forms.CharField(label="Senha opcional", required=False, widget=forms.PasswordInput(render_value=True))
    max_downloads = forms.IntegerField(label="Maximo de downloads", min_value=1, required=False)
    allow_preview = forms.BooleanField(label="Permitir visualizacao", required=False, initial=True)
    allow_download = forms.BooleanField(label="Permitir download", required=False, initial=True)


class FileCommentForm(forms.Form):
    content = forms.CharField(label="Comentario", max_length=4000, widget=forms.Textarea(attrs={"rows": 3}))


class DocumentRequestForm(forms.Form):
    title = forms.CharField(label="Titulo", max_length=180)
    recipient = forms.ModelChoiceField(
        label="Cliente", queryset=CustomUser.objects.filter(nivel_permissao="CLI").order_by("username")
    )
    due_at = forms.DateTimeField(
        label="Prazo", required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    description = forms.CharField(label="Descricao", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    items = forms.CharField(
        label="Documentos solicitados",
        help_text="Um documento por linha.",
        widget=forms.Textarea(attrs={"rows": 6, "placeholder": "RG\nCPF\nComprovante de residencia"}),
    )

    def clean_items(self):
        items = [line.strip() for line in self.cleaned_data["items"].splitlines() if line.strip()]
        if not items:
            raise forms.ValidationError("Informe ao menos um documento.")
        if len(items) > 50:
            raise forms.ValidationError("Limite de 50 itens por solicitacao.")
        return items


class TOTPCodeForm(forms.Form):
    code = forms.CharField(label="Codigo de autenticacao", min_length=6, max_length=20)


class APITokenForm(forms.Form):
    name = forms.CharField(label="Nome do token", max_length=100)
    expires_days = forms.IntegerField(label="Validade em dias", min_value=1, max_value=3650, required=False)


class WorkspaceForm(forms.Form):
    name = forms.CharField(label="Nome do workspace", max_length=150)
    cliente = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(nivel_permissao="CLI").order_by("username")
    )


class FolderForm(forms.Form):
    workspace = forms.ModelChoiceField(queryset=Workspace.objects.all())
    name = forms.CharField(max_length=150)
    parent = forms.ModelChoiceField(queryset=Folder.objects.all(), required=False)

    def clean(self):
        cleaned = super().clean()
        workspace = cleaned.get("workspace")
        parent = cleaned.get("parent")
        if parent and workspace and parent.workspace_id != workspace.id:
            self.add_error("parent", "A pasta pai deve pertencer ao mesmo workspace.")
        return cleaned


class FotoForm(forms.Form):
    arquivo = forms.FileField(label="Selecione a Foto", required=True)

    def clean_arquivo(self):
        arquivo = self.cleaned_data.get("arquivo")
        if arquivo and arquivo.size > 5 * 1024 * 1024:
            raise forms.ValidationError("A foto excede o limite de 5 MB.")
        if arquivo and arquivo.content_type not in {"image/png", "image/jpeg", "image/webp"}:
            raise forms.ValidationError("Use PNG, JPEG ou WEBP.")
        return arquivo
