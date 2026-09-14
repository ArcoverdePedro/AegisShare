import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("adt", "0002_userlocationaccess"),
    ]

    operations = [
        migrations.CreateModel(
            name="Transfer",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("transferred_at", models.DateTimeField()),
                ("reason", models.CharField(blank=True, max_length=255)),
                (
                    "operation_key",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "admission",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="transfers",
                        to="adt.admission",
                    ),
                ),
                (
                    "destination_occupancy",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="transfer_in",
                        to="adt.bedoccupancy",
                    ),
                ),
                (
                    "source_occupancy",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="transfer_out",
                        to="adt.bedoccupancy",
                    ),
                ),
                (
                    "transferred_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="adt_transfers_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["transferred_at", "created_at"],
                "permissions": [("transfer_patient", "Pode transferir paciente")],
            },
        ),
        migrations.AddIndex(
            model_name="transfer",
            index=models.Index(
                fields=["admission", "transferred_at"],
                name="adt_transfer_adm_time_idx",
            ),
        ),
        migrations.CreateModel(
            name="Discharge",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("discharged_at", models.DateTimeField()),
                (
                    "disposition",
                    models.CharField(
                        choices=[
                            ("HOME", "Domicílio"),
                            ("TRANSFER_EXTERNAL", "Transferência externa"),
                            ("DEATH", "Óbito"),
                            ("OTHER", "Outro"),
                        ],
                        max_length=24,
                    ),
                ),
                ("reason", models.CharField(blank=True, max_length=255)),
                (
                    "operation_key",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "admission",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="discharge",
                        to="adt.admission",
                    ),
                ),
                (
                    "discharged_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="adt_discharges_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "final_occupancy",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="discharge",
                        to="adt.bedoccupancy",
                    ),
                ),
            ],
            options={
                "ordering": ["-discharged_at", "-created_at"],
                "permissions": [
                    ("discharge_patient", "Pode registrar alta de paciente")
                ],
            },
        ),
        migrations.AddIndex(
            model_name="discharge",
            index=models.Index(
                fields=["discharged_at"],
                name="adt_discharge_time_idx",
            ),
        ),
    ]
