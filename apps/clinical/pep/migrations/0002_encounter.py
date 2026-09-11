import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pep", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Encounter",
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
                (
                    "encounter_type",
                    models.CharField(
                        choices=[
                            ("CONSULTATION", "Consulta"),
                            ("EMERGENCY", "Urgência/Emergência"),
                            ("INPATIENT", "Internação"),
                            ("TELEHEALTH", "Teleatendimento"),
                            ("OTHER", "Outro"),
                        ],
                        default="CONSULTATION",
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("OPEN", "Aberto"),
                            ("CLOSED", "Encerrado"),
                            ("CANCELLED", "Cancelado"),
                        ],
                        default="OPEN",
                        max_length=10,
                    ),
                ),
                ("started_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("location", models.CharField(blank=True, max_length=160)),
                ("reason", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_pep_encounters",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="encounters",
                        to="pep.patient",
                    ),
                ),
                (
                    "responsible_professional",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="responsible_pep_encounters",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-started_at", "-created_at"],
                "indexes": [
                    models.Index(
                        fields=["patient", "started_at"],
                        name="pep_enc_patient_start_idx",
                    ),
                    models.Index(fields=["status"], name="pep_enc_status_idx"),
                    models.Index(
                        fields=["responsible_professional", "started_at"],
                        name="pep_enc_prof_start_idx",
                    ),
                ],
            },
        ),
    ]
