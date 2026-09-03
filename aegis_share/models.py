import uuid

from auditlog.registry import auditlog
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.utils import timezone


class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    NIVEL_PERMISSAO_CHOICES = [
        ("ADM", "Administrador"),
        ("FUNC", "Funcionário"),
        ("CLI", "Cliente"),
    ]

    foto_perfil = models.TextField(null=True, blank=True)
    telefone = models.CharField(max_length=16, null=True, blank=True)
    nivel_permissao = models.CharField(
        max_length=4,
        choices=NIVEL_PERMISSAO_CHOICES,
        default="CLI",
        verbose_name="Nível de Permissão",
    )

    def is_admin(self):
        return self.nivel_permissao == "ADM" or self.is_superuser

    def is_employee(self):
        return self.nivel_permissao == "FUNC"

    def is_client(self):
        return self.nivel_permissao == "CLI"

    def __str__(self):
        return f"{self.username} ({self.nivel_permissao})"


class Workspace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="client_workspaces",
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="WorkspaceMember",
        related_name="workspaces",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_workspaces",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["cliente", "name"], name="uniq_workspace_client_name")
        ]

    def user_has_access(self, user):
        if user.is_admin() or self.cliente_id == user.id:
            return True
        return self.members.filter(id=user.id).exists()

    def __str__(self):
        return self.name


class WorkspaceMember(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    can_upload = models.BooleanField(default=True)
    can_share = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["workspace", "user"], name="uniq_workspace_member")
        ]


class Folder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="folders")
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    name = models.CharField(max_length=150)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "parent", "name"], name="uniq_folder_parent_name"
            )
        ]

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class IPFSFile(models.Model):
    pinata_id = models.CharField(max_length=100, null=True, blank=True, verbose_name="ID do Pinata")
    cid = models.CharField(max_length=255, unique=True, verbose_name="IPFS Content ID")
    nome_arquivo = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100, null=True, blank=True)
    tamanho_arquivo = models.BigIntegerField()
    sha256 = models.CharField(max_length=64, blank=True)
    is_encrypted = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    workspace = models.ForeignKey(
        Workspace, null=True, blank=True, on_delete=models.SET_NULL, related_name="files"
    )
    folder = models.ForeignKey(
        Folder, null=True, blank=True, on_delete=models.SET_NULL, related_name="files"
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="files")
    dono_arquivo = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uploaded_ipfs_file",
    )
    data_adicionado = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="deleted_files",
    )
    usuarios_permitidos = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="FileAccess",
        related_name="accessible_ipfs_files",
    )

    class Meta:
        ordering = ["-data_adicionado"]
        indexes = [
            models.Index(fields=["dono_arquivo", "deleted_at"]),
            models.Index(fields=["mime_type"]),
            models.Index(fields=["data_adicionado"]),
        ]

    @property
    def tamanho_em_mb(self):
        return f"{(self.tamanho_arquivo / (1024 * 1024)):.2f} MB"

    @property
    def current_version(self):
        return self.versions.order_by("-version_number").first()

    def user_tem_acesso(self, user):
        if not getattr(user, "is_authenticated", False) or self.deleted_at:
            return False
        if user.is_admin() or self.dono_arquivo_id == user.id:
            return True
        if self.workspace_id and self.workspace.user_has_access(user):
            return True
        return self.usuarios_permitidos.filter(id=user.id).exists()

    def user_pode_compartilhar(self, user):
        if not getattr(user, "is_authenticated", False) or self.deleted_at:
            return False
        if user.is_admin() or self.dono_arquivo_id == user.id:
            return True
        if self.workspace_id:
            return WorkspaceMember.objects.filter(
                workspace_id=self.workspace_id, user=user, can_share=True
            ).exists()
        return False

    def user_pode_alterar(self, user):
        return bool(
            getattr(user, "is_authenticated", False)
            and not self.deleted_at
            and (user.is_admin() or self.dono_arquivo_id == user.id)
        )

    def soft_delete(self, user):
        if not self.deleted_at:
            self.deleted_at = timezone.now()
            self.deleted_by = user
            self.save(update_fields=["deleted_at", "deleted_by", "updated_at"])

    def restore(self):
        if self.deleted_at:
            self.deleted_at = None
            self.deleted_by = None
            self.save(update_fields=["deleted_at", "deleted_by", "updated_at"])

    def __str__(self):
        return self.nome_arquivo


class FileVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.ForeignKey(IPFSFile, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    cid = models.CharField(max_length=255, unique=True)
    pinata_id = models.CharField(max_length=100, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    original_size = models.BigIntegerField()
    encrypted_size = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    encrypted_sha256 = models.CharField(max_length=64, blank=True)
    is_encrypted = models.BooleanField(default=True)
    wrapped_key = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_file_versions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version_number"]
        constraints = [
            models.UniqueConstraint(fields=["file", "version_number"], name="uniq_file_version")
        ]

    def __str__(self):
        return f"{self.file.nome_arquivo} v{self.version_number}"


class FileAccess(models.Model):
    arquivo = models.ForeignKey(IPFSFile, on_delete=models.CASCADE, related_name="access_grants")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="file_access_grants"
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="granted_file_accesses",
    )
    data_compartilhado = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["arquivo", "user"], name="uniq_file_access")
        ]

    def __str__(self):
        return f"{self.user.username} - Acesso a {self.arquivo.nome_arquivo}"


class SharedLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.ForeignKey(IPFSFile, on_delete=models.CASCADE, related_name="shared_links")
    token_prefix = models.CharField(max_length=12, db_index=True)
    token_hash = models.CharField(max_length=64, unique=True)
    password_hash = models.CharField(max_length=128, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    max_downloads = models.PositiveIntegerField(null=True, blank=True)
    download_count = models.PositiveIntegerField(default=0)
    allow_preview = models.BooleanField(default=True)
    allow_download = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_shared_links"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_accessed_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_active(self):
        if self.revoked_at:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        if self.max_downloads is not None and self.download_count >= self.max_downloads:
            return False
        return True


class FileComment(models.Model):
    file = models.ForeignKey(IPFSFile, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]


class DocumentRequest(models.Model):
    STATUS_CHOICES = [
        ("OPEN", "Aberta"),
        ("PARTIAL", "Parcial"),
        ("DONE", "Concluída"),
        ("CANCELLED", "Cancelada"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="document_requests_received",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="document_requests_created",
    )
    due_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="OPEN")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def refresh_status(self):
        items = list(self.items.all())
        if not items:
            return
        completed = sum(bool(item.completed_at) for item in items)
        new_status = "DONE" if completed == len(items) else "PARTIAL" if completed else "OPEN"
        if self.status != new_status and self.status != "CANCELLED":
            self.status = new_status
            self.save(update_fields=["status", "updated_at"])


class DocumentRequestItem(models.Model):
    request = models.ForeignKey(DocumentRequest, on_delete=models.CASCADE, related_name="items")
    label = models.CharField(max_length=180)
    required = models.BooleanField(default=True)
    fulfilled_by_file = models.ForeignKey(
        IPFSFile, null=True, blank=True, on_delete=models.SET_NULL, related_name="request_items"
    )
    completed_at = models.DateTimeField(null=True, blank=True)


class Notification(models.Model):
    KIND_CHOICES = [
        ("FILE", "Arquivo"),
        ("SHARE", "Compartilhamento"),
        ("REQUEST", "Solicitação"),
        ("CHAT", "Chat"),
        ("SECURITY", "Segurança"),
        ("SYSTEM", "Sistema"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default="SYSTEM")
    title = models.CharField(max_length=180)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=500, blank=True)
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "read_at", "created_at"])]


class UserSecuritySettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="security_settings"
    )
    totp_secret_encrypted = models.TextField(blank=True)
    totp_enabled = models.BooleanField(default=False)
    recovery_codes = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class TrackedSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tracked_sessions"
    )
    session_key = models.CharField(max_length=64, unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_seen_at"]


class APIToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_tokens")
    name = models.CharField(max_length=100)
    prefix = models.CharField(max_length=12, db_index=True)
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_active(self):
        return not self.revoked_at and (not self.expires_at or self.expires_at > timezone.now())


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="conversations")
    file = models.ForeignKey(
        IPFSFile, null=True, blank=True, on_delete=models.SET_NULL, related_name="conversations"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Conversa {self.id}"

    def get_other_user(self, user):
        return self.participants.exclude(id=user.id).first()

    def get_last_message(self):
        return self.messages.order_by("-created_at").first()

    def get_unread_count(self, user):
        return self.messages.filter(is_read=False).exclude(sender=user).count()


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages"
    )
    content = models.TextField(max_length=4000)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["conversation", "created_at"])]

    def __str__(self):
        return f"{self.sender.username}: {self.content[:50]}"

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=["is_read"])


# Registro centralizado: alteracoes e acessos ficam no django-auditlog.
auditlog.register(
    CustomUser,
    exclude_fields=["password", "last_login", "foto_perfil"],
    mask_fields=["email", "telefone"],
)
auditlog.register(Workspace)
auditlog.register(WorkspaceMember)
auditlog.register(Folder)
auditlog.register(Tag)
auditlog.register(IPFSFile)
auditlog.register(FileVersion, exclude_fields=["wrapped_key"])
auditlog.register(FileAccess)
auditlog.register(SharedLink, exclude_fields=["token_hash", "password_hash"])
auditlog.register(FileComment)
auditlog.register(DocumentRequest)
auditlog.register(DocumentRequestItem)
auditlog.register(Notification)
auditlog.register(
    UserSecuritySettings,
    exclude_fields=["totp_secret_encrypted", "recovery_codes"],
)
auditlog.register(TrackedSession, exclude_fields=["session_key"])
auditlog.register(APIToken, exclude_fields=["token_hash"])
auditlog.register(Conversation)
auditlog.register(Message)
