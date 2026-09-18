import uuid

from auditlog.context import set_actor
from auditlog.signals import accessed
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.views.decorators.debug import sensitive_variables

from aegis_share.services.crypto import encrypt_file, sha256_hex
from apps.clinical.pep.permissions import is_internal_professional

from .models import LaboratoryInboxReceipt, LaboratorySource

MAX_FILE_BYTES = 1024 * 1024
MAX_BODY_BYTES = MAX_FILE_BYTES + 64 * 1024


def require_inbox_permission(user, *, receive=False):
    permissions = ["interoperability.view_lab_inbox"]
    if receive:
        permissions.append("interoperability.receive_lab_file")
    if not is_internal_professional(user) or not user.has_perms(permissions):
        raise PermissionDenied


def accessible_sources(user):
    sources = LaboratorySource.objects.all()
    return sources if user.is_superuser else sources.filter(operators=user)


def metadata_receipts(user):
    return (
        LaboratoryInboxReceipt.objects.filter(source__in=accessible_sources(user))
        .defer(
            "ciphertext",
            "wrapped_key",
            "plaintext_sha256",
            "ciphertext_sha256",
            "source__label",
        )
        .select_related("source", "received_by")
    )


@sensitive_variables()
def receive_laboratory_file(*, user, source_id, uploaded_file):
    require_inbox_permission(user, receive=True)
    get_object_or_404(accessible_sources(user).filter(active=True), pk=source_id)
    content = uploaded_file.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise ValidationError("O arquivo excede o limite de 1 MiB.", code="too_large")
    if not content or len(content) != uploaded_file.size:
        raise ValidationError("Arquivo vazio ou incompleto.")
    digest = sha256_hex(content)
    with transaction.atomic(), set_actor(user):
        source = get_object_or_404(LaboratorySource.objects.select_for_update(), pk=source_id)
        require_inbox_permission(user, receive=True)
        get_object_or_404(accessible_sources(user).filter(active=True), pk=source.pk)
        # O lock da origem serializa recebimentos idênticos, sem capturar falhas de auditoria.
        existing = (
            LaboratoryInboxReceipt.objects.defer("ciphertext", "wrapped_key")
            .filter(source=source, plaintext_sha256=digest)
            .first()
        )
        if existing:
            accessed.send(LaboratoryInboxReceipt, instance=existing)
            return existing
        receipt_id = uuid.uuid4()
        ciphertext, wrapped_key, plain_hash, cipher_hash = encrypt_file(
            content,
            aad=f"aegisshare:lab-inbox:{receipt_id}".encode(),
        )
        return LaboratoryInboxReceipt.objects.create(
            id=receipt_id,
            source=source,
            received_by=user,
            size=len(content),
            ciphertext=ciphertext,
            wrapped_key=wrapped_key,
            plaintext_sha256=plain_hash,
            ciphertext_sha256=cipher_hash,
        )
