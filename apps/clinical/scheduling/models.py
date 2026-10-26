import uuid

from auditlog.registry import auditlog
from django.conf import settings
from django.db import models

from apps.clinical.pep.models import Encounter, Patient


class AgendaSlot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="agenda_slots"
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    capacity = models.PositiveSmallIntegerField(default=1)
    location = models.CharField("Unidade/consultório", max_length=160)
    blocked_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at", "professional_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["professional", "starts_at"], name="uniq_scheduling_slot_start"
            ),
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at"), capacity__gte=1),
                name="scheduling_slot_valid",
            ),
        ]
        permissions = [
            ("view_agenda", "Pode consultar agenda e fila ambulatorial"),
            ("manage_agenda", "Pode abrir e bloquear horários"),
            ("book_appointment", "Pode agendar, remarcar e cancelar"),
            ("overbook_appointment", "Pode autorizar encaixe acima da capacidade"),
            ("checkin_appointment", "Pode registrar chegada, chamada e falta"),
        ]

    def __str__(self):
        return f"Horário {self.pk}"


class Appointment(models.Model):
    class Status(models.TextChoices):
        BOOKED = "BOOKED", "Agendado"
        CHECKED_IN = "CHECKED_IN", "Chegou"
        CALLED = "CALLED", "Chamado"
        CANCELLED = "CANCELLED", "Cancelado"
        RESCHEDULED = "RESCHEDULED", "Remarcado"
        NO_SHOW = "NO_SHOW", "Falta"

    ACTIVE = [Status.BOOKED, Status.CHECKED_IN, Status.CALLED]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slot = models.ForeignKey(AgendaSlot, on_delete=models.PROTECT, related_name="appointments")
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="appointments")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.BOOKED)
    overbooked = models.BooleanField(default=False)
    reason = models.CharField(max_length=255, blank=True)
    rescheduled_from = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="rescheduled_to"
    )
    encounter = models.OneToOneField(
        Encounter, null=True, blank=True, on_delete=models.PROTECT, related_name="appointment"
    )
    booked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    booked_at = models.DateTimeField(auto_now_add=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    called_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    operation_key = models.UUIDField(unique=True)

    class Meta:
        ordering = ["slot__starts_at", "booked_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["slot", "patient"],
                condition=models.Q(status__in=["BOOKED", "CHECKED_IN", "CALLED"]),
                name="uniq_scheduling_active_patient_slot",
            )
        ]

    def __str__(self):
        return f"Agendamento {self.pk}"

    @property
    def ticket(self):
        """Senha curta para chamada sem expor nome em telas compartilhadas."""
        return str(self.pk)[:6].upper()


auditlog.register(AgendaSlot, exclude_fields=["blocked_reason"])
auditlog.register(Appointment, exclude_fields=["reason"])
