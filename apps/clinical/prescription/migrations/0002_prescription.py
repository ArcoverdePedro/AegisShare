import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pep", "0003_clinicalevolution"),
        ("prescription", "0001_catalog"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MedicationRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("DRAFT", "Rascunho"), ("SUBMITTED", "Submetida"), ("VALIDATED", "Validada"), ("CANCELLED", "Cancelada")], default="DRAFT", max_length=12)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("validated_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("cancellation_reason", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("authored_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="authored_medication_requests", to=settings.AUTH_USER_MODEL)),
                ("cancelled_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="cancelled_medication_requests", to=settings.AUTH_USER_MODEL)),
                ("encounter", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="medication_requests", to="pep.encounter")),
                ("replaces", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="replacements", to="prescription.medicationrequest")),
                ("validated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="validated_medication_requests", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
                "permissions": [
                    ("view_medication_request", "Pode visualizar prescrições"),
                    ("prescribe_medication", "Pode prescrever medicamentos"),
                    ("validate_medication_request", "Pode validar prescrições"),
                    ("cancel_medication_request", "Pode cancelar prescrições"),
                ],
                "indexes": [
                    models.Index(fields=["encounter", "created_at"], name="rx_request_enc_created_idx"),
                    models.Index(fields=["status", "created_at"], name="rx_request_status_idx"),
                    models.Index(fields=["authored_by", "created_at"], name="rx_request_author_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="MedicationRequestItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("dose", models.DecimalField(decimal_places=4, max_digits=12)),
                ("dose_unit", models.CharField(max_length=40)),
                ("route", models.CharField(max_length=80)),
                ("frequency", models.CharField(max_length=120)),
                ("duration_value", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("duration_unit", models.CharField(blank=True, max_length=40)),
                ("instructions", models.TextField(blank=True)),
                ("sequence", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("drug", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="request_items", to="prescription.drug")),
                ("medication_request", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="items", to="prescription.medicationrequest")),
            ],
            options={
                "ordering": ["sequence", "created_at"],
                "indexes": [models.Index(fields=["medication_request", "sequence"], name="rx_request_item_seq_idx")],
                "constraints": [
                    models.UniqueConstraint(fields=("medication_request", "sequence"), name="uniq_rx_request_item_sequence"),
                    models.CheckConstraint(condition=models.Q(dose__gt=0), name="rx_request_item_dose_positive"),
                ],
            },
        ),
        migrations.CreateModel(
            name="MedicationSafetyReview",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("allergy_status", models.CharField(choices=[("UNAVAILABLE", "Indisponível"), ("REVIEW_REQUIRED", "Revisão manual necessária"), ("REVIEW_CONFIRMED", "Revisão manual confirmada"), ("STRUCTURED_CHECKED", "Checagem estruturada")], max_length=20)),
                ("dose_status", models.CharField(choices=[("PASS", "Aprovada"), ("BLOCKED", "Bloqueada"), ("NOT_EVALUABLE", "Não avaliável")], max_length=20)),
                ("blocking_findings", models.PositiveIntegerField(default=0)),
                ("warning_findings", models.PositiveIntegerField(default=0)),
                ("reference_version", models.CharField(max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("medication_request", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="safety_reviews", to="prescription.medicationrequest")),
                ("reviewed_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="medication_safety_reviews", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["created_at"],
                "indexes": [models.Index(fields=["medication_request", "created_at"], name="rx_review_request_idx")],
            },
        ),
        migrations.CreateModel(
            name="MedicationSafetyFinding",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("INTERACTION", "Interação"), ("ALLERGY", "Alergia"), ("DOSE", "Dose")], max_length=16)),
                ("severity", models.CharField(max_length=32)),
                ("blocking", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("dose_rule", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="findings", to="prescription.doserule")),
                ("interaction", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="findings", to="prescription.interaction")),
                ("request_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="safety_findings", to="prescription.medicationrequestitem")),
                ("review", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="findings", to="prescription.medicationsafetyreview")),
            ],
            options={"ordering": ["created_at"]},
        ),
    ]
