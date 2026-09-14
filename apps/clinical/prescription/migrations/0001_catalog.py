import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Drug",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("presentation", models.CharField(max_length=255)),
                ("strength_text", models.CharField(blank=True, max_length=120)),
                ("route_hint", models.CharField(blank=True, max_length=120)),
                ("dispense_unit", models.CharField(max_length=40)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["name", "presentation", "code"],
                "permissions": [("manage_drug_catalog", "Pode manter catálogo farmacêutico")],
                "indexes": [models.Index(fields=["active", "name"], name="rx_drug_active_name_idx")],
            },
        ),
        migrations.CreateModel(
            name="DoseRule",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("rule_code", models.CharField(max_length=64)),
                ("basis", models.CharField(choices=[("AGE", "Idade"), ("WEIGHT", "Peso"), ("AGE_AND_WEIGHT", "Idade e peso")], max_length=20)),
                ("min_age_days", models.PositiveIntegerField(blank=True, null=True)),
                ("max_age_days", models.PositiveIntegerField(blank=True, null=True)),
                ("min_weight_kg", models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True)),
                ("max_weight_kg", models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True)),
                ("min_dose", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
                ("max_dose", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
                ("dose_unit", models.CharField(max_length=40)),
                ("per_kg", models.BooleanField(default=False)),
                ("reference_source", models.CharField(blank=True, max_length=255)),
                ("reference_version", models.CharField(blank=True, max_length=120)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("active", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="approved_dose_rules", to=settings.AUTH_USER_MODEL)),
                ("drug", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="dose_rules", to="prescription.drug")),
            ],
            options={
                "indexes": [models.Index(fields=["drug", "active"], name="rx_dose_drug_active_idx")],
                "constraints": [models.UniqueConstraint(fields=("drug", "rule_code", "reference_version"), name="uniq_rx_dose_rule_version")],
            },
        ),
        migrations.CreateModel(
            name="Interaction",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("severity", models.CharField(choices=[("INFO", "Informativa"), ("MINOR", "Leve"), ("MODERATE", "Moderada"), ("MAJOR", "Grave"), ("CONTRAINDICATED", "Contraindicada")], max_length=20)),
                ("blocking", models.BooleanField(default=False)),
                ("summary", models.TextField()),
                ("reference_source", models.CharField(blank=True, max_length=255)),
                ("reference_version", models.CharField(blank=True, max_length=120)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("active", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="approved_drug_interactions", to=settings.AUTH_USER_MODEL)),
                ("drug_a", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="interactions_as_a", to="prescription.drug")),
                ("drug_b", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="interactions_as_b", to="prescription.drug")),
            ],
            options={
                "indexes": [models.Index(fields=["drug_a", "drug_b", "active"], name="rx_interaction_pair_idx")],
                "constraints": [
                    models.CheckConstraint(condition=~models.Q(drug_a=models.F("drug_b")), name="rx_interaction_distinct_drugs"),
                    models.UniqueConstraint(fields=("drug_a", "drug_b", "reference_version"), name="uniq_rx_interaction_pair_version"),
                ],
            },
        ),
    ]
