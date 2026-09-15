import uuid

from auditlog.registry import auditlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.clinical.pep.models import Encounter
from apps.clinical.prescription.models import MedicationDispenseItem


class VitalSignsRecord(models.Model):
    class Origin(models.TextChoices):
        ONLINE = "ONLINE", "Online"
        OFFLINE_SYNC = "OFFLINE_SYNC", "Sincronização offline"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.ForeignKey(
        Encounter,
        on_delete=models.PROTECT,
        related_name="nursing_vital_signs",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="nursing_vital_sign_records",
    )
    recorded_at = models.DateTimeField()
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    replaces = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="corrections",
    )
    origin = models.CharField(
        max_length=12,
        choices=Origin.choices,
        default=Origin.ONLINE,
    )

    temperature_c = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    heart_rate_bpm = models.PositiveIntegerField(null=True, blank=True)
    respiratory_rate_irpm = models.PositiveIntegerField(null=True, blank=True)
    systolic_bp_mmhg = models.PositiveIntegerField(null=True, blank=True)
    diastolic_bp_mmhg = models.PositiveIntegerField(null=True, blank=True)
    oxygen_saturation_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    weight_kg = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at", "-created_at"]
        indexes = [
            models.Index(fields=["encounter", "recorded_at"], name="nur_vitals_enc_time_idx"),
            models.Index(fields=["recorded_by", "recorded_at"], name="nur_vitals_user_time_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(temperature_c__isnull=False)
                    | Q(heart_rate_bpm__isnull=False)
                    | Q(respiratory_rate_irpm__isnull=False)
                    | Q(systolic_bp_mmhg__isnull=False)
                    | Q(diastolic_bp_mmhg__isnull=False)
                    | Q(oxygen_saturation_pct__isnull=False)
                    | Q(weight_kg__isnull=False)
                ),
                name="nur_vitals_any_measure",
            ),
            models.CheckConstraint(
                condition=Q(temperature_c__isnull=True) | Q(temperature_c__gt=0),
                name="nur_vitals_temperature_positive",
            ),
            models.CheckConstraint(
                condition=Q(heart_rate_bpm__isnull=True) | Q(heart_rate_bpm__gt=0),
                name="nur_vitals_hr_positive",
            ),
            models.CheckConstraint(
                condition=Q(respiratory_rate_irpm__isnull=True)
                | Q(respiratory_rate_irpm__gt=0),
                name="nur_vitals_rr_positive",
            ),
            models.CheckConstraint(
                condition=Q(systolic_bp_mmhg__isnull=True) | Q(systolic_bp_mmhg__gt=0),
                name="nur_vitals_sysbp_positive",
            ),
            models.CheckConstraint(
                condition=Q(diastolic_bp_mmhg__isnull=True)
                | Q(diastolic_bp_mmhg__gt=0),
                name="nur_vitals_diabp_positive",
            ),
            models.CheckConstraint(
                condition=Q(oxygen_saturation_pct__isnull=True)
                | (Q(oxygen_saturation_pct__gt=0) & Q(oxygen_saturation_pct__lte=100)),
                name="nur_vitals_spo2_range",
            ),
            models.CheckConstraint(
                condition=Q(weight_kg__isnull=True) | Q(weight_kg__gt=0),
                name="nur_vitals_weight_positive",
            ),
        ]
        permissions = [
            ("view_nursing", "Pode visualizar registros de enfermagem"),
            ("record_vitals", "Pode registrar sinais vitais"),
        ]

    def clean(self):
        super().clean()
        measures = (
            self.temperature_c,
            self.heart_rate_bpm,
            self.respiratory_rate_irpm,
            self.systolic_bp_mmhg,
            self.diastolic_bp_mmhg,
            self.oxygen_saturation_pct,
            self.weight_kg,
        )
        if not any(value is not None for value in measures):
            raise ValidationError("Informe ao menos uma medida clínica.")

        errors = {}
        for field_name in (
            "temperature_c",
            "heart_rate_bpm",
            "respiratory_rate_irpm",
            "systolic_bp_mmhg",
            "diastolic_bp_mmhg",
            "oxygen_saturation_pct",
            "weight_kg",
        ):
            value = getattr(self, field_name)
            if value is not None and value <= 0:
                errors[field_name] = "O valor deve ser maior que zero."

        if self.oxygen_saturation_pct is not None and self.oxygen_saturation_pct > 100:
            errors["oxygen_saturation_pct"] = "A saturação deve estar entre 0 e 100%."

        if self.replaces_id:
            if self.pk and self.replaces_id == self.pk:
                errors["replaces"] = "Um registro não pode substituir a si mesmo."
            elif self.replaces.encounter_id != self.encounter_id:
                errors["replaces"] = "A correção deve pertencer ao mesmo encontro."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Sinais vitais confirmados são append-only.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Sinais vitais confirmados não podem ser excluídos.")

    def __str__(self):
        return f"Sinais vitais {self.id}"


class MedicationAdministration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dispense_item = models.ForeignKey(
        MedicationDispenseItem,
        on_delete=models.PROTECT,
        related_name="nursing_administrations",
    )
    administered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="medication_administrations",
    )
    administered_at = models.DateTimeField()
    administered_dose = models.DecimalField(max_digits=12, decimal_places=4)
    administered_dose_unit = models.CharField(max_length=40)
    operation_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-administered_at", "-created_at"]
        indexes = [
            models.Index(
                fields=["dispense_item", "administered_at"],
                name="nur_admin_item_time_idx",
            ),
            models.Index(
                fields=["administered_by", "administered_at"],
                name="nur_admin_user_time_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(administered_dose__gt=0),
                name="nur_admin_dose_positive",
            )
        ]
        permissions = [
            ("administer_medication", "Pode administrar medicamentos"),
        ]

    def clean(self):
        super().clean()
        self.administered_dose_unit = " ".join((self.administered_dose_unit or "").split())
        errors = {}
        if self.administered_dose is not None and self.administered_dose <= 0:
            errors["administered_dose"] = "A dose administrada deve ser maior que zero."
        if not self.administered_dose_unit:
            errors["administered_dose_unit"] = "Informe a unidade da dose administrada."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Administrações confirmadas são append-only.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Administrações confirmadas não podem ser excluídas.")

    def __str__(self):
        return f"Administração {self.id}"


auditlog.register(
    VitalSignsRecord,
    exclude_fields=[
        "temperature_c",
        "heart_rate_bpm",
        "respiratory_rate_irpm",
        "systolic_bp_mmhg",
        "diastolic_bp_mmhg",
        "oxygen_saturation_pct",
        "weight_kg",
    ],
)
auditlog.register(
    MedicationAdministration,
    exclude_fields=["administered_dose", "administered_dose_unit"],
)
