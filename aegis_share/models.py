from django.db import models
import uuid
from django.contrib.auth.models import AbstractUser
from django.conf import settings


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
    """Representa uma conversa entre dois ou mais usuários."""
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='conversations',
        verbose_name='Participantes'
    )
    data_ultima_msg = models.DateTimeField(
        auto_now=True,
        verbose_name='Última mensagem em'
    )
    
    def __str__(self):
        return f"Conversa entre {', '.join(self.participants.values_list('username', flat=True))}"


class Message(models.Model):
    """Representa uma única mensagem em uma conversa."""
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='Conversa'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        verbose_name='Remetente'
    )
    content = models.TextField(verbose_name='Conteúdo')

    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data/Hora'
    )

    class Meta:
        ordering = ['timestamp']
        verbose_name = 'Mensagem'
        verbose_name_plural = 'Mensagens'

    def __str__(self):
        return f"Mensagem de {self.sender.username} em {self.timestamp.strftime('%H:%M')}"
