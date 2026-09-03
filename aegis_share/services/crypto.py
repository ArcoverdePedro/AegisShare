import base64
import hashlib
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

FILE_MAGIC = b"AEGIS1"
NONCE_SIZE = 12
KEY_SIZE = 32


class CryptoConfigurationError(ImproperlyConfigured):
    pass


def _master_key() -> bytes:
    raw = settings.FILE_ENCRYPTION_KEY
    if not raw:
        raise CryptoConfigurationError("FILE_ENCRYPTION_KEY nao configurada.")
    try:
        key = base64.urlsafe_b64decode(raw.encode())
    except Exception as exc:
        raise CryptoConfigurationError("FILE_ENCRYPTION_KEY deve estar em base64 URL-safe.") from exc
    if len(key) != KEY_SIZE:
        raise CryptoConfigurationError("FILE_ENCRYPTION_KEY deve representar exatamente 32 bytes.")
    return key


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def encrypt_file(content: bytes, *, aad: bytes) -> tuple[bytes, str, str, str]:
    """Retorna encrypted_blob, wrapped_key, plaintext_sha256, encrypted_sha256."""
    content_key = AESGCM.generate_key(bit_length=256)
    content_nonce = secrets.token_bytes(NONCE_SIZE)
    ciphertext = AESGCM(content_key).encrypt(content_nonce, content, aad)
    encrypted_blob = FILE_MAGIC + content_nonce + ciphertext

    wrap_nonce = secrets.token_bytes(NONCE_SIZE)
    wrapped = AESGCM(_master_key()).encrypt(wrap_nonce, content_key, aad)
    wrapped_key = base64.urlsafe_b64encode(wrap_nonce + wrapped).decode()

    return (
        encrypted_blob,
        wrapped_key,
        sha256_hex(content),
        sha256_hex(encrypted_blob),
    )


def decrypt_file(encrypted_blob: bytes, wrapped_key: str, *, aad: bytes) -> bytes:
    if not encrypted_blob.startswith(FILE_MAGIC):
        raise ValueError("Formato criptografado AegisShare invalido.")

    wrapped_raw = base64.urlsafe_b64decode(wrapped_key.encode())
    wrap_nonce, wrapped = wrapped_raw[:NONCE_SIZE], wrapped_raw[NONCE_SIZE:]
    content_key = AESGCM(_master_key()).decrypt(wrap_nonce, wrapped, aad)

    offset = len(FILE_MAGIC)
    content_nonce = encrypted_blob[offset : offset + NONCE_SIZE]
    ciphertext = encrypted_blob[offset + NONCE_SIZE :]
    return AESGCM(content_key).decrypt(content_nonce, ciphertext, aad)


def encrypt_secret(value: str, *, purpose: str) -> str:
    nonce = secrets.token_bytes(NONCE_SIZE)
    ciphertext = AESGCM(_master_key()).encrypt(nonce, value.encode(), purpose.encode())
    return base64.urlsafe_b64encode(nonce + ciphertext).decode()


def decrypt_secret(value: str, *, purpose: str) -> str:
    raw = base64.urlsafe_b64decode(value.encode())
    nonce, ciphertext = raw[:NONCE_SIZE], raw[NONCE_SIZE:]
    return AESGCM(_master_key()).decrypt(nonce, ciphertext, purpose.encode()).decode()
