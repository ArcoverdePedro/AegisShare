import logging
import uuid
from pathlib import Path

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from aegis_share.models import FileAccess, FileVersion, IPFSFile

from .antivirus import scan_bytes
from .crypto import decrypt_file, encrypt_file, sha256_hex
from .notifications import notify_file_shared
from .pinata import PinataClient

logger = logging.getLogger(__name__)


class FileIntegrityError(RuntimeError):
    pass


def _version_aad(version_id: uuid.UUID) -> bytes:
    return f"aegisshare:file-version:{version_id}".encode()


def _encrypted_name(filename: str, version_number: int) -> str:
    clean = Path(filename).name.replace("/", "_").replace("\\", "_")
    return f"{clean}.v{version_number}.aegis"


def create_file_from_upload(*, uploaded_file, owner, actor, workspace=None, folder=None, description=""):
    content = uploaded_file.read()
    scan_bytes(content)

    version_id = uuid.uuid4()
    version_number = 1
    encrypted, wrapped_key, plain_hash, encrypted_hash = encrypt_file(
        content, aad=_version_aad(version_id)
    )

    client = PinataClient()
    remote = client.upload_bytes(
        encrypted,
        filename=_encrypted_name(uploaded_file.name, version_number),
    )

    try:
        with transaction.atomic():
            file = IPFSFile.objects.create(
                pinata_id=remote["id"],
                cid=remote["cid"],
                nome_arquivo=Path(uploaded_file.name).name,
                mime_type=uploaded_file.content_type or "application/octet-stream",
                tamanho_arquivo=len(content),
                sha256=plain_hash,
                is_encrypted=True,
                description=description,
                workspace=workspace,
                folder=folder,
                dono_arquivo=owner,
            )
            version = FileVersion.objects.create(
                id=version_id,
                file=file,
                version_number=version_number,
                cid=remote["cid"],
                pinata_id=remote["id"],
                mime_type=file.mime_type or "application/octet-stream",
                original_size=len(content),
                encrypted_size=len(encrypted),
                sha256=plain_hash,
                encrypted_sha256=encrypted_hash,
                is_encrypted=True,
                wrapped_key=wrapped_key,
                uploaded_by=actor,
            )
            if actor.is_employee() and actor.id != owner.id:
                FileAccess.objects.get_or_create(
                    arquivo=file,
                    user=actor,
                    defaults={"granted_by": actor},
                )
    except Exception:
        client.delete_file(remote["id"])
        raise

    logger.info(
        "file_created",
        extra={"file_id": file.id, "version_id": str(version.id), "actor_id": str(actor.id)},
    )
    return file


def create_new_version(*, file: IPFSFile, uploaded_file, actor):
    if not file.user_pode_alterar(actor):
        raise PermissionError("Usuario sem permissao para criar nova versao.")

    content = uploaded_file.read()
    scan_bytes(content)

    current = file.versions.aggregate(max_version=Max("version_number"))["max_version"] or 0
    version_number = current + 1
    version_id = uuid.uuid4()
    encrypted, wrapped_key, plain_hash, encrypted_hash = encrypt_file(
        content, aad=_version_aad(version_id)
    )

    client = PinataClient()
    remote = client.upload_bytes(
        encrypted,
        filename=_encrypted_name(file.nome_arquivo, version_number),
    )

    try:
        with transaction.atomic():
            version = FileVersion.objects.create(
                id=version_id,
                file=file,
                version_number=version_number,
                cid=remote["cid"],
                pinata_id=remote["id"],
                mime_type=uploaded_file.content_type or file.mime_type or "application/octet-stream",
                original_size=len(content),
                encrypted_size=len(encrypted),
                sha256=plain_hash,
                encrypted_sha256=encrypted_hash,
                is_encrypted=True,
                wrapped_key=wrapped_key,
                uploaded_by=actor,
            )
            file.cid = remote["cid"]
            file.pinata_id = remote["id"]
            file.mime_type = version.mime_type
            file.tamanho_arquivo = len(content)
            file.sha256 = plain_hash
            file.is_encrypted = True
            file.save(
                update_fields=[
                    "cid",
                    "pinata_id",
                    "mime_type",
                    "tamanho_arquivo",
                    "sha256",
                    "is_encrypted",
                    "updated_at",
                ]
            )
    except Exception:
        client.delete_file(remote["id"])
        raise

    logger.info(
        "file_version_created",
        extra={"file_id": file.id, "version": version_number, "actor_id": str(actor.id)},
    )
    return version


def get_version_content(version: FileVersion) -> bytes:
    remote_content = PinataClient().download_bytes(version.cid)

    if version.encrypted_sha256 and sha256_hex(remote_content) != version.encrypted_sha256:
        raise FileIntegrityError("O conteudo criptografado nao corresponde ao hash registrado.")

    if version.is_encrypted:
        if not version.wrapped_key:
            raise FileIntegrityError("Versao marcada como criptografada sem chave protegida.")
        plain = decrypt_file(
            remote_content,
            version.wrapped_key,
            aad=_version_aad(version.id),
        )
    else:
        plain = remote_content

    if version.sha256 and sha256_hex(plain) != version.sha256:
        raise FileIntegrityError("O arquivo recuperado nao corresponde ao SHA-256 registrado.")
    return plain


def grant_access(*, file: IPFSFile, recipient, actor):
    if not file.user_pode_compartilhar(actor):
        raise PermissionError("Usuario sem permissao para compartilhar este arquivo.")
    grant, created = FileAccess.objects.get_or_create(
        arquivo=file,
        user=recipient,
        defaults={"granted_by": actor},
    )
    if created:
        notify_file_shared(file, recipient, actor)
    return grant, created


def revoke_access(*, file: IPFSFile, recipient, actor):
    if not file.user_pode_compartilhar(actor):
        raise PermissionError("Usuario sem permissao para revogar este acesso.")
    return FileAccess.objects.filter(arquivo=file, user=recipient).delete()[0]


def purge_file(file: IPFSFile):
    """Remove conteudo remoto e registro local. Retorna IDs remotos que falharam."""
    client = PinataClient()
    failures = []
    for version in file.versions.all():
        if version.pinata_id and not client.delete_file(version.pinata_id):
            failures.append(version.pinata_id)
    if failures:
        return failures
    file.delete()
    return []


def purge_expired_trash(retention_days: int):
    cutoff = timezone.now() - timezone.timedelta(days=retention_days)
    purged = 0
    failures = []
    for file in IPFSFile.objects.filter(deleted_at__isnull=False, deleted_at__lte=cutoff):
        file_failures = purge_file(file)
        if file_failures:
            failures.extend(file_failures)
        else:
            purged += 1
    return purged, failures
