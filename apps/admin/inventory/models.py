import uuid
from decimal import Decimal

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


class StockLocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField("Código", max_length=64, unique=True)
    name = models.CharField("Nome", max_length=200)
    active = models.BooleanField("Ativo", default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} · {self.name}"


class MaterialBalance(models.Model):
    """Saldo por material/local/lote; alterado somente junto de um MaterialMovement."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="balances")
    location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, related_name="balances")
    lot = models.CharField("Lote", max_length=120, blank=True)
    expires_on = models.DateField("Validade", null=True, blank=True)
    quantity = models.IntegerField(default=0)

    class Meta:
        ordering = ["item__code", "location__code", "expires_on", "lot"]
        constraints = [
            models.UniqueConstraint(
                fields=["item", "location", "lot"], name="uniq_inventory_balance"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0), name="inventory_balance_nonnegative"
            ),
        ]
        permissions = [
            ("move_stock", "Pode registrar entrada, saída, transferência e devolução de materiais"),
            ("adjust_stock", "Pode registrar ajuste de inventário e estorno de movimento"),
        ]

    def __str__(self):
        return f"Saldo {self.pk}"


class MaterialMovement(models.Model):
    class Kind(models.TextChoices):
        RECEIPT = "RECEIPT", "Entrada"
        ISSUE = "ISSUE", "Saída/entrega"
        RETURN = "RETURN", "Devolução ao estoque"
        TRANSFER_OUT = "TRANSFER_OUT", "Transferência (saída)"
        TRANSFER_IN = "TRANSFER_IN", "Transferência (entrada)"
        ADJUSTMENT = "ADJUSTMENT", "Ajuste de inventário"
        REVERSAL = "REVERSAL", "Estorno"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    balance = models.ForeignKey(MaterialBalance, on_delete=models.PROTECT, related_name="movements")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    quantity_delta = models.IntegerField()
    requisition = models.ForeignKey(
        Requisition, null=True, blank=True, on_delete=models.PROTECT, related_name="movements"
    )
    reverses = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversed_by"
    )
    reason = models.CharField(max_length=255, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="material_movements"
    )
    operation_key = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            # Transferencia grava duas pernas com a mesma chave, uma por local.
            models.UniqueConstraint(
                fields=["operation_key", "balance"], name="uniq_inventory_movement_operation"
            ),
            models.CheckConstraint(
                condition=~models.Q(quantity_delta=0), name="inventory_movement_nonzero"
            ),
        ]

    def __str__(self):
        return f"Movimento {self.pk}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Movimentos não podem ser alterados; registre um estorno.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Movimentos não podem ser excluídos; registre um estorno.")


class Supplier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.CharField("CNPJ/CPF", max_length=18, unique=True)
    name = models.CharField("Razão social", max_length=200)
    active = models.BooleanField("Ativo", default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.document})"


class PurchaseOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Aguardando aprovação"
        APPROVED = "APPROVED", "Aprovado"
        PARTIAL = "PARTIAL", "Recebido parcialmente"
        RECEIVED = "RECEIVED", "Recebido"
        CANCELLED = "CANCELLED", "Cancelado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    notes = models.CharField("Justificativa", max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="purchase_orders"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approved_purchase_orders",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="cancelled_purchase_orders",
    )
    cancel_reason = models.CharField(max_length=255, blank=True)
    operation_key = models.UUIDField(unique=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        permissions = [
            ("view_purchases", "Pode consultar fornecedores e pedidos de compra"),
            ("request_purchase", "Pode registrar pedido de compra"),
            ("approve_purchase", "Pode aprovar ou cancelar pedido de compra"),
            ("receive_purchase", "Pode registrar recebimento de compra"),
        ]
        constraints = [
            # Segregacao: quem solicita nao aprova o proprio pedido.
            models.CheckConstraint(
                condition=~models.Q(approved_by=models.F("created_by")),
                name="inventory_po_approver_not_creator",
            ),
        ]

    def __str__(self):
        return f"Pedido de compra {self.pk}"

    @property
    def total(self):
        return sum((line.quantity * line.unit_price for line in self.lines.all()), Decimal("0"))


class PurchaseOrderLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="lines")
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    received_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["item__code", "id"]
        constraints = [
            models.UniqueConstraint(fields=["order", "item"], name="uniq_inventory_po_item"),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1, received_quantity__lte=models.F("quantity")),
                name="inventory_po_line_received_le_ordered",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0), name="inventory_po_line_price_nonnegative"
            ),
        ]

    def __str__(self):
        return f"Item de compra {self.pk}"

    @property
    def pending(self):
        return self.quantity - self.received_quantity


class PurchaseReceipt(models.Model):
    """Recebimento confirmado: gera exatamente uma entrada de estoque."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    line = models.ForeignKey(PurchaseOrderLine, on_delete=models.PROTECT, related_name="receipts")
    movement = models.OneToOneField(
        MaterialMovement, on_delete=models.PROTECT, related_name="purchase_receipt"
    )
    invoice_number = models.CharField("Nota fiscal", max_length=60)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["received_at", "id"]

    def __str__(self):
        return f"Recebimento {self.pk}"


auditlog.register(InventoryItem, exclude_fields=["code", "name", "unit"])
auditlog.register(Supplier)
auditlog.register(PurchaseOrder)
auditlog.register(PurchaseOrderLine)
auditlog.register(PurchaseReceipt)
auditlog.register(StockLocation)
auditlog.register(MaterialBalance)
auditlog.register(MaterialMovement)
auditlog.register(Requisition, exclude_fields=["item_code", "item_name", "item_unit", "quantity"])
