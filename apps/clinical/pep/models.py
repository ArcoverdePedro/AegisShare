import uuid

from auditlog.registry import auditlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .validators import normalize_cpf, validate_cpf


class Patient(models.Model):
    class IdentifierType(models.TextChoices):
        CPF = "CPF", "CPF"
        OTHER = "OTHER", "Outro identificador"

    class Sex(models.TextChoices):
        FEMALE = "F", "Feminino"
        MALE = "M", "Masculino"
        INTERSEX = "I", "Intersexo"
        OTHER = "O", "Outro"
        UNKNOWN = "U", "Não informado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identifier_type = models.CharField(
        max_length=10,
        choices=IdentifierType.choices,
        default=IdentifierType.CPF,
    )
    identifier = models.CharField(max_length=64)
    full_name = models.CharField(max_length=255)
    birth_date = models.DateField()
    sex = models.CharField(max_length=1, choices=Sex.choices, default=Sex.UNKNOWN)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_patients",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name", "birth_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["identifier_type", "identifier"],
                name="uniq_pep_patient_identifier",
            )
        ]
        indexes = [
            models.Index(fields=["full_name"], name="pep_patient_name_idx"),
            models.Index(fields=["birth_date"], name="pep_patient_birth_idx"),
            models.Index(fields=["active"], name="pep_patient_active_idx"),
        ]

    def clean(self):
        super().clean()
        self.identifier = (self.identifier or "").strip()
        self.full_name = " ".join((self.full_name or "").split())

        if self.identifier_type == self.IdentifierType.CPF:
            self.identifier = normalize_cpf(self.identifier)
            validate_cpf(self.identifier)

        if self.birth_date and self.birth_date > timezone.localdate():
            raise ValidationError({"birth_date": "A data de nascimento não pode estar no futuro."})

        if not self.full_name:
            raise ValidationError({"full_name": "Informe o nome do paciente."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Paciente {self.id}"


class PatientAccessGrant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="access_grants",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patient_access_grants",
    )
    reason = models.CharField(max_length=255)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="granted_patient_accesses",
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "user"],
                name="uniq_pep_patient_access_user",
            )
        ]
        indexes = [
            models.Index(fields=["user", "expires_at"], name="pep_access_user_exp_idx"),
            models.Index(
                fields=["patient", "expires_at"],
                name="pep_access_patient_exp_idx",
            ),
        ]

    @property
    def is_active(self):
        return self.expires_at is None or self.expires_at > timezone.now()

    def clean(self):
        super().clean()
        self.reason = " ".join((self.reason or "").split())
        if not self.reason:
            raise ValidationError({"reason": "Informe a justificativa do acesso."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Acesso PEP {self.id}"


auditlog.register(
    Patient,
    exclude_fields=["identifier", "full_name", "birth_date", "phone", "email"],
)
auditlog.register(PatientAccessGrant, exclude_fields=["reason"])
