import uuid

from auditlog.registry import auditlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.clinical.pep.models import Encounter


class Drug(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    presentation = models.CharField(max_length=255)
    strength_text = models.CharField(max_length=120, blank=True)
    route_hint = models.CharField(max_length=120, blank=True)
    dispense_unit = models.CharField(max_length=40)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "presentation", "code"]
        indexes = [models.Index(fields=["active", "name"], name="rx_drug_active_name_idx")]
        permissions = [("manage_drug_catalog", "Pode manter catálogo farmacêutico")]

    def clean(self):
        super().clean()
        self.code = (self.code or "").strip().upper()
        self.name = " ".join((self.name or "").split())
        self.presentation = " ".join((self.presentation or "").split())
        self.strength_text = " ".join((self.strength_text or "").split())
        self.route_hint = " ".join((self.route_hint or "").split())
        self.dispense_unit = " ".join((self.dispense_unit or "").split())
        errors = {}
        if not self.code:
            errors["code"] = "Informe o código do medicamento."
        if not self.name:
            errors["name"] = "Informe o nome do medicamento."
        if not self.presentation:
            errors["presentation"] = "Informe a apresentação."
        if not self.dispense_unit:
            errors["dispense_unit"] = "Informe a unidade de dispensação."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Medicamento {self.code}"


class Interaction(models.Model):
    class Severity(models.TextChoices):
        INFO = "INFO", "Informativa"
        MINOR = "MINOR", "Leve"
        MODERATE = "MODERATE", "Moderada"
        MAJOR = "MAJOR", "Grave"
        CONTRAINDICATED = "CONTRAINDICATED", "Contraindicada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    drug_a = models.ForeignKey(Drug, on_delete=models.PROTECT, related_name="interactions_as_a")
    drug_b = models.ForeignKey(Drug, on_delete=models.PROTECT, related_name="interactions_as_b")
    severity = models.CharField(max_length=20, choices=Severity.choices)
    blocking = models.BooleanField(default=False)
    summary = models.TextField()
    reference_source = models.CharField(max_length=255, blank=True)
    reference_version = models.CharField(max_length=120, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approved_drug_interactions",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(drug_a=F("drug_b")),
                name="rx_interaction_distinct_drugs",
            ),
            models.UniqueConstraint(
                fields=["drug_a", "drug_b", "reference_version"],
                name="uniq_rx_interaction_pair_version",
            ),
        ]
        indexes = [
            models.Index(
                fields=["drug_a", "drug_b", "active"],
                name="rx_interaction_pair_idx",
            )
        ]

    def clean(self):
        super().clean()
        self.reference_source = " ".join((self.reference_source or "").split())
        self.reference_version = " ".join((self.reference_version or "").split())
        self.summary = (self.summary or "").strip()
        if self.drug_a_id and self.drug_b_id and str(self.drug_a_id) > str(self.drug_b_id):
            self.drug_a_id, self.drug_b_id = self.drug_b_id, self.drug_a_id
        if self.drug_a_id and self.drug_a_id == self.drug_b_id:
            raise ValidationError("Uma interação exige dois medicamentos distintos.")
        if not self.summary:
            raise ValidationError({"summary": "Informe o resumo governado da interação."})
        if self.active and not all(
            [self.reference_source, self.reference_version, self.approved_by_id, self.approved_at]
        ):
            raise ValidationError("Interação ativa exige fonte, versão e aprovação explícita.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Interação {self.id}"


class DoseRule(models.Model):
    class Basis(models.TextChoices):
        AGE = "AGE", "Idade"
        WEIGHT = "WEIGHT", "Peso"
        AGE_AND_WEIGHT = "AGE_AND_WEIGHT", "Idade e peso"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    drug = models.ForeignKey(Drug, on_delete=models.PROTECT, related_name="dose_rules")
    rule_code = models.CharField(max_length=64)
    basis = models.CharField(max_length=20, choices=Basis.choices)
    min_age_days = models.PositiveIntegerField(null=True, blank=True)
    max_age_days = models.PositiveIntegerField(null=True, blank=True)
    min_weight_kg = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    max_weight_kg = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    min_dose = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    max_dose = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    dose_unit = models.CharField(max_length=40)
    per_kg = models.BooleanField(default=False)
    reference_source = models.CharField(max_length=255, blank=True)
    reference_version = models.CharField(max_length=120, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approved_dose_rules",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["drug", "rule_code", "reference_version"],
                name="uniq_rx_dose_rule_version",
            )
        ]
        indexes = [models.Index(fields=["drug", "active"], name="rx_dose_drug_active_idx")]

    def clean(self):
        super().clean()
        self.rule_code = (self.rule_code or "").strip().upper()
        self.dose_unit = " ".join((self.dose_unit or "").split())
        self.reference_source = " ".join((self.reference_source or "").split())
        self.reference_version = " ".join((self.reference_version or "").split())
        errors = {}
        for minimum, maximum, field in [
            (self.min_age_days, self.max_age_days, "max_age_days"),
            (self.min_weight_kg, self.max_weight_kg, "max_weight_kg"),
            (self.min_dose, self.max_dose, "max_dose"),
        ]:
            if minimum is not None and maximum is not None and minimum > maximum:
                errors[field] = "O limite máximo não pode ser menor que o mínimo."
        if self.basis == self.Basis.AGE and (
            self.min_weight_kg is not None or self.max_weight_kg is not None or self.per_kg
        ):
            errors["basis"] = "Regra baseada somente em idade não pode depender de peso."
        if self.basis == self.Basis.WEIGHT and (
            self.min_age_days is not None or self.max_age_days is not None
        ):
            errors["basis"] = "Regra baseada somente em peso não pode depender de idade."
        if not self.rule_code:
            errors["rule_code"] = "Informe o código da regra."
        if not self.dose_unit:
            errors["dose_unit"] = "Informe a unidade de dose."
        if self.active and not all(
            [self.reference_source, self.reference_version, self.approved_by_id, self.approved_at]
        ):
            errors["active"] = "Regra ativa exige fonte, versão e aprovação explícita."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Regra de dose {self.rule_code}"


