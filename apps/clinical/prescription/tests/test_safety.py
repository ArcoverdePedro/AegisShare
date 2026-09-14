from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.models import Encounter, Patient

from ..models import (
    DoseRule,
    Drug,
    Interaction,
    MedicationRequest,
    MedicationRequestItem,
    MedicationSafetyFinding,
    MedicationSafetyReview,
)
from ..safety import (
    SafetyReferenceError,
    SafetyStateError,
    evaluate_medication_request_safety,
)


class MedicationSafetyEngineTests(TestCase):
    def setUp(self):
        self.admin = make_user("rx-safety-admin", role="ADM")
        self.professional = make_user("rx-safety-professional", role="FUNC")
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="RX-SAFETY-PATIENT",
            full_name="Paciente Sintético Safety",
            birth_date=timezone.localdate() - timedelta(days=3650),
            created_by=self.admin,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            responsible_professional=self.professional,
            created_by=self.admin,
        )
        self.drug_a = self._drug("RX-SAFE-A", "Medicamento Sintético A")
        self.drug_b = self._drug("RX-SAFE-B", "Medicamento Sintético B")

    def _drug(self, code, name):
        return Drug.objects.create(
            code=code,
            name=name,
            presentation="Apresentação sintética",
            dispense_unit="unidade",
        )

    def _submitted_request(self, items):
        request = MedicationRequest.objects.create(
            encounter=self.encounter,
            authored_by=self.professional,
        )
        for sequence, item_data in enumerate(items, start=1):
            MedicationRequestItem.objects.create(
                medication_request=request,
                drug=item_data["drug"],
                dose=item_data.get("dose", Decimal("10")),
                dose_unit=item_data.get("dose_unit", "mg"),
                route="via sintética",
                frequency="frequência sintética",
                sequence=sequence,
            )
        request.status = MedicationRequest.Status.SUBMITTED
        request.submitted_at = timezone.now()
        request.save(update_fields=["status", "submitted_at", "updated_at"])
        return request

    def _age_rule(
        self,
        drug,
        *,
        code,
        min_dose=Decimal("5"),
        max_dose=Decimal("15"),
        dose_unit="mg",
    ):
        return DoseRule.objects.create(
            drug=drug,
            rule_code=code,
            basis=DoseRule.Basis.AGE,
            min_age_days=3000,
            max_age_days=5000,
            min_dose=min_dose,
            max_dose=max_dose,
            dose_unit=dose_unit,
            reference_source="Fonte sintética de teste",
            reference_version=f"TEST-{code}-V1",
            approved_by=self.admin,
            approved_at=timezone.now(),
            active=True,
        )

    def _interaction(self, *, severity, blocking):
        return Interaction.objects.create(
            drug_a=self.drug_a,
            drug_b=self.drug_b,
            severity=severity,
            blocking=blocking,
            summary="Interação exclusivamente sintética para teste automatizado.",
            reference_source="Fonte sintética de teste",
            reference_version=f"TEST-INT-{severity}-{int(blocking)}",
            approved_by=self.admin,
            approved_at=timezone.now(),
            active=True,
        )

    def test_draft_request_is_not_evaluated(self):
        request = MedicationRequest.objects.create(
            encounter=self.encounter,
            authored_by=self.professional,
        )

        with self.assertRaises(SafetyStateError):
            evaluate_medication_request_safety(request)

    def test_age_rule_within_configured_limits_passes(self):
        request = self._submitted_request([{"drug": self.drug_a}])
        self._age_rule(self.drug_a, code="AGE-PASS")

        result = evaluate_medication_request_safety(request)

        self.assertEqual(result.allergy_status, MedicationSafetyReview.AllergyStatus.UNAVAILABLE)
        self.assertEqual(result.dose_status, MedicationSafetyReview.DoseStatus.PASS)
        self.assertEqual(result.blocking_findings, 0)
        self.assertEqual(result.warning_findings, 0)
        self.assertEqual(result.findings, ())
        self.assertTrue(result.reference_version.startswith("RXSET-"))

    def test_age_rule_outside_configured_dose_is_blocked(self):
        request = self._submitted_request(
            [{"drug": self.drug_a, "dose": Decimal("20")}]
        )
        rule = self._age_rule(self.drug_a, code="AGE-BLOCK")

        result = evaluate_medication_request_safety(request)

        self.assertEqual(result.dose_status, MedicationSafetyReview.DoseStatus.BLOCKED)
        self.assertEqual(result.blocking_findings, 1)
        finding = result.findings[0]
        self.assertEqual(finding.kind, MedicationSafetyFinding.Kind.DOSE)
        self.assertEqual(finding.dose_rule_id, rule.pk)
        self.assertTrue(finding.blocking)
        self.assertEqual(finding.reason_code, "DOSE_OUTSIDE_RULE")

    def test_weight_rule_is_not_evaluable_without_structured_weight(self):
        request = self._submitted_request([{"drug": self.drug_a}])
        rule = DoseRule.objects.create(
            drug=self.drug_a,
            rule_code="WEIGHT-NOT-EVALUABLE",
            basis=DoseRule.Basis.WEIGHT,
            min_weight_kg=Decimal("1"),
            max_weight_kg=Decimal("100"),
            min_dose=Decimal("1"),
            max_dose=Decimal("20"),
            dose_unit="mg",
            reference_source="Fonte sintética de teste",
            reference_version="TEST-WEIGHT-V1",
            approved_by=self.admin,
            approved_at=timezone.now(),
            active=True,
        )

        result = evaluate_medication_request_safety(request)

        self.assertEqual(result.dose_status, MedicationSafetyReview.DoseStatus.NOT_EVALUABLE)
        self.assertEqual(result.blocking_findings, 0)
        self.assertEqual(result.warning_findings, 1)
        self.assertEqual(result.findings[0].dose_rule_id, rule.pk)
        self.assertEqual(result.findings[0].reason_code, "DOSE_WEIGHT_UNAVAILABLE")

    def test_unit_mismatch_is_not_converted_or_silently_approved(self):
        request = self._submitted_request([{"drug": self.drug_a, "dose_unit": "mg"}])
        self._age_rule(self.drug_a, code="UNIT-MISMATCH", dose_unit="mL")

        result = evaluate_medication_request_safety(request)

        self.assertEqual(result.dose_status, MedicationSafetyReview.DoseStatus.NOT_EVALUABLE)
        self.assertEqual(result.findings[0].reason_code, "DOSE_UNIT_MISMATCH")
        self.assertFalse(result.findings[0].blocking)

    def test_missing_active_dose_rule_is_not_evaluable(self):
        request = self._submitted_request([{"drug": self.drug_a}])

        result = evaluate_medication_request_safety(request)

        self.assertEqual(result.dose_status, MedicationSafetyReview.DoseStatus.NOT_EVALUABLE)
        self.assertEqual(result.findings[0].reason_code, "DOSE_NO_APPLICABLE_RULE")

    def test_blocking_interaction_uses_configured_blocking_flag(self):
        request = self._submitted_request(
            [{"drug": self.drug_a}, {"drug": self.drug_b}]
        )
        self._age_rule(self.drug_a, code="INT-A")
        self._age_rule(self.drug_b, code="INT-B")
        interaction = self._interaction(
            severity=Interaction.Severity.MINOR,
            blocking=True,
        )

        result = evaluate_medication_request_safety(request)

        self.assertEqual(result.dose_status, MedicationSafetyReview.DoseStatus.PASS)
        self.assertEqual(result.blocking_findings, 1)
        self.assertEqual(result.warning_findings, 0)
        finding = result.findings[0]
        self.assertEqual(finding.interaction_id, interaction.pk)
        self.assertEqual(finding.severity, Interaction.Severity.MINOR)
        self.assertTrue(finding.blocking)

    def test_major_interaction_remains_nonblocking_when_reference_says_so(self):
        request = self._submitted_request(
            [{"drug": self.drug_a}, {"drug": self.drug_b}]
        )
        self._age_rule(self.drug_a, code="NONBLOCK-A")
        self._age_rule(self.drug_b, code="NONBLOCK-B")
        interaction = self._interaction(
            severity=Interaction.Severity.MAJOR,
            blocking=False,
        )

        result = evaluate_medication_request_safety(request)

        self.assertEqual(result.blocking_findings, 0)
        self.assertEqual(result.warning_findings, 1)
        finding = result.findings[0]
        self.assertEqual(finding.interaction_id, interaction.pk)
        self.assertEqual(finding.severity, Interaction.Severity.MAJOR)
        self.assertFalse(finding.blocking)

    def test_active_ungoverned_reference_is_rejected_even_if_database_was_bypassed(self):
        request = self._submitted_request([{"drug": self.drug_a}])
        rule = DoseRule.objects.create(
            drug=self.drug_a,
            rule_code="BYPASS-GOVERNANCE",
            basis=DoseRule.Basis.AGE,
            min_age_days=3000,
            max_age_days=5000,
            min_dose=Decimal("1"),
            max_dose=Decimal("20"),
            dose_unit="mg",
            active=False,
        )
        DoseRule.objects.filter(pk=rule.pk).update(active=True)

        with self.assertRaises(SafetyReferenceError):
            evaluate_medication_request_safety(request)

    def test_reference_set_version_is_deterministic_and_changes_with_active_set(self):
        request = self._submitted_request([{"drug": self.drug_a}])
        self._age_rule(self.drug_a, code="VERSION-A")

        first = evaluate_medication_request_safety(request)
        second = evaluate_medication_request_safety(request)
        self.assertEqual(first.reference_version, second.reference_version)

        self._age_rule(self.drug_a, code="VERSION-B")
        third = evaluate_medication_request_safety(request)
        self.assertNotEqual(first.reference_version, third.reference_version)

    def test_approved_reference_cannot_be_rewritten_or_reactivated(self):
        interaction = self._interaction(
            severity=Interaction.Severity.MODERATE,
            blocking=False,
        )
        interaction.summary = "Tentativa sintética de reescrita."
        with self.assertRaises(ValidationError):
            interaction.save()

        interaction.refresh_from_db()
        interaction.active = False
        interaction.save()
        interaction.active = True
        with self.assertRaises(ValidationError):
            interaction.save()

    def test_approved_dose_rule_cannot_be_rewritten(self):
        rule = self._age_rule(self.drug_a, code="IMMUTABLE-RULE")
        rule.max_dose = Decimal("99")

        with self.assertRaises(ValidationError):
            rule.save()
