import uuid

from auditlog.registry import auditlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class PatientExportReceipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey("pep.Patient", on_delete=models.PROTECT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    contract_version = models.CharField(max_length=32, default="patient-r4-v1", editable=False)
    content_sha256 = models.CharField(max_length=64, editable=False)

    class Meta:
        permissions = [("export_patient", "Pode exportar cadastro mínimo de paciente")]

    def __str__(self):
        return f"Exportação {self.pk}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Recibos de exportação são imutáveis.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Recibos de exportação não podem ser excluídos.")


auditlog.register(PatientExportReceipt)
