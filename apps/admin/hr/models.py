import uuid

from auditlog.registry import auditlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Employee(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    department = models.CharField("Setor", max_length=120)
    job_title = models.CharField("Função", max_length=120)
    active = models.BooleanField("Cadastro ativo", default=True)
    council = models.CharField("Conselho (ex.: CRM, COREN)", max_length=20, blank=True)
    registration_number = models.CharField("Número do registro", max_length=30, blank=True)
    registration_state = models.CharField("UF do registro", max_length=2, blank=True)
    registration_valid_until = models.DateField("Registro válido até", null=True, blank=True)
    specialty = models.CharField("Especialidade", max_length=120, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"Cadastro funcional {self.pk}"

    def clean(self):
        for field in ("department", "job_title"):
            value = getattr(self, field).strip()
            if not value:
                raise ValidationError({field: "Este campo é obrigatório."})
            setattr(self, field, value)
        self.council = self.council.strip().upper()
        self.registration_state = self.registration_state.strip().upper()
        self.registration_number = self.registration_number.strip()
        if self.registration_number and not (self.council and self.registration_state):
            raise ValidationError({"council": "Informe conselho e UF do registro."})
        if not self._state.adding:
            original = Employee.objects.only("user_id").get(pk=self.pk)
            if original.user_id != self.user_id:
                raise ValidationError({"user": "O usuário associado não pode ser alterado."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Cadastros funcionais não podem ser excluídos.")


class EmployeeAbsence(models.Model):
    class Kind(models.TextChoices):
        VACATION = "VACATION", "Férias"
        LEAVE = "LEAVE", "Licença/afastamento"
        OTHER = "OTHER", "Outro"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="absences")
    kind = models.CharField("Tipo", max_length=10, choices=Kind.choices)
    starts_on = models.DateField("Início")
    ends_on = models.DateField("Fim")

    class Meta:
        ordering = ["-starts_on"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_on__gte=models.F("starts_on")),
                name="hr_absence_valid_period",
            )
        ]

    def __str__(self):
        return f"Ausência {self.pk}"


def absent_on(user, day):
    """Ausência registrada impede abrir ou ocupar horários de agenda do profissional."""
    return EmployeeAbsence.objects.filter(
        employee__user=user, starts_on__lte=day, ends_on__gte=day
    ).exists()


auditlog.register(Employee, exclude_fields=["department", "job_title"])
auditlog.register(EmployeeAbsence)
