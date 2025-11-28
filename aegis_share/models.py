import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

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
        return self.nivel_permissao == "ADM"

    def __str__(self):
        return f"{self.username} ({self.nivel_permissao})"


class IPFSFile(models.Model):
    pinata_id = models.CharField(max_length=100, null=True, blank=True, verbose_name="ID do Pinata")
    cid = models.CharField(max_length=255, unique=True, verbose_name="IPFS Content ID")
    nome_arquivo = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100, null=True, blank=True)
    tamanho_arquivo = models.BigIntegerField()
    dono_arquivo = models.ForeignKey(
        "CustomUser", on_delete=models.CASCADE, related_name="uploaded_ipfs_file"
    )
    data_adicionado = models.DateTimeField(auto_now_add=True)
    usuarios_permitidos = models.ManyToManyField(
        "CustomUser", through="FileAccess", related_name="accessible_ipfs_files"
    )

    @property
    def tamanho_em_mb(self):
        return f"{(self.tamanho_arquivo / (1024 * 1024)):.2f} MB"

    def user_tem_acesso(self, user):
        if user.is_admin():
            return True
        if self.dono_arquivo == user:
            return True
        return self.usuarios_permitidos.filter(id=user.id).exists()

    def __str__(self):
        return self.nome_arquivo


class FileAccess(models.Model):
    arquivo = models.ForeignKey(
        IPFSFile, on_delete=models.CASCADE
    )

    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE
    )

    data_compartilhado = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("arquivo", "user"),)

    def __str__(self):
        return f"{self.user.username} - Acesso a {self.arquivo.nome_arquivo}"


class Conversation(models.Model):
    """Modelo para representar uma conversa entre dois usuários"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='conversations'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Conversa {self.id}"

    def get_other_user(self, user):
        """Retorna o outro participante da conversa"""
        return self.participants.exclude(id=user.id).first()

    def get_last_message(self):
        """Retorna a última mensagem da conversa"""
        return self.messages.order_by('-created_at').first()

    def get_unread_count(self, user):
        """Conta mensagens não lidas para um usuário"""
        return self.messages.filter(is_read=False).exclude(sender=user).count()


class Message(models.Model):
    """Modelo para representar uma mensagem"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Campos opcionais para anexos
    attachment = models.ForeignKey(
        'IPFSFile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages'
    )

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender.username}: {self.content[:50]}"

    def mark_as_read(self):
        """Marca a mensagem como lida"""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])