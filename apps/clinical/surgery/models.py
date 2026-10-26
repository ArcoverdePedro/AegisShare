import uuid

from auditlog.registry import auditlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Procedure(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField("Código", max_length=64, unique=True)
    name = models.CharField("Nome", max_length=200)
    active = models.BooleanField("Ativo", default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"Procedimento {self.pk}"

    def clean(self):
        for field in ("code", "name"):
            value = getattr(self, field).strip()
            if not value:
                raise ValidationError({field: "Este campo é obrigatório."})
            setattr(self, field, value)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class SurgicalCase(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.ForeignKey("pep.Encounter", on_delete=models.PROTECT)
    procedure = models.ForeignKey(Procedure, on_delete=models.PROTECT)
    procedure_code = models.CharField(max_length=64)
    procedure_name = models.CharField(max_length=200)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    requested_at = models.DateTimeField(auto_now_add=True)
    operation_key = models.UUIDField()

    class Meta:
        ordering = ["-requested_at", "-id"]
        indexes = [models.Index(fields=["-requested_at", "-id"], name="surgery_requested_idx")]
        constraints = [
            models.UniqueConstraint(fields=["operation_key"], name="uniq_surgery_operation_key")
        ]
        permissions = [
            ("view_cases", "Pode consultar solicitações de procedimentos"),
            ("request_procedure", "Pode solicitar procedimento"),
        ]

    def __str__(self):
        return f"Solicitação {self.pk}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Solicitações não podem ser alteradas.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Solicitações não podem ser excluídas.")


class OperatingRoom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField("Código", max_length=40, unique=True)
    name = models.CharField("Nome", max_length=120)
    active = models.BooleanField("Ativa", default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} · {self.name}"


class SurgerySchedule(models.Model):
    """Reserva de sala/cirurgiao; agendar nao equivale a autorizacao clinica (G08)."""

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Agendada"
        RESCHEDULED = "RESCHEDULED", "Remarcada"
        CANCELLED = "CANCELLED", "Cancelada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(SurgicalCase, on_delete=models.PROTECT, related_name="schedules")
    room = models.ForeignKey(OperatingRoom, on_delete=models.PROTECT, related_name="schedules")
    surgeon = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="surgery_schedules"
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SCHEDULED)
    reason = models.CharField(max_length=255, blank=True)
    rescheduled_from = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="rescheduled_to"
    )
    scheduled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    operation_key = models.UUIDField(unique=True)

    class Meta:
        ordering = ["starts_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="surgery_schedule_valid_period",
            ),
            models.UniqueConstraint(
                fields=["case"],
                condition=models.Q(status="SCHEDULED"),
                name="uniq_surgery_active_schedule",
            ),
        ]
        permissions = [("schedule_case", "Pode agendar, remarcar e cancelar cirurgia")]

    def __str__(self):
        return f"Agendamento cirúrgico {self.pk}"


auditlog.register(Procedure, exclude_fields=["code", "name"])
auditlog.register(SurgicalCase, exclude_fields=["procedure_code", "procedure_name"])
auditlog.register(OperatingRoom)
auditlog.register(SurgerySchedule, exclude_fields=["reason"])
