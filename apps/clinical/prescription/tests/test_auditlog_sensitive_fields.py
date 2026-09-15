from datetime import timedelta
from decimal import Decimal

from auditlog.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from apps.clinical.pep.models import Encounter, Patient

from ..models import Drug, Interaction, MedicationRequest, MedicationRequestItem

User = get_user_model()


class AuditlogSensitiveFieldTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(
            username="rx-audit-sensitive-actor",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="RX-AUDIT-SENSITIVE-PATIENT",
            full_name="Paciente Sintético Auditoria",
            birth_date=timezone.localdate() - timedelta(days=365 * 30),
            created_by=self.actor,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            responsible_professional=self.actor,
            created_by=self.actor,
        )
        self.drug_a = Drug.objects.create(
            code="RX-AUDIT-SENSITIVE-A",
            name="Medicamento Sintético A",
            presentation="Apresentação sintética",
            dispense_unit="unidade",
        )
        self.drug_b = Drug.objects.create(
            code="RX-AUDIT-SENSITIVE-B",
            name="Medicamento Sintético B",
            presentation="Apresentação sintética",
            dispense_unit="unidade",
        )

    def _latest_entry(self, instance, action):
        content_type = ContentType.objects.get_for_model(instance.__class__)
        return LogEntry.objects.filter(
            content_type=content_type,
            object_pk=str(instance.pk),
            action=action,
        ).latest("timestamp")

    def assert_field_and_value_absent(self, entry, field_name, sensitive_value):
        changes = entry.changes or {}
        self.assertNotIn(field_name, changes)
        self.assertNotIn(sensitive_value, str(changes))

    def test_interaction_summary_is_excluded_from_auditlog(self):
        sensitive_summary = "Resumo clínico livre que não deve aparecer no auditlog"
        interaction = Interaction.objects.create(
            drug_a=self.drug_a,
            drug_b=self.drug_b,
            severity=Interaction.Severity.MODERATE,
            blocking=False,
            summary=sensitive_summary,
        )

        entry = self._latest_entry(interaction, LogEntry.Action.CREATE)

        self.assert_field_and_value_absent(entry, "summary", sensitive_summary)

    def test_medication_request_cancellation_reason_is_excluded_from_auditlog(self):
        request = MedicationRequest.objects.create(
            encounter=self.encounter,
            authored_by=self.actor,
        )
        sensitive_reason = "Motivo clínico livre que não deve aparecer no auditlog"
        request.status = MedicationRequest.Status.CANCELLED
        request.cancelled_by = self.actor
        request.cancelled_at = timezone.now()
        request.cancellation_reason = sensitive_reason
        request.save(
            update_fields=[
                "status",
                "cancelled_by",
                "cancelled_at",
                "cancellation_reason",
                "updated_at",
            ]
        )

        entry = self._latest_entry(request, LogEntry.Action.UPDATE)

        self.assert_field_and_value_absent(entry, "cancellation_reason", sensitive_reason)

    def test_medication_request_item_instructions_are_excluded_from_auditlog(self):
        request = MedicationRequest.objects.create(
            encounter=self.encounter,
            authored_by=self.actor,
        )
        sensitive_instructions = "Instrução clínica livre que não deve aparecer no auditlog"
        item = MedicationRequestItem.objects.create(
            medication_request=request,
            drug=self.drug_a,
            dose=Decimal("1"),
            dose_unit="unidade",
            route="via sintética",
            frequency="frequência sintética",
            instructions=sensitive_instructions,
            sequence=1,
        )

        entry = self._latest_entry(item, LogEntry.Action.CREATE)

        self.assert_field_and_value_absent(entry, "instructions", sensitive_instructions)
