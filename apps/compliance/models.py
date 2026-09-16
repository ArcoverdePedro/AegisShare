import uuid

from auditlog.registry import auditlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class DataSubjectRequest(models.Model):
    class Category(models.TextChoices):
        ACCESS = "ACCESS", "Acesso"
        CORRECTION = "CORRECTION", "Correção"
        DELETION = "DELETION", "Exclusão"
        PORTABILITY = "PORTABILITY", "Portabilidade"
        OTHER = "OTHER", "Outra"

    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", "Recebida"
        IN_REVIEW = "IN_REVIEW", "Em análise"
        CLOSED = "CLOSED", "Encerrada administrativamente"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey("pep.Patient", on_delete=models.PROTECT)
    category = models.CharField(max_length=16, choices=Category.choices)
    summary = models.TextField(max_length=2000)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RECEIVED)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["status", "created_at"], name="lgp_status_created_idx")]
        permissions = [
            ("view_requests", "Pode consultar solicitações do titular"),
            ("register_request", "Pode registrar solicitações do titular"),
            ("process_request", "Pode processar solicitações do titular"),
        ]

    def __str__(self):
        return f"Solicitação {self.pk}"

    def save(self, *args, **kwargs):
        if not self._state.adding and set(kwargs.get("update_fields") or ()) != {"status"}:
            raise ValidationError("O cadastro da solicitação não pode ser editado.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Solicitações não podem ser excluídas.")


NEXT_STATUS = {
    DataSubjectRequest.Status.RECEIVED: DataSubjectRequest.Status.IN_REVIEW,
    DataSubjectRequest.Status.IN_REVIEW: DataSubjectRequest.Status.CLOSED,
}


class DataSubjectRequestEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(DataSubjectRequest, on_delete=models.PROTECT, related_name="events")
    from_status = models.CharField(
        max_length=16, choices=DataSubjectRequest.Status.choices, blank=True
    )
    to_status = models.CharField(max_length=16, choices=DataSubjectRequest.Status.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    note = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["request", "to_status"], name="uniq_lgp_request_state"),
        ]

    def __str__(self):
        return f"Evento de solicitação {self.pk}"

    def clean(self):
        super().clean()
        self.note = (self.note or "").strip()
        expected = (
            NEXT_STATUS.get(self.from_status)
            if self.from_status
            else DataSubjectRequest.Status.RECEIVED
        )
        if self.to_status != expected:
            raise ValidationError("Transição administrativa inválida.")
        if self.to_status == DataSubjectRequest.Status.CLOSED and not self.note:
            raise ValidationError(
                {"note": "Registre uma nota de atendimento para encerrar a solicitação."}
            )
        if not self.from_status and self.note:
            raise ValidationError({"note": "O evento inicial não deve duplicar o resumo."})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("O histórico da solicitação é imutável.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Eventos de solicitação não podem ser excluídos.")


auditlog.register(DataSubjectRequest, exclude_fields=["summary"])
auditlog.register(DataSubjectRequestEvent, exclude_fields=["note"])
