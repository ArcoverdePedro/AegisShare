import uuid

from auditlog.registry import auditlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class LabTest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField("Código", max_length=64, unique=True)
    name = models.CharField("Nome", max_length=200)
    specimen_type = models.CharField("Material", max_length=100)
    active = models.BooleanField("Ativo", default=True)

    class Meta:
        ordering = ["name", "code"]

    def __str__(self):
        return f"Exame {self.pk}"

    def clean(self):
        for field in ("code", "name", "specimen_type"):
            value = getattr(self, field).strip()
            if not value:
                raise ValidationError({field: "Este campo é obrigatório."})
            setattr(self, field, value)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class ServiceRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.ForeignKey("pep.Encounter", on_delete=models.PROTECT)
    lab_test = models.ForeignKey(LabTest, on_delete=models.PROTECT)
    test_code = models.CharField(max_length=64)
    test_name = models.CharField(max_length=200)
    specimen_type = models.CharField(max_length=100)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    requested_at = models.DateTimeField(auto_now_add=True)
    operation_key = models.UUIDField(unique=True)

    class Meta:
        ordering = ["-requested_at", "-id"]
        indexes = [models.Index(fields=["-requested_at", "-id"], name="lis_requested_idx")]
        permissions = [
            ("view_orders", "Pode consultar pedidos laboratoriais"),
            ("order_test", "Pode solicitar exame"),
            ("collect_specimen", "Pode registrar coleta"),
            ("receive_specimen", "Pode receber ou rejeitar amostra no laboratório"),
            ("cancel_order", "Pode cancelar pedido laboratorial"),
        ]

    @property
    def specimen(self):
        """Amostra vigente: a mais recente nao rejeitada (recoletas preservam as anteriores)."""
        return next((s for s in self.specimens.all() if s.status != "REJECTED"), None)

    @property
    def collected(self):
        return self.specimen is not None

    @property
    def cancelled(self):
        return hasattr(self, "cancellation")

    def __str__(self):
        return f"Pedido {self.pk}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Pedidos não podem ser alterados.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Pedidos não podem ser excluídos.")


class Specimen(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service_request = models.ForeignKey(
        ServiceRequest, on_delete=models.PROTECT, related_name="specimens"
    )
    replaces = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="replaced_by"
    )
    accession_code = models.CharField(max_length=64, unique=True)
    collected_at = models.DateTimeField()
    collected_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    recorded_at = models.DateTimeField(auto_now_add=True)
    operation_key = models.UUIDField(unique=True)

    class Meta:
        ordering = ["-recorded_at", "-id"]

    def __str__(self):
        return f"Amostra {self.pk}"

    @property
    def status(self):
        kinds = {event.kind for event in self.events.all()}
        return next((k for k in ("REJECTED", "RECEIVED") if k in kinds), "COLLECTED")

    @property
    def rejection(self):
        return next((e for e in self.events.all() if e.kind == "REJECTED"), None)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Coletas não podem ser alteradas.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Coletas não podem ser excluídas.")


class SpecimenEvent(models.Model):
    class Kind(models.TextChoices):
        RECEIVED = "RECEIVED", "Recebida no laboratório"
        REJECTED = "REJECTED", "Rejeitada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    specimen = models.ForeignKey(Specimen, on_delete=models.PROTECT, related_name="events")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    reason = models.CharField(max_length=255, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    recorded_at = models.DateTimeField(auto_now_add=True)
    operation_key = models.UUIDField(unique=True)

    class Meta:
        ordering = ["recorded_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["specimen", "kind"], name="uniq_lis_specimen_event")
        ]

    def __str__(self):
        return f"Evento de amostra {self.pk}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Eventos de amostra não podem ser alterados.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Eventos de amostra não podem ser excluídos.")


class ServiceRequestCancellation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service_request = models.OneToOneField(
        ServiceRequest, on_delete=models.PROTECT, related_name="cancellation"
    )
    reason = models.CharField(max_length=255)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    cancelled_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Cancelamento {self.pk}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Cancelamentos não podem ser alterados.")
        return super().save(*args, **kwargs)


auditlog.register(LabTest, exclude_fields=["code", "name", "specimen_type"])
auditlog.register(ServiceRequest, exclude_fields=["test_code", "test_name", "specimen_type"])
auditlog.register(Specimen, exclude_fields=["accession_code"])
auditlog.register(SpecimenEvent, exclude_fields=["reason"])
auditlog.register(ServiceRequestCancellation, exclude_fields=["reason"])
