import uuid

from auditlog.registry import auditlog
from django.core.exceptions import ValidationError
from django.db import models


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

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Leito {self.code}"


auditlog.register(Location)
auditlog.register(Bed)
