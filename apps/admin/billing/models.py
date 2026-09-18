import uuid
from decimal import Decimal

from auditlog.registry import auditlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class HospitalAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.OneToOneField("pep.Encounter", on_delete=models.PROTECT)
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    opened_at = models.DateTimeField(auto_now_add=True)
    operation_key = models.UUIDField()

    class Meta:
        ordering = ["-opened_at", "-id"]
        indexes = [models.Index(fields=["-opened_at", "-id"], name="billing_account_opened_idx")]
        constraints = [
            models.UniqueConstraint(fields=["operation_key"], name="uniq_billing_account_operation")
        ]
        permissions = [
            ("view_accounts", "Pode consultar contas em preparação"),
            ("open_account", "Pode abrir conta em preparação"),
            ("add_item", "Pode lançar item manual"),
        ]

    def __str__(self):
        return f"Conta {self.pk}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Contas não podem ser alteradas.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Contas não podem ser excluídas.")


class BillingItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(HospitalAccount, on_delete=models.PROTECT, related_name="items")
    description = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    recorded_at = models.DateTimeField(auto_now_add=True)
    operation_key = models.UUIDField()

    class Meta:
        ordering = ["-recorded_at", "-id"]
        indexes = [
            models.Index(fields=["account", "-recorded_at", "-id"], name="billing_item_account_idx")
        ]
        constraints = [
            models.UniqueConstraint(fields=["operation_key"], name="uniq_billing_item_operation"),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1, quantity__lte=999999),
                name="billing_item_quantity_range",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0, unit_price__lte=Decimal("9999999999.99")),
                name="billing_item_price_range",
            ),
        ]

    @property
    def subtotal(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"Item {self.pk}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Itens não podem ser alterados.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Itens não podem ser excluídos.")


auditlog.register(HospitalAccount)
auditlog.register(BillingItem, exclude_fields=["description", "quantity", "unit_price"])
