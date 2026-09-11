import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Patient",
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
                    "identifier_type",
                    models.CharField(
                        choices=[("CPF", "CPF"), ("OTHER", "Outro identificador")],
                        default="CPF",
                        max_length=10,
                    ),
                ),
                ("identifier", models.CharField(max_length=64)),
                ("full_name", models.CharField(max_length=255)),
                ("birth_date", models.DateField()),
                (
                    "sex",
                    models.CharField(
                        choices=[
                            ("F", "Feminino"),
                            ("M", "Masculino"),
                            ("I", "Intersexo"),
                            ("O", "Outro"),
                            ("U", "Não informado"),
                        ],
                        default="U",
                        max_length=1,
                    ),
                ),
                ("phone", models.CharField(blank=True, max_length=32)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_patients",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["full_name", "birth_date"],
                "indexes": [
                    models.Index(fields=["full_name"], name="pep_patient_name_idx"),
                    models.Index(fields=["birth_date"], name="pep_patient_birth_idx"),
                    models.Index(fields=["active"], name="pep_patient_active_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("identifier_type", "identifier"),
                        name="uniq_pep_patient_identifier",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="PatientAccessGrant",
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
                ("reason", models.CharField(max_length=255)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "granted_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="granted_patient_accesses",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="access_grants",
                        to="pep.patient",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="patient_access_grants",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["user", "expires_at"],
                        name="pep_access_user_exp_idx",
                    ),
                    models.Index(
                        fields=["patient", "expires_at"],
                        name="pep_access_patient_exp_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("patient", "user"),
                        name="uniq_pep_patient_access_user",
                    )
                ],
            },
        ),
    ]
