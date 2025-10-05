from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class UsersInfos(models.Model):
    NIVEL_PERMISSAO_CHOICES = [
        ('ADM', 'Administrador'),
        ('FUNC', 'Funcionário'),
        ('CLI', 'Cliente'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    foto_perfil = models.TextField(null=True, blank=True)
    cpf = models.CharField(max_length=50)

    nivel_permissao = models.CharField(
        max_length=4,
        choices=NIVEL_PERMISSAO_CHOICES,
        default='CLI',
        verbose_name='Nível de Permissão'
    )

    def __str__(self):
        return f"Usuario {self.user.username} ({self.get_nivel_permissao_display()})"


class IPFSFile(models.Model):
    cid = models.CharField(
        max_length=255,
        unique=True,
        verbose_name='IPFS Content ID'
    )

    # O nome amigável/original do arquivo (não é o CID)
    original_name = models.CharField(max_length=255)

    # Tamanho do arquivo em bytes (útil para exibição)
    size = models.BigIntegerField()

    # O usuário que publicou ou "cadastrou" este CID
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='uploaded_ipfs_files'
    )

    # Data de quando este metadado foi adicionado ao seu banco
    date_added = models.DateTimeField(auto_now_add=True)

    # A relação Many-to-Many com o modelo intermediário para o compartilhamento
    users_with_access = models.ManyToManyField(
        User,
        through='FileAccess',
        related_name='accessible_ipfs_files'
    )

    def __str__(self):
        return self.original_name


class FileAccess(models.Model):
    # FK para o arquivo IPFS
    file = models.ForeignKey(IPFSFile, on_delete=models.CASCADE)

    # FK para o usuário que tem acesso
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    # Nível de permissão (exemplo: Read Only, Admin)
    PERMISSIONS_CHOICES = [
        ('R', 'Read Only'),
        ('RW', 'Read/Write'),
    ]
    permission_level = models.CharField(
        max_length=2,
        choices=PERMISSIONS_CHOICES,
        default='R'
    )
    date_shared = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (('file', 'user'),)

    def __str__(self):
        return f'{self.user.username} - Acesso a {self.file.original_name}'
