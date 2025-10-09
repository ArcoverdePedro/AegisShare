from django.db import models
import uuid
from django.contrib.auth.models import AbstractUser


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

    cpf = models.CharField(max_length=15, null=True, blank=True)

    nivel_permissao = models.CharField(
        max_length=4,
        choices=NIVEL_PERMISSAO_CHOICES,
        default="CLI",
        verbose_name="Nível de Permissão",
    )

    def is_admin(self):
        return self.nivel_permissao == "ADM"

    def __str__(self):
        return f"{self.username} ({self.get_nivel_permissao_display()})"


class IPFSFile(models.Model):
    cid = models.CharField(
        max_length=255, unique=True, verbose_name="IPFS Content ID"
    )

    nome_arquivo = models.CharField(max_length=255)

    tamanho_arquivo = models.BigIntegerField()

    dono_arquivo = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="uploaded_ipfs_file"
    )

    data_adicionado = models.DateTimeField(auto_now_add=True)

    usuarios_permitidos = models.ManyToManyField(
        CustomUser, through="FileAccess", related_name="accessible_ipfs_files"
    )

    def user_can_access(self, user):

        if user.is_admin():
            return True

        if self.dono_arquivo == user:
            return True

        return self.usuarios_permitidos.filter(pk=user.pk).exists()

    def __str__(self):
        return self.nome_arquivo


class FileAccess(models.Model):

    arquivo = models.ForeignKey(IPFSFile, on_delete=models.CASCADE)

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    data_compartilhado = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("arquivo", "user"),)

    def __str__(self):
        return f"{self.user.username} - Acesso a {self.arquivo.nome_arquivo}"
