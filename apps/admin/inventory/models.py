import uuid

from auditlog.registry import auditlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class InventoryItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField("Código", max_length=64, unique=True)
    name = models.CharField("Nome", max_length=200)
    unit = models.CharField("Unidade de contagem", max_length=40)
    active = models.BooleanField("Ativo", default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"Material {self.pk}"

    def clean(self):
        for field in ("code", "name", "unit"):
            value = getattr(self, field).strip()
            if not value:
                raise ValidationError({field: "Este campo é obrigatório."})
            setattr(self, field, value)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Requisition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT)
    item_code = models.CharField(max_length=64)
    item_name = models.CharField(max_length=200)
    item_unit = models.CharField(max_length=40)
    quantity = models.PositiveIntegerField()
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    requested_at = models.DateTimeField(auto_now_add=True)
    operation_key = models.UUIDField()

    class Meta:
        ordering = ["-requested_at", "-id"]
        indexes = [models.Index(fields=["-requested_at", "-id"], name="inventory_req_created_idx")]
        constraints = [
            models.UniqueConstraint(fields=["operation_key"], name="uniq_inventory_req_operation"),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1, quantity__lte=999999),
                name="inventory_req_qty_range",
            ),
        ]
        permissions = [
            ("view_requisitions", "Pode consultar catálogo e requisições institucionais"),
            ("request_material", "Pode requisitar material"),
        ]

    def __str__(self):
        return f"Requisição {self.pk}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Requisições não podem ser alteradas.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Requisições não podem ser excluídas.")


auditlog.register(InventoryItem, exclude_fields=["code", "name", "unit"])
auditlog.register(Requisition, exclude_fields=["item_code", "item_name", "item_unit", "quantity"])
