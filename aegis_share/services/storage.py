import logging
import os
import string
import tempfile
from pathlib import Path

from django.conf import settings

from .crypto import sha256_hex

logger = logging.getLogger(__name__)

LOCAL_PREFIX = "local:"


class StorageError(RuntimeError):
    pass


class LocalStorageClient:
    """Diretorio privado no servidor; recebe somente bytes ja cifrados."""

    def __init__(self):
        self.root = Path(settings.FILE_STORAGE_ROOT)

    def _path(self, ref: str) -> Path:
        digest = ref.removeprefix(LOCAL_PREFIX)
        if len(digest) != 64 or not set(digest) <= set(string.hexdigits.lower()):
            raise StorageError("Referencia local invalida.")
        return self.root / digest[:2] / digest

    def upload_bytes(self, content: bytes, *, filename: str) -> dict:
        ref = LOCAL_PREFIX + sha256_hex(content)
        path = self._path(ref)
        try:
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
                tmp.write(content)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.chmod(tmp.name, 0o600)
            os.replace(tmp.name, path)
        except OSError as exc:
            logger.exception("local_storage_upload_failed", extra={"upload_filename": filename})
            raise StorageError("Falha ao gravar arquivo no armazenamento local.") from exc
        return {"id": ref, "cid": ref}

    def download_bytes(self, ref: str) -> bytes:
        try:
            return self._path(ref).read_bytes()
        except OSError as exc:
            logger.exception("local_storage_download_failed", extra={"cid": ref})
            raise StorageError("Falha ao recuperar arquivo do armazenamento local.") from exc

    def delete_file(self, ref: str) -> bool:
        try:
            self._path(ref).unlink(missing_ok=True)
            return True
        except OSError, StorageError:
            logger.exception("local_storage_delete_failed", extra={"pinata_id": ref})
            return False

    def ping(self) -> bool:
        return self.root.is_dir() and os.access(self.root, os.W_OK)


def storage_client():
    """Backend usado para gravar novas versoes."""
    from .pinata import PinataClient

    if settings.FILE_STORAGE_BACKEND == "local":
        return LocalStorageClient()
    return PinataClient()


def client_for(ref: str):
    """Leitura/remocao seguem a origem da referencia; CIDs legados continuam na Pinata."""
    from .pinata import PinataClient

    return LocalStorageClient() if ref.startswith(LOCAL_PREFIX) else PinataClient()
