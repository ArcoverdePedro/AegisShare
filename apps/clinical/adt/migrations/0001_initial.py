# Generated manually from Spec 002 ADT foundation.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("pep", "0003_clinicalevolution"),
    ]

    operations = [
        migrations.CreateModel(
            name="Location",
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
                ("code", models.CharField(max_length=40, unique=True)),
                ("name", models.CharField(max_length=160)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("UNIT", "Unidade"),
                            ("WARD", "Setor"),
                            ("ROOM", "Quarto"),
                            ("OTHER", "Outro"),
                        ],
                        default="OTHER",
                        max_length=10,
                    ),
                ),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="adt.location",
                    ),
                ),
            ],
            options={"ordering": ["name", "code"]},
        ),
        migrations.CreateModel(
            name="Admission",
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
                ("admitted_at", models.DateTimeField()),
                (
                    "operation_key",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "admitted_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="adt_admissions_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "encounter",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="adt_admission",
                        to="pep.encounter",
                    ),
                ),
            ],
            options={
                "ordering": ["-admitted_at", "-created_at"],
                "permissions": [
                    ("admit_patient", "Pode admitir paciente"),
                    (
                        "view_movement_history",
                        "Pode visualizar histórico de movimentação ADT",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="Bed",
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
                ("code", models.CharField(max_length=40)),
                ("label", models.CharField(max_length=120)),
                (
                    "operational_status",
                    models.CharField(
                        choices=[
                            ("AVAILABLE", "Disponível"),
                            ("BLOCKED", "Bloqueado"),
                            ("OUT_OF_SERVICE", "Fora de serviço"),
                        ],
                        default="AVAILABLE",
                        max_length=20,
                    ),
                ),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "location",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="beds",
                        to="adt.location",
                    ),
                ),
            ],
            options={
                "ordering": ["location__name", "code"],
                "permissions": [
                    ("view_bed_map", "Pode visualizar mapa de leitos"),
                    (
                        "manage_bed_status",
                        "Pode alterar estado operacional de leitos",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="BedOccupancy",
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
                ("started_at", models.DateTimeField()),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                (
                    "end_reason",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("TRANSFER", "Transferência"),
                            ("DISCHARGE", "Alta"),
                            ("CORRECTION", "Correção"),
                        ],
                        max_length=12,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "admission",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="occupancies",
                        to="adt.admission",
                    ),
                ),
                (
                    "bed",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="occupancies",
                        to="adt.bed",
                    ),
                ),
                (
                    "ended_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="adt_occupancies_ended",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "started_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="adt_occupancies_started",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["started_at", "created_at"]},
        ),
        migrations.AddIndex(
            model_name="location",
            index=models.Index(fields=["active"], name="adt_location_active_idx"),
        ),
        migrations.AddIndex(
            model_name="admission",
            index=models.Index(fields=["admitted_at"], name="adt_admission_time_idx"),
        ),
        migrations.AddIndex(
            model_name="bed",
            index=models.Index(
                fields=["location", "operational_status"],
                name="adt_bed_loc_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="bed",
            index=models.Index(fields=["active"], name="adt_bed_active_idx"),
        ),
        migrations.AddConstraint(
            model_name="bed",
            constraint=models.UniqueConstraint(
                fields=("location", "code"),
                name="uniq_adt_bed_location_code",
            ),
        ),
        migrations.AddIndex(
            model_name="bedoccupancy",
            index=models.Index(fields=["bed", "ended_at"], name="adt_occ_bed_end_idx"),
        ),
        migrations.AddIndex(
            model_name="bedoccupancy",
            index=models.Index(
                fields=["admission", "ended_at"],
                name="adt_occ_adm_end_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="bedoccupancy",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("ended_at__isnull", True))
                    | models.Q(("ended_at__gte", models.F("started_at")))
                ),
                name="adt_occ_end_after_start",
            ),
        ),
        migrations.AddConstraint(
            model_name="bedoccupancy",
            constraint=models.UniqueConstraint(
                condition=models.Q(("ended_at__isnull", True)),
                fields=("bed",),
                name="uniq_adt_active_bed_occ",
            ),
        ),
        migrations.AddConstraint(
            model_name="bedoccupancy",
            constraint=models.UniqueConstraint(
                condition=models.Q(("ended_at__isnull", True)),
                fields=("admission",),
                name="uniq_adt_active_adm_occ",
            ),
        ),
    ]
