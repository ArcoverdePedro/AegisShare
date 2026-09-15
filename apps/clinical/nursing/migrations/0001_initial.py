import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("pep", "0003_clinicalevolution"),
        ("prescription", "0008_request_history_guards"),
    ]

    operations = [
        migrations.CreateModel(
            name="VitalSignsRecord",
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
                ("recorded_at", models.DateTimeField()),
                (
                    "idempotency_key",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                (
                    "origin",
                    models.CharField(
                        choices=[
                            ("ONLINE", "Online"),
                            ("OFFLINE_SYNC", "Sincronização offline"),
                        ],
                        default="ONLINE",
                        max_length=12,
                    ),
                ),
                (
                    "temperature_c",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=5,
                        null=True,
                    ),
                ),
                ("heart_rate_bpm", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "respiratory_rate_irpm",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                (
                    "systolic_bp_mmhg",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                (
                    "diastolic_bp_mmhg",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                (
                    "oxygen_saturation_pct",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=5,
                        null=True,
                    ),
                ),
                (
                    "weight_kg",
                    models.DecimalField(
                        blank=True,
                        decimal_places=3,
                        max_digits=8,
                        null=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "encounter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="nursing_vital_signs",
                        to="pep.encounter",
                    ),
                ),
                (
                    "recorded_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="nursing_vital_sign_records",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "replaces",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="corrections",
                        to="nursing.vitalsignsrecord",
                    ),
                ),
            ],
            options={
                "ordering": ["-recorded_at", "-created_at"],
                "permissions": [
                    ("view_nursing", "Pode visualizar registros de enfermagem"),
                    ("record_vitals", "Pode registrar sinais vitais"),
                ],
                "indexes": [
                    models.Index(
                        fields=["encounter", "recorded_at"],
                        name="nur_vitals_enc_time_idx",
                    ),
                    models.Index(
                        fields=["recorded_by", "recorded_at"],
                        name="nur_vitals_user_time_idx",
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=(
                            models.Q(("temperature_c__isnull", False))
                            | models.Q(("heart_rate_bpm__isnull", False))
                            | models.Q(("respiratory_rate_irpm__isnull", False))
                            | models.Q(("systolic_bp_mmhg__isnull", False))
                            | models.Q(("diastolic_bp_mmhg__isnull", False))
                            | models.Q(("oxygen_saturation_pct__isnull", False))
                            | models.Q(("weight_kg__isnull", False))
                        ),
                        name="nur_vitals_any_measure",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("temperature_c__isnull", True))
                        | models.Q(("temperature_c__gt", 0)),
                        name="nur_vitals_temperature_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("heart_rate_bpm__isnull", True))
                        | models.Q(("heart_rate_bpm__gt", 0)),
                        name="nur_vitals_hr_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("respiratory_rate_irpm__isnull", True))
                        | models.Q(("respiratory_rate_irpm__gt", 0)),
                        name="nur_vitals_rr_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("systolic_bp_mmhg__isnull", True))
                        | models.Q(("systolic_bp_mmhg__gt", 0)),
                        name="nur_vitals_sysbp_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("diastolic_bp_mmhg__isnull", True))
                        | models.Q(("diastolic_bp_mmhg__gt", 0)),
                        name="nur_vitals_diabp_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("oxygen_saturation_pct__isnull", True))
                        | (
                            models.Q(("oxygen_saturation_pct__gt", 0))
                            & models.Q(("oxygen_saturation_pct__lte", 100))
                        ),
                        name="nur_vitals_spo2_range",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("weight_kg__isnull", True))
                        | models.Q(("weight_kg__gt", 0)),
                        name="nur_vitals_weight_positive",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="MedicationAdministration",
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
                ("administered_at", models.DateTimeField()),
                (
                    "administered_dose",
                    models.DecimalField(decimal_places=4, max_digits=12),
                ),
                ("administered_dose_unit", models.CharField(max_length=40)),
                (
                    "operation_key",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "administered_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="medication_administrations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "dispense_item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="nursing_administrations",
                        to="prescription.medicationdispenseitem",
                    ),
                ),
            ],
            options={
                "ordering": ["-administered_at", "-created_at"],
                "permissions": [
                    ("administer_medication", "Pode administrar medicamentos"),
                ],
                "indexes": [
                    models.Index(
                        fields=["dispense_item", "administered_at"],
                        name="nur_admin_item_time_idx",
                    ),
                    models.Index(
                        fields=["administered_by", "administered_at"],
                        name="nur_admin_user_time_idx",
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("administered_dose__gt", 0)),
                        name="nur_admin_dose_positive",
                    ),
                ],
            },
        ),
    ]
