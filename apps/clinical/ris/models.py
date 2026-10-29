import uuid

from auditlog.registry import auditlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ImagingExam(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField("Código", max_length=64, unique=True)
    name = models.CharField("Nome", max_length=200)
    active = models.BooleanField("Ativo", default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"Exame {self.pk}"

    def clean(self):
        for field in ("code", "name"):
            value = getattr(self, field).strip()
            if not value:
                raise ValidationError({field: "Este campo é obrigatório."})
            setattr(self, field, value)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class ImagingOrder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.ForeignKey("pep.Encounter", on_delete=models.PROTECT)
    exam = models.ForeignKey(ImagingExam, on_delete=models.PROTECT)
    exam_code = models.CharField(max_length=64)
    exam_name = models.CharField(max_length=200)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    requested_at = models.DateTimeField(auto_now_add=True)
    operation_key = models.UUIDField()

    class Meta:
        ordering = ["-requested_at", "-id"]
        indexes = [models.Index(fields=["-requested_at", "-id"], name="ris_requested_idx")]
        constraints = [
            models.UniqueConstraint(fields=["operation_key"], name="uniq_ris_operation_key")
        ]
        permissions = [
            ("view_orders", "Pode consultar pedidos de imagem"),
            ("order_exam", "Pode solicitar exame de imagem"),
            ("write_report", "Pode redigir e retificar laudo de imagem"),
            ("release_report", "Pode liberar laudo de imagem"),
        ]

    def __str__(self):
        return f"Pedido {self.pk}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Pedidos não podem ser alterados.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Pedidos não podem ser excluídos.")


class ImagingReport(models.Model):
    """Laudo em texto; so liberado aparece ao solicitante. Retificacao = nova versao."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(ImagingOrder, on_delete=models.PROTECT, related_name="reports")
    performed_at = models.DateTimeField("Exame realizado em")
    findings = models.TextField("Achados")
    impression = models.TextField("Impressão")
    supersedes = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="superseded_by"
    )
    reason = models.CharField("Motivo da retificação", max_length=255, blank=True)
    authored_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    authored_at = models.DateTimeField(auto_now_add=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-authored_at", "-id"]

    def __str__(self):
        return f"Laudo {self.pk}"

    def save(self, *args, **kwargs):
        if not self._state.adding and set(kwargs.get("update_fields") or ()) != {
            "released_by",
            "released_at",
        }:
            raise ValidationError("Laudos não podem ser editados; registre retificação.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Laudos não podem ser excluídos.")


auditlog.register(ImagingExam, exclude_fields=["code", "name"])
auditlog.register(ImagingOrder, exclude_fields=["exam_code", "exam_name"])
auditlog.register(ImagingReport, exclude_fields=["findings", "impression", "reason"])
