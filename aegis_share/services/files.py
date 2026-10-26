import logging
import uuid
from datetime import timedelta
from pathlib import Path

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from aegis_share.file_policy import FilePolicyError, validate_uploaded_file
from aegis_share.models import FileAccess, FileVersion, IPFSFile, WorkspaceMember

from .antivirus import scan_bytes
from .crypto import decrypt_file, encrypt_file, sha256_hex
from .notifications import notify_file_shared
from .storage import LOCAL_PREFIX, LocalStorageClient, client_for, storage_client

logger = logging.getLogger(__name__)


class FileIntegrityError(RuntimeError):
    pass


def _version_aad(version_id: uuid.UUID) -> bytes:
    return f"aegisshare:file-version:{version_id}".encode()


def _encrypted_name(filename: str, version_number: int) -> str:
    clean = Path(filename).name.replace("/", "_").replace("\\", "_")
    return f"{clean}.v{version_number}.aegis"


def _read_validated(uploaded_file) -> bytes:
    validate_uploaded_file(uploaded_file)
    content = uploaded_file.read()
    if len(content) != uploaded_file.size:
        raise FilePolicyError("Nao foi possivel ler o arquivo completo.")
    scan_bytes(content)
    return content


def _validate_upload_scope(*, owner, actor, workspace=None, folder=None):
    if folder and not workspace:
        raise PermissionError("Uma pasta exige um workspace associado.")
    if not workspace:
        return

    if workspace.cliente_id != owner.id:
        raise PermissionError("O workspace nao pertence ao cliente selecionado.")

    actor_can_upload = bool(
        getattr(actor, "is_authenticated", False)
        and (
            actor.is_admin()
            or workspace.cliente_id == actor.id
            or WorkspaceMember.objects.filter(
                workspace=workspace,
                user=actor,
                can_upload=True,
            ).exists()
        )
    )
    if not actor_can_upload:
        raise PermissionError("Usuario sem permissao de upload neste workspace.")

    if folder and folder.workspace_id != workspace.id:
        raise PermissionError("A pasta nao pertence ao workspace selecionado.")


def create_file_from_upload(
    *, uploaded_file, owner, actor, workspace=None, folder=None, description=""
):
    _validate_upload_scope(
        owner=owner,
        actor=actor,
        workspace=workspace,
        folder=folder,
    )
    content = _read_validated(uploaded_file)

    version_id = uuid.uuid4()
    version_number = 1
    encrypted, wrapped_key, plain_hash, encrypted_hash = encrypt_file(
        content, aad=_version_aad(version_id)
    )

    client = storage_client()
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
        extra={
            "file_id": file.id,
            "version_id": str(version.id),
            "actor_id": str(actor.id),
        },
    )
    return file


def create_new_version(*, file: IPFSFile, uploaded_file, actor):
    if not file.user_pode_alterar(actor):
        raise PermissionError("Usuario sem permissao para criar nova versao.")

    content = _read_validated(uploaded_file)
    current = file.versions.aggregate(max_version=Max("version_number"))["max_version"] or 0
    version_number = current + 1
    version_id = uuid.uuid4()
    encrypted, wrapped_key, plain_hash, encrypted_hash = encrypt_file(
        content, aad=_version_aad(version_id)
    )

    client = storage_client()
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
                mime_type=(
                    uploaded_file.content_type
                    or file.mime_type
                    or "application/octet-stream"
                ),
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
        extra={
            "file_id": file.id,
            "version": version_number,
            "actor_id": str(actor.id),
        },
    )
    return version


def get_version_content(version: FileVersion) -> bytes:
    remote_content = client_for(version.cid).download_bytes(version.cid)
    if version.encrypted_sha256 and sha256_hex(remote_content) != version.encrypted_sha256:
        raise FileIntegrityError(
            "O conteudo criptografado nao corresponde ao hash registrado."
        )

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
    failures = []
    versions = list(file.versions.all())
    if not versions and file.pinata_id:
        # Compatibilidade com registros muito antigos sem FileVersion.
        versions = [file]
    for version in versions:
        pinata_id = getattr(version, "pinata_id", "")
        if pinata_id and not client_for(pinata_id).delete_file(pinata_id):
            failures.append(pinata_id)
    if failures:
        return failures
    file.delete()
    return []


def purge_expired_trash(retention_days: int):
    cutoff = timezone.now() - timedelta(days=retention_days)
    purged = 0
    failures = []
    for file in IPFSFile.objects.filter(
        deleted_at__isnull=False,
        deleted_at__lte=cutoff,
    ):
        file_failures = purge_file(file)
        if file_failures:
            failures.extend(file_failures)
        else:
            purged += 1
    return purged, failures


def copy_version_to_local(version: FileVersion, *, encrypt_plaintext=False):
    """Copia uma versao para o backend local, conferindo bytes antes de trocar a referencia.

    A origem nao e removida: retorna (cid, pinata_id) antigos para desativacao posterior.
    """
    if version.cid.startswith(LOCAL_PREFIX):
        return None
    if not version.is_encrypted and not encrypt_plaintext:
        raise FileIntegrityError("Versao legada sem criptografia exige --encrypt-plaintext.")

    content = client_for(version.cid).download_bytes(version.cid)
    if version.is_encrypted:
        if not version.encrypted_sha256 or sha256_hex(content) != version.encrypted_sha256:
            raise FileIntegrityError("Conteudo de origem nao confere com o hash registrado.")
    else:
        if not version.sha256 or sha256_hex(content) != version.sha256:
            raise FileIntegrityError("Conteudo legado nao confere com o SHA-256 registrado.")
        content, version.wrapped_key, _, version.encrypted_sha256 = encrypt_file(
            content, aad=_version_aad(version.id)
        )
        version.encrypted_size = len(content)
        version.is_encrypted = True

    old = (version.cid, version.pinata_id)
    local = LocalStorageClient()
    remote = local.upload_bytes(
        content, filename=_encrypted_name(version.file.nome_arquivo, version.version_number)
    )
    version.cid = remote["cid"]
    version.pinata_id = remote["id"]
    try:
        get_version_content(version)
        with transaction.atomic():
            version.save(
                update_fields=[
                    "cid",
                    "pinata_id",
                    "is_encrypted",
                    "wrapped_key",
                    "encrypted_sha256",
                    "encrypted_size",
                ]
            )
            IPFSFile.objects.filter(pk=version.file_id, cid=old[0]).update(
                cid=version.cid, pinata_id=version.pinata_id, is_encrypted=True
            )
    except Exception:
        local.delete_file(remote["id"])
        raise
    return old
