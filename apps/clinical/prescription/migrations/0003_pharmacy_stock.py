import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("prescription", "0002_prescription"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StockItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("storage_location", models.CharField(max_length=160)),
                ("minimum_level", models.DecimalField(decimal_places=4, default=0, max_digits=14)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("drug", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_items", to="prescription.drug")),
            ],
            options={
                "permissions": [
                    ("view_pharmacy_stock", "Pode consultar estoque farmacêutico"),
                    ("manage_pharmacy_stock", "Pode gerenciar estoque farmacêutico"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("drug", "storage_location"), name="uniq_rx_stock_location"),
                    models.CheckConstraint(condition=models.Q(minimum_level__gte=0), name="rx_stock_min_nonnegative"),
                ],
            },
        ),
        migrations.CreateModel(
            name="Lot",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("lot_number", models.CharField(max_length=120)),
                ("expires_on", models.DateField()),
                ("quantity_available", models.DecimalField(decimal_places=4, default=0, max_digits=14)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("stock_item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lots", to="prescription.stockitem")),
            ],
            options={
                "indexes": [models.Index(fields=["stock_item", "expires_on", "active"], name="rx_lot_expiry_idx")],
                "constraints": [
                    models.UniqueConstraint(fields=("stock_item", "lot_number"), name="uniq_rx_lot_number"),
                    models.CheckConstraint(condition=models.Q(quantity_available__gte=0), name="rx_lot_quantity_nonnegative"),
                ],
            },
        ),
        migrations.CreateModel(
            name="MedicationDispense",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("operation_key", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("dispensed_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("dispensed_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="medication_dispenses", to=settings.AUTH_USER_MODEL)),
                ("medication_request", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="dispenses", to="prescription.medicationrequest")),
            ],
            options={
                "ordering": ["-dispensed_at", "-created_at"],
                "permissions": [
                    ("view_medication_dispense", "Pode visualizar dispensações"),
                    ("dispense_medication", "Pode dispensar medicamentos"),
                ],
                "indexes": [models.Index(fields=["medication_request", "dispensed_at"], name="rx_dispense_request_idx")],
            },
        ),
        migrations.CreateModel(
            name="MedicationDispenseItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=14)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("dispense", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="items", to="prescription.medicationdispense")),
                ("lot", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="dispense_items", to="prescription.lot")),
                ("request_item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="dispense_items", to="prescription.medicationrequestitem")),
            ],
            options={
                "constraints": [models.CheckConstraint(condition=models.Q(quantity__gt=0), name="rx_dispense_item_quantity_positive")]
            },
        ),
        migrations.CreateModel(
            name="StockMovement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("movement_type", models.CharField(choices=[("DISPENSE", "Dispensação"), ("RECEIPT", "Entrada"), ("ADJUSTMENT", "Ajuste")], max_length=12)),
                ("quantity_delta", models.DecimalField(decimal_places=4, max_digits=14)),
                ("operation_key", models.UUIDField(default=uuid.uuid4)),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="pharmacy_stock_movements", to=settings.AUTH_USER_MODEL)),
                ("dispense_item", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="stock_movement", to="prescription.medicationdispenseitem")),
                ("lot", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="movements", to="prescription.lot")),
            ],
            options={
                "ordering": ["created_at"],
                "indexes": [
                    models.Index(fields=["lot", "created_at"], name="rx_stock_move_lot_idx"),
                    models.Index(fields=["operation_key"], name="rx_stock_move_operation_idx"),
                ],
                "constraints": [models.CheckConstraint(condition=~models.Q(quantity_delta=0), name="rx_stock_movement_nonzero")],
            },
        ),
    ]
