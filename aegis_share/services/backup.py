"""Cifragem em fluxo de backups (AES-256-GCM por blocos, ordem e fim autenticados)."""

import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings

from .crypto import CryptoConfigurationError, decode_key

MAGIC = b"AEGISBAK1"
PREFIX_SIZE = 7
CHUNK_SIZE = 1 << 20


class BackupError(RuntimeError):
    pass


def backup_key() -> bytes:
    key = decode_key(settings.BACKUP_ENCRYPTION_KEY, "BACKUP_ENCRYPTION_KEY")
    if settings.BACKUP_ENCRYPTION_KEY == settings.FILE_ENCRYPTION_KEY:
        raise CryptoConfigurationError(
            "BACKUP_ENCRYPTION_KEY deve ser diferente da chave de arquivos."
        )
    return key


def _nonce(prefix: bytes, counter: int, last: bool) -> bytes:
    # 7 bytes aleatorios por backup + contador + marca de bloco final: impede reordenar/truncar.
    return prefix + counter.to_bytes(4, "big") + (b"\x01" if last else b"\x00")


def seal(src, dst, key: bytes, chunk_size: int = CHUNK_SIZE) -> None:
    aes = AESGCM(key)
    prefix = secrets.token_bytes(PREFIX_SIZE)
    dst.write(MAGIC + prefix)
    counter, chunk = 0, src.read(chunk_size)
    while True:
        following = src.read(chunk_size)
        last = not following
        sealed = aes.encrypt(_nonce(prefix, counter, last), chunk, MAGIC)
        dst.write(len(sealed).to_bytes(4, "big") + sealed)
        if last:
            return
        counter, chunk = counter + 1, following


def unseal(src, dst, key: bytes) -> None:
    aes = AESGCM(key)
    header = src.read(len(MAGIC) + PREFIX_SIZE)
    if not header.startswith(MAGIC) or len(header) != len(MAGIC) + PREFIX_SIZE:
        raise BackupError("Arquivo nao e um backup AegisShare.")
    prefix, counter = header[len(MAGIC) :], 0
    while True:
        size = src.read(4)
        sealed = src.read(int.from_bytes(size, "big")) if len(size) == 4 else b""
        if not sealed or len(sealed) != int.from_bytes(size, "big"):
            raise BackupError("Backup truncado.")
        for last in (False, True):
            try:
                dst.write(aes.decrypt(_nonce(prefix, counter, last), sealed, MAGIC))
                break
            except InvalidTag:
                continue
        else:
            raise BackupError("Backup corrompido ou chave incorreta.")
        if last:
            if src.read(1):
                raise BackupError("Dados apos o bloco final.")
            return
        counter += 1
