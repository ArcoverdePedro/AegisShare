import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from aegis_share.models import SharedLink


class SharedLinkError(ValueError):
    pass


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_shared_link(
    *,
    file,
    actor,
    expires_in_hours=None,
    password=None,
    max_downloads=None,
    allow_preview=True,
    allow_download=True,
):
    if not file.user_pode_compartilhar(actor):
        raise PermissionError("Usuario sem permissao para gerar link deste arquivo.")

    token = secrets.token_urlsafe(32)
    expires_at = None
    if expires_in_hours:
        expires_at = timezone.now() + timedelta(hours=int(expires_in_hours))

    link = SharedLink.objects.create(
        file=file,
        token_prefix=token[:12],
        token_hash=_token_hash(token),
        password_hash=make_password(password) if password else "",
        expires_at=expires_at,
        max_downloads=max_downloads or None,
        allow_preview=allow_preview,
        allow_download=allow_download,
        created_by=actor,
    )
    return link, token


def resolve_shared_link(token: str, *, password=None, for_download=False):
    link = (
        SharedLink.objects.select_related("file", "file__dono_arquivo")
        .filter(token_hash=_token_hash(token))
        .first()
    )
    if not link or not link.is_active or link.file.deleted_at:
        raise SharedLinkError("Link invalido, expirado ou revogado.")
    if link.password_hash and not check_password(password or "", link.password_hash):
        raise SharedLinkError("Senha do link invalida.")
    if for_download and not link.allow_download:
        raise SharedLinkError("Este link nao permite download.")
    if not for_download and not link.allow_preview:
        raise SharedLinkError("Este link nao permite visualizacao.")
    return link


def consume_download(token: str, *, password=None):
    with transaction.atomic():
        link = (
            SharedLink.objects.select_for_update()
            .select_related("file", "file__dono_arquivo")
            .filter(token_hash=_token_hash(token))
            .first()
        )
        if not link or not link.is_active or link.file.deleted_at:
            raise SharedLinkError("Link invalido, expirado ou sem downloads disponiveis.")
        if link.password_hash and not check_password(password or "", link.password_hash):
            raise SharedLinkError("Senha do link invalida.")
        if not link.allow_download:
            raise SharedLinkError("Este link nao permite download.")
        link.download_count += 1
        link.last_accessed_at = timezone.now()
        link.save(update_fields=["download_count", "last_accessed_at"])
        return link


def revoke_shared_link(link, actor):
    if not link.file.user_pode_compartilhar(actor):
        raise PermissionError("Usuario sem permissao para revogar este link.")
    link.revoked_at = timezone.now()
    link.save(update_fields=["revoked_at"])
