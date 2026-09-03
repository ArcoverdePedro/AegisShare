import hashlib
import secrets
from datetime import timedelta

import pyotp
from django.utils import timezone

from aegis_share.models import APIToken, UserSecuritySettings

from .crypto import decrypt_secret, encrypt_secret


def _security_settings(user):
    obj, _ = UserSecuritySettings.objects.get_or_create(user=user)
    return obj


def begin_totp_setup(user):
    security = _security_settings(user)
    secret = pyotp.random_base32()
    security.totp_secret_encrypted = encrypt_secret(
        secret, purpose=f"totp:{user.id}"
    )
    security.totp_enabled = False
    security.recovery_codes = []
    security.save()
    uri = pyotp.TOTP(secret).provisioning_uri(
        name=user.email or user.username,
        issuer_name="AegisShare",
    )
    return secret, uri


def verify_totp(user, code: str) -> bool:
    try:
        security = user.security_settings
    except UserSecuritySettings.DoesNotExist:
        return False
    if not security.totp_secret_encrypted:
        return False
    secret = decrypt_secret(
        security.totp_secret_encrypted,
        purpose=f"totp:{user.id}",
    )
    return pyotp.TOTP(secret).verify((code or "").strip(), valid_window=1)


def enable_totp(user, code: str):
    security = _security_settings(user)
    if not verify_totp(user, code):
        raise ValueError("Codigo TOTP invalido.")

    recovery_plain = [secrets.token_hex(5).upper() for _ in range(8)]
    security.recovery_codes = [
        hashlib.sha256(code.encode()).hexdigest() for code in recovery_plain
    ]
    security.totp_enabled = True
    security.save(update_fields=["totp_enabled", "recovery_codes", "updated_at"])
    return recovery_plain


def disable_totp(user):
    security = _security_settings(user)
    security.totp_enabled = False
    security.totp_secret_encrypted = ""
    security.recovery_codes = []
    security.save()


def consume_recovery_code(user, code: str) -> bool:
    security = _security_settings(user)
    candidate = hashlib.sha256((code or "").strip().upper().encode()).hexdigest()
    if candidate not in security.recovery_codes:
        return False
    security.recovery_codes = [item for item in security.recovery_codes if item != candidate]
    security.save(update_fields=["recovery_codes", "updated_at"])
    return True


def create_api_token(user, *, name: str, expires_days=None):
    raw = f"ags_{secrets.token_urlsafe(36)}"
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    expires_at = None
    if expires_days:
        expires_at = timezone.now() + timedelta(days=int(expires_days))
    obj = APIToken.objects.create(
        user=user,
        name=name,
        prefix=raw[:12],
        token_hash=token_hash,
        expires_at=expires_at,
    )
    return obj, raw


def authenticate_api_token(raw: str):
    token_hash = hashlib.sha256((raw or "").encode()).hexdigest()
    token = APIToken.objects.select_related("user").filter(token_hash=token_hash).first()
    if not token or not token.is_active or not token.user.is_active:
        return None
    token.last_used_at = timezone.now()
    token.save(update_fields=["last_used_at"])
    return token.user
