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
    Lot,
    MedicationDispense,
    MedicationRequest,
    MedicationRequestItem,
    MedicationSafetyReview,
    StockItem,
    StockMovement,
)


class PrescriptionModelTests(TestCase):
    def setUp(self):
        self.user = make_user("rx-model-user", role="FUNC")
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="RX-PATIENT-1",
            full_name="Paciente Prescrição",
            birth_date=timezone.localdate() - timedelta(days=365 * 30),
            created_by=self.user,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            responsible_professional=self.user,
            created_by=self.user,
        )
        self.drug = Drug.objects.create(
            code="med-001",
            name="Medicamento Sintético",
            presentation="Comprimido de teste",
            dispense_unit="unidade",
        )

    def test_drug_code_is_normalized(self):
        self.assertEqual(self.drug.code, "MED-001")

    def test_active_interaction_requires_governed_reference(self):
        other = Drug.objects.create(
            code="MED-002",
            name="Segundo Medicamento Sintético",
            presentation="Comprimido de teste",
            dispense_unit="unidade",
        )
        interaction = Interaction(
            drug_a=self.drug,
            drug_b=other,
            severity=Interaction.Severity.MAJOR,
            blocking=True,
            summary="Achado sintético para teste.",
            active=True,
        )

        with self.assertRaises(ValidationError):
            interaction.save()

    def test_active_dose_rule_requires_governed_reference(self):
        rule = DoseRule(
            drug=self.drug,
            rule_code="TEST-AGE",
            basis=DoseRule.Basis.AGE,
            min_age_days=0,
            max_age_days=3650,
            min_dose=Decimal("1"),
            max_dose=Decimal("2"),
            dose_unit="mg",
            active=True,
        )

        with self.assertRaises(ValidationError):
            rule.save()

    def test_request_item_becomes_immutable_after_submission(self):
        request = MedicationRequest.objects.create(
            encounter=self.encounter,
            authored_by=self.user,
        )
        item = MedicationRequestItem.objects.create(
            medication_request=request,
            drug=self.drug,
            dose=Decimal("1"),
            dose_unit="mg",
            route="oral",
            frequency="1x ao dia",
            sequence=1,
        )
        request.status = MedicationRequest.Status.SUBMITTED
        request.submitted_at = timezone.now()
        request.save()

        item.frequency = "2x ao dia"
        with self.assertRaises(ValidationError):
            item.save()
        with self.assertRaises(ValidationError):
            item.delete()

    def test_safety_review_is_append_only(self):
        request = MedicationRequest.objects.create(
            encounter=self.encounter,
            authored_by=self.user,
        )
        review = MedicationSafetyReview.objects.create(
            medication_request=request,
            reviewed_by=self.user,
            allergy_status=MedicationSafetyReview.AllergyStatus.UNAVAILABLE,
            dose_status=MedicationSafetyReview.DoseStatus.NOT_EVALUABLE,
            reference_version="synthetic-v1",
        )

        review.warning_findings = 1
        with self.assertRaises(ValidationError):
            review.save()
        with self.assertRaises(ValidationError):
            review.delete()

    def test_negative_lot_balance_is_rejected(self):
        stock = StockItem.objects.create(
            drug=self.drug,
            storage_location="Farmácia Teste",
            minimum_level=Decimal("0"),
        )
        lot = Lot(
            stock_item=stock,
            lot_number="LOT-NEG",
            expires_on=timezone.localdate() + timedelta(days=30),
            quantity_available=Decimal("-1"),
        )

        with self.assertRaises(ValidationError):
            lot.save()

    def test_dispense_requires_validated_request(self):
        request = MedicationRequest.objects.create(
            encounter=self.encounter,
            authored_by=self.user,
        )
        dispense = MedicationDispense(
            medication_request=request,
            dispensed_by=self.user,
            dispensed_at=timezone.now(),
        )

        with self.assertRaises(ValidationError):
            dispense.save()

    def test_manual_stock_adjustment_requires_reason(self):
        stock = StockItem.objects.create(
            drug=self.drug,
            storage_location="Farmácia Teste",
            minimum_level=Decimal("0"),
        )
        lot = Lot.objects.create(
            stock_item=stock,
            lot_number="LOT-001",
            expires_on=timezone.localdate() + timedelta(days=30),
            quantity_available=Decimal("10"),
        )
        movement = StockMovement(
            lot=lot,
            movement_type=StockMovement.Type.ADJUSTMENT,
            quantity_delta=Decimal("1"),
            actor=self.user,
        )

        with self.assertRaises(ValidationError):
            movement.save()
