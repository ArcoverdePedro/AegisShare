import uuid

from auditlog.registry import auditlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.clinical.pep.models import Encounter


class Location(models.Model):
    class Kind(models.TextChoices):
        UNIT = "UNIT", "Unidade"
        WARD = "WARD", "Setor"
        ROOM = "ROOM", "Quarto"
        OTHER = "OTHER", "Outro"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=160)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.OTHER)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "code"]
        indexes = [models.Index(fields=["active"], name="adt_location_active_idx")]

    def clean(self):
        super().clean()
        self.code = (self.code or "").strip().upper()
        self.name = " ".join((self.name or "").split())
        if not self.code:
            raise ValidationError({"code": "Informe o código da localização."})
        if not self.name:
            raise ValidationError({"name": "Informe o nome da localização."})
        if self.parent_id and self.parent_id == self.id:
            raise ValidationError({"parent": "A localização não pode ser pai de si própria."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Local {self.code}"


class Bed(models.Model):
    class OperationalStatus(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Disponível"
        BLOCKED = "BLOCKED", "Bloqueado"
        OUT_OF_SERVICE = "OUT_OF_SERVICE", "Fora de serviço"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="beds")
    code = models.CharField(max_length=40)
    label = models.CharField(max_length=120)
    operational_status = models.CharField(
        max_length=20,
        choices=OperationalStatus.choices,
        default=OperationalStatus.AVAILABLE,
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["location__name", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["location", "code"],
                name="uniq_adt_bed_location_code",
            )
        ]
        indexes = [
            models.Index(
                fields=["location", "operational_status"],
                name="adt_bed_loc_status_idx",
            ),
            models.Index(fields=["active"], name="adt_bed_active_idx"),
        ]
        permissions = [
            ("view_bed_map", "Pode visualizar mapa de leitos"),
            ("manage_bed_status", "Pode alterar estado operacional de leitos"),
        ]

    def clean(self):
        super().clean()
        self.code = (self.code or "").strip().upper()
        self.label = " ".join((self.label or "").split())
        if not self.code:
            raise ValidationError({"code": "Informe o código do leito."})
        if not self.label:
            raise ValidationError({"label": "Informe a identificação do leito."})

    @property
    def current_status(self):
        if self.occupancies.filter(ended_at__isnull=True).exists():
            return "OCCUPIED"
        return self.operational_status

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Leito {self.code}"


class Admission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.OneToOneField(
        Encounter,
        on_delete=models.PROTECT,
        related_name="adt_admission",
    )
    admitted_at = models.DateTimeField()
    admitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="adt_admissions_created",
    )
    operation_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-admitted_at", "-created_at"]
        indexes = [models.Index(fields=["admitted_at"], name="adt_admission_time_idx")]
        permissions = [
            ("admit_patient", "Pode admitir paciente"),
            ("view_movement_history", "Pode visualizar histórico de movimentação ADT"),
        ]

    def clean(self):
        super().clean()
        if not self.encounter_id:
            return
        if self.encounter.encounter_type != Encounter.Type.INPATIENT:
            raise ValidationError({"encounter": "A admissão exige encontro do tipo internação."})
        if self.encounter.status != Encounter.Status.OPEN:
            raise ValidationError({"encounter": "A admissão exige encontro aberto."})
        if self.admitted_at and self.admitted_at < self.encounter.started_at:
            raise ValidationError(
                {"admitted_at": "A admissão não pode ser anterior ao início do encontro."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Admissão {self.id}"


class BedOccupancy(models.Model):
    class EndReason(models.TextChoices):
        TRANSFER = "TRANSFER", "Transferência"
        DISCHARGE = "DISCHARGE", "Alta"
        CORRECTION = "CORRECTION", "Correção"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admission = models.ForeignKey(
        Admission,
        on_delete=models.PROTECT,
        related_name="occupancies",
    )
    bed = models.ForeignKey(Bed, on_delete=models.PROTECT, related_name="occupancies")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="adt_occupancies_started",
    )
    ended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="adt_occupancies_ended",
    )
    end_reason = models.CharField(max_length=12, choices=EndReason.choices, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["started_at", "created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(ended_at__isnull=True) | Q(ended_at__gte=F("started_at")),
                name="adt_occ_end_after_start",
            ),
            models.UniqueConstraint(
                fields=["bed"],
                condition=Q(ended_at__isnull=True),
                name="uniq_adt_active_bed_occ",
            ),
            models.UniqueConstraint(
                fields=["admission"],
                condition=Q(ended_at__isnull=True),
                name="uniq_adt_active_adm_occ",
            ),
        ]
        indexes = [
            models.Index(fields=["bed", "ended_at"], name="adt_occ_bed_end_idx"),
            models.Index(
                fields=["admission", "ended_at"],
                name="adt_occ_adm_end_idx",
            ),
        ]

    def clean(self):
        super().clean()
        if self.ended_at and self.ended_at < self.started_at:
            raise ValidationError({"ended_at": "O fim não pode ser anterior ao início."})
        if self.ended_at and (not self.ended_by_id or not self.end_reason):
            raise ValidationError("O encerramento exige responsável e motivo.")
        if not self.ended_at and (self.ended_by_id or self.end_reason):
            raise ValidationError("Ocupação ativa não pode possuir dados de encerramento.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Ocupação {self.id}"


auditlog.register(Location)
auditlog.register(Bed)
auditlog.register(Admission)
auditlog.register(BedOccupancy)
