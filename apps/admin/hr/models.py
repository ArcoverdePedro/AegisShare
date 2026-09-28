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
        if not self._state.adding:
            original = Employee.objects.only("user_id").get(pk=self.pk)
            if original.user_id != self.user_id:
                raise ValidationError({"user": "O usuário associado não pode ser alterado."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Cadastros funcionais não podem ser excluídos.")


auditlog.register(Employee, exclude_fields=["department", "job_title"])