class MedicationRequest(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        SUBMITTED = "SUBMITTED", "Submetida"
        VALIDATED = "VALIDATED", "Validada"
        CANCELLED = "CANCELLED", "Cancelada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.ForeignKey(
        Encounter,
        on_delete=models.PROTECT,
        related_name="medication_requests",
    )
    authored_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="authored_medication_requests",
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    replaces = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="replacements",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="validated_medication_requests",
    )
    validated_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="cancelled_medication_requests",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["encounter", "created_at"], name="rx_request_enc_created_idx"),
            models.Index(fields=["status", "created_at"], name="rx_request_status_idx"),
            models.Index(fields=["authored_by", "created_at"], name="rx_request_author_idx"),
        ]
        permissions = [
            ("view_medication_request", "Pode visualizar prescrições"),
            ("prescribe_medication", "Pode prescrever medicamentos"),
            ("validate_medication_request", "Pode validar prescrições"),
            ("cancel_medication_request", "Pode cancelar prescrições"),
        ]

    def clean(self):
        super().clean()
        self.cancellation_reason = " ".join((self.cancellation_reason or "").split())
        if (
            self.encounter_id
            and self.status in {self.Status.DRAFT, self.Status.SUBMITTED}
            and self.encounter.status != Encounter.Status.OPEN
        ):
            raise ValidationError({"encounter": "Prescrição nova exige encontro aberto."})
        if self.replaces_id and self.replaces.encounter_id != self.encounter_id:
            raise ValidationError({"replaces": "A substituição deve pertencer ao mesmo encontro."})
        if self.status == self.Status.SUBMITTED and not self.submitted_at:
            raise ValidationError({"submitted_at": "Prescrição submetida exige horário de submissão."})
        if self.status == self.Status.VALIDATED and not (self.validated_by_id and self.validated_at):
            raise ValidationError("Prescrição validada exige responsável e horário de validação.")
        if self.status == self.Status.CANCELLED and not (
            self.cancelled_by_id and self.cancelled_at and self.cancellation_reason
        ):
            raise ValidationError("Prescrição cancelada exige ator, horário e motivo.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Prescrição {self.id}"


class MedicationRequestItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    medication_request = models.ForeignKey(
        MedicationRequest,
        on_delete=models.PROTECT,
        related_name="items",
    )
    drug = models.ForeignKey(Drug, on_delete=models.PROTECT, related_name="request_items")
    dose = models.DecimalField(max_digits=12, decimal_places=4)
    dose_unit = models.CharField(max_length=40)
    route = models.CharField(max_length=80)
    frequency = models.CharField(max_length=120)
    duration_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    duration_unit = models.CharField(max_length=40, blank=True)
    instructions = models.TextField(blank=True)
    sequence = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sequence", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["medication_request", "sequence"],
                name="uniq_rx_request_item_sequence",
            ),
            models.CheckConstraint(condition=Q(dose__gt=0), name="rx_request_item_dose_positive"),
        ]
        indexes = [
            models.Index(
                fields=["medication_request", "sequence"],
                name="rx_request_item_seq_idx",
            )
        ]

    def clean(self):
        super().clean()
        self.dose_unit = " ".join((self.dose_unit or "").split())
        self.route = " ".join((self.route or "").split())
        self.frequency = " ".join((self.frequency or "").split())
        self.duration_unit = " ".join((self.duration_unit or "").split())
        self.instructions = (self.instructions or "").strip()
        if self.dose is not None and self.dose <= 0:
            raise ValidationError({"dose": "A dose deve ser maior que zero."})
        if self.drug_id and not self.drug.active and self._state.adding:
            raise ValidationError({"drug": "Medicamento inativo não pode ser prescrito."})
        if (
            self.medication_request_id
            and self.medication_request.status != MedicationRequest.Status.DRAFT
        ):
            raise ValidationError("Itens só podem ser alterados enquanto a prescrição está em rascunho.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.medication_request.status != MedicationRequest.Status.DRAFT:
            raise ValidationError("Itens submetidos não podem ser excluídos.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"Item de prescrição {self.id}"


class MedicationSafetyReview(models.Model):
    class AllergyStatus(models.TextChoices):
        UNAVAILABLE = "UNAVAILABLE", "Indisponível"
        REVIEW_REQUIRED = "REVIEW_REQUIRED", "Revisão manual necessária"
        REVIEW_CONFIRMED = "REVIEW_CONFIRMED", "Revisão manual confirmada"
        STRUCTURED_CHECKED = "STRUCTURED_CHECKED", "Checagem estruturada"

    class DoseStatus(models.TextChoices):
        PASS = "PASS", "Aprovada"
        BLOCKED = "BLOCKED", "Bloqueada"
        NOT_EVALUABLE = "NOT_EVALUABLE", "Não avaliável"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    medication_request = models.ForeignKey(
        MedicationRequest,
        on_delete=models.PROTECT,
        related_name="safety_reviews",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="medication_safety_reviews",
    )
    allergy_status = models.CharField(max_length=20, choices=AllergyStatus.choices)
    dose_status = models.CharField(max_length=20, choices=DoseStatus.choices)
    blocking_findings = models.PositiveIntegerField(default=0)
    warning_findings = models.PositiveIntegerField(default=0)
    reference_version = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["medication_request", "created_at"],
                name="rx_review_request_idx",
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Revisões de segurança são append-only.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Revisões de segurança concluídas não podem ser excluídas.")

    def __str__(self):
        return f"Revisão farmacêutica {self.id}"


class MedicationSafetyFinding(models.Model):
    class Kind(models.TextChoices):
        INTERACTION = "INTERACTION", "Interação"
        ALLERGY = "ALLERGY", "Alergia"
        DOSE = "DOSE", "Dose"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(
        MedicationSafetyReview,
        on_delete=models.PROTECT,
        related_name="findings",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    request_item = models.ForeignKey(
        MedicationRequestItem,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="safety_findings",
    )
    interaction = models.ForeignKey(
        Interaction,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="findings",
    )
    dose_rule = models.ForeignKey(
        DoseRule,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="findings",
    )
    severity = models.CharField(max_length=32)
    blocking = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Achados de segurança são append-only.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Achados de segurança não podem ser excluídos.")

    def __str__(self):
        return f"Achado farmacêutico {self.id}"


class StockItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    drug = models.ForeignKey(Drug, on_delete=models.PROTECT, related_name="stock_items")
    storage_location = models.CharField(max_length=160)
    minimum_level = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["drug", "storage_location"],
                name="uniq_rx_stock_location",
            ),
            models.CheckConstraint(
                condition=Q(minimum_level__gte=0),
                name="rx_stock_min_nonnegative",
            ),
        ]
        permissions = [
            ("view_pharmacy_stock", "Pode consultar estoque farmacêutico"),
            ("manage_pharmacy_stock", "Pode gerenciar estoque farmacêutico"),
        ]

    def clean(self):
        super().clean()
        self.storage_location = " ".join((self.storage_location or "").split())
        if not self.storage_location:
            raise ValidationError({"storage_location": "Informe a localização do estoque."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Estoque {self.id}"


class Lot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stock_item = models.ForeignKey(StockItem, on_delete=models.PROTECT, related_name="lots")
    lot_number = models.CharField(max_length=120)
    expires_on = models.DateField()
    quantity_available = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["stock_item", "lot_number"],
                name="uniq_rx_lot_number",
            ),
            models.CheckConstraint(
                condition=Q(quantity_available__gte=0),
                name="rx_lot_quantity_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=["stock_item", "expires_on", "active"],
                name="rx_lot_expiry_idx",
            )
        ]

    def clean(self):
        super().clean()
        self.lot_number = " ".join((self.lot_number or "").split())
        if not self.lot_number:
            raise ValidationError({"lot_number": "Informe o lote."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Lote {self.id}"


class MedicationDispense(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    medication_request = models.ForeignKey(
        MedicationRequest,
        on_delete=models.PROTECT,
        related_name="dispenses",
    )
    dispensed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="medication_dispenses",
    )
    operation_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    dispensed_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-dispensed_at", "-created_at"]
        indexes = [
            models.Index(
                fields=["medication_request", "dispensed_at"],
                name="rx_dispense_request_idx",
            )
        ]
        permissions = [
            ("view_medication_dispense", "Pode visualizar dispensações"),
            ("dispense_medication", "Pode dispensar medicamentos"),
        ]

    def clean(self):
        super().clean()
        if (
            self.medication_request_id
            and self.medication_request.status != MedicationRequest.Status.VALIDATED
        ):
            raise ValidationError(
                {"medication_request": "A dispensação exige prescrição validada."}
            )

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Dispensações concluídas são append-only.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Dispensações concluídas não podem ser excluídas.")

    def __str__(self):
        return f"Dispensação {self.id}"


class MedicationDispenseItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dispense = models.ForeignKey(
        MedicationDispense,
        on_delete=models.PROTECT,
        related_name="items",
    )
    request_item = models.ForeignKey(
        MedicationRequestItem,
        on_delete=models.PROTECT,
        related_name="dispense_items",
    )
    lot = models.ForeignKey(Lot, on_delete=models.PROTECT, related_name="dispense_items")
    quantity = models.DecimalField(max_digits=14, decimal_places=4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="rx_dispense_item_quantity_positive",
            )
        ]

    def clean(self):
        super().clean()
        if self.quantity is not None and self.quantity <= 0:
            raise ValidationError({"quantity": "A quantidade deve ser maior que zero."})
        if (
            self.lot_id
            and self.request_item_id
            and self.lot.stock_item.drug_id != self.request_item.drug_id
        ):
            raise ValidationError({"lot": "O lote não corresponde ao medicamento prescrito."})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Itens dispensados são append-only.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Itens dispensados não podem ser excluídos.")

    def __str__(self):
        return f"Item dispensado {self.id}"


class StockMovement(models.Model):
    class Type(models.TextChoices):
        DISPENSE = "DISPENSE", "Dispensação"
        RECEIPT = "RECEIPT", "Entrada"
        ADJUSTMENT = "ADJUSTMENT", "Ajuste"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lot = models.ForeignKey(Lot, on_delete=models.PROTECT, related_name="movements")
    movement_type = models.CharField(max_length=12, choices=Type.choices)
    quantity_delta = models.DecimalField(max_digits=14, decimal_places=4)
    dispense_item = models.OneToOneField(
        MedicationDispenseItem,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_movement",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pharmacy_stock_movements",
    )
    operation_key = models.UUIDField(default=uuid.uuid4)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(quantity_delta=0),
                name="rx_stock_movement_nonzero",
            )
        ]
        indexes = [
            models.Index(fields=["lot", "created_at"], name="rx_stock_move_lot_idx"),
            models.Index(fields=["operation_key"], name="rx_stock_move_operation_idx"),
        ]

    def clean(self):
        super().clean()
        self.reason = " ".join((self.reason or "").split())
        if self.movement_type == self.Type.DISPENSE:
            if self.quantity_delta is not None and self.quantity_delta >= 0:
                raise ValidationError({"quantity_delta": "Dispensação exige delta negativo."})
            if not self.dispense_item_id:
                raise ValidationError(
                    {"dispense_item": "Movimento de dispensação exige item dispensado."}
                )
        if self.movement_type == self.Type.ADJUSTMENT and not self.reason:
            raise ValidationError({"reason": "Ajuste manual exige justificativa."})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Movimentos de estoque são append-only.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Movimentos de estoque não podem ser excluídos.")

    def __str__(self):
        return f"Movimento de estoque {self.id}"


auditlog.register(Drug)
auditlog.register(Interaction, exclude_fields=["summary"])
auditlog.register(DoseRule)
auditlog.register(MedicationRequest, exclude_fields=["cancellation_reason"])
auditlog.register(MedicationRequestItem, exclude_fields=["instructions"])
auditlog.register(MedicationSafetyReview)
auditlog.register(MedicationSafetyFinding)
auditlog.register(StockItem)
auditlog.register(Lot)
auditlog.register(MedicationDispense)
auditlog.register(MedicationDispenseItem)
auditlog.register(StockMovement, exclude_fields=["reason"])
