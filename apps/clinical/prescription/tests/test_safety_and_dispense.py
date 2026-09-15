import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.utils import timezone

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.models import Encounter, Patient, PatientAccessGrant

from ..dispense_services import DispenseStateError, dispense_medication
from ..models import (
    DoseRule,
    Drug,
    Interaction,
    Lot,
    MedicationRequest,
    MedicationSafetyReview,
    StockMovement,
)
from ..safety import evaluate_medication_safety
from ..services import (
    PrescriptionValidationError,
    add_medication_request_item,
    create_medication_request,
    submit_medication_request,
    validate_medication_request,
)
from ..stock_services import create_lot, create_stock_item


class SafetyAndDispenseTests(TestCase):
    def setUp(self):
        self.admin = make_user("rx-flow-admin", role="ADM")
        self.prescriber = make_user("rx-flow-prescriber", role="FUNC")
        self.pharmacist = make_user("rx-flow-pharmacist", role="FUNC")
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="RX-FLOW-PATIENT",
            full_name="Paciente Sintético Fluxo RX",
            birth_date=timezone.localdate() - timedelta(days=365 * 30),
            created_by=self.admin,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            responsible_professional=self.prescriber,
            created_by=self.admin,
        )
        for user in (self.prescriber, self.pharmacist):
            PatientAccessGrant.objects.create(
                patient=self.patient,
                user=user,
                granted_by=self.admin,
                reason="Cobertura sintética de teste",
            )
        self._grant(self.prescriber, "prescribe_medication")
        for codename in (
            "validate_medication_request",
            "dispense_medication",
            "manage_pharmacy_stock",
        ):
            self._grant(self.pharmacist, codename)

        self.drug_a = Drug.objects.create(
            code="RX-FLOW-A",
            name="Medicamento Sintético A",
            presentation="Comprimido teste",
            dispense_unit="unidade",
        )
        self.drug_b = Drug.objects.create(
            code="RX-FLOW-B",
            name="Medicamento Sintético B",
            presentation="Comprimido teste",
            dispense_unit="unidade",
        )

    def _grant(self, user, codename):
        permission = Permission.objects.get(
            codename=codename,
            content_type__app_label="prescription",
        )
        user.user_permissions.add(permission)
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            if hasattr(user, cache_name):
                delattr(user, cache_name)

    def _submitted_request(self, *, two_items=False):
        request = create_medication_request(
            encounter_id=self.encounter.pk,
            actor=self.prescriber,
        )
        add_medication_request_item(
            request_id=request.pk,
            actor=self.prescriber,
            drug_id=self.drug_a.pk,
            dose=Decimal("10"),
            dose_unit="mg",
            route="oral",
            frequency="1x ao dia",
            sequence=1,
        )
        if two_items:
            add_medication_request_item(
                request_id=request.pk,
                actor=self.prescriber,
                drug_id=self.drug_b.pk,
                dose=Decimal("5"),
                dose_unit="mg",
                route="oral",
                frequency="1x ao dia",
                sequence=2,
            )
        return submit_medication_request(request_id=request.pk, actor=self.prescriber)

    def test_weight_rule_without_structured_weight_is_not_evaluable(self):
        request = self._submitted_request()
        DoseRule.objects.create(
            drug=self.drug_a,
            rule_code="SYNTH-WEIGHT",
            basis=DoseRule.Basis.WEIGHT,
            min_weight_kg=Decimal("1"),
            max_weight_kg=Decimal("200"),
            min_dose=Decimal("1"),
            max_dose=Decimal("20"),
            dose_unit="mg",
            reference_source="fixture-sintetica",
            reference_version="test-v1",
            approved_by=self.admin,
            approved_at=timezone.now(),
            active=True,
        )

        snapshot = evaluate_medication_safety(request)

        self.assertEqual(snapshot["dose_status"], MedicationSafetyReview.DoseStatus.NOT_EVALUABLE)
        self.assertTrue(
            any(
                finding["severity"] == MedicationSafetyReview.DoseStatus.NOT_EVALUABLE
                for finding in snapshot["findings"]
            )
        )

    def test_blocking_interaction_persists_review_and_refuses_validation(self):
        request = self._submitted_request(two_items=True)
        Interaction.objects.create(
            drug_a=self.drug_a,
            drug_b=self.drug_b,
            severity=Interaction.Severity.MAJOR,
            blocking=True,
            summary="Interação sintética bloqueante para teste",
            reference_source="fixture-sintetica",
            reference_version="test-v1",
            approved_by=self.admin,
            approved_at=timezone.now(),
            active=True,
        )

        with self.assertRaises(PrescriptionValidationError) as context:
            validate_medication_request(
                request_id=request.pk,
                actor=self.pharmacist,
                manual_allergy_review_confirmed=True,
            )

        request.refresh_from_db()
        self.assertEqual(request.status, MedicationRequest.Status.SUBMITTED)
        review = MedicationSafetyReview.objects.get(pk=context.exception.review_id)
        self.assertGreater(review.blocking_findings, 0)
        self.assertTrue(review.findings.filter(blocking=True).exists())

    def test_manual_allergy_review_is_required_without_structured_source(self):
        request = self._submitted_request()

        with self.assertRaises(PrescriptionValidationError):
            validate_medication_request(
                request_id=request.pk,
                actor=self.pharmacist,
                manual_allergy_review_confirmed=False,
            )

        request.refresh_from_db()
        self.assertEqual(request.status, MedicationRequest.Status.SUBMITTED)
        self.assertEqual(
            request.safety_reviews.latest("created_at").allergy_status,
            MedicationSafetyReview.AllergyStatus.UNAVAILABLE,
        )

    def test_validate_then_dispense_is_atomic_and_idempotent(self):
        request = self._submitted_request()
        request, _review = validate_medication_request(
            request_id=request.pk,
            actor=self.pharmacist,
            manual_allergy_review_confirmed=True,
        )
        stock_item = create_stock_item(
            actor=self.pharmacist,
            drug_id=self.drug_a.pk,
            storage_location="Farmácia teste",
        )
        lot = create_lot(
            actor=self.pharmacist,
            stock_item_id=stock_item.pk,
            lot_number="SYNTH-001",
            expires_on=timezone.localdate() + timedelta(days=30),
            initial_quantity=Decimal("10"),
        )
        request_item = request.items.get()
        operation_key = uuid.uuid4()
        allocation = {
            "request_item_id": request_item.pk,
            "lot_id": lot.pk,
            "quantity": Decimal("3"),
        }

        first = dispense_medication(
            request_id=request.pk,
            actor=self.pharmacist,
            operation_key=operation_key,
            allocations=[allocation],
        )
        second = dispense_medication(
            request_id=request.pk,
            actor=self.pharmacist,
            operation_key=operation_key,
            allocations=[allocation],
        )

        lot.refresh_from_db()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(lot.quantity_available, Decimal("7"))
        self.assertEqual(
            StockMovement.objects.filter(
                movement_type=StockMovement.Type.DISPENSE,
                operation_key=operation_key,
            ).count(),
            1,
        )

    def test_dispense_rejects_insufficient_locked_balance(self):
        request = self._submitted_request()
        request, _review = validate_medication_request(
            request_id=request.pk,
            actor=self.pharmacist,
            manual_allergy_review_confirmed=True,
        )
        stock_item = create_stock_item(
            actor=self.pharmacist,
            drug_id=self.drug_a.pk,
            storage_location="Farmácia saldo",
        )
        lot = create_lot(
            actor=self.pharmacist,
            stock_item_id=stock_item.pk,
            lot_number="SYNTH-LOW",
            expires_on=timezone.localdate() + timedelta(days=30),
            initial_quantity=Decimal("1"),
        )

        with self.assertRaises(DispenseStateError):
            dispense_medication(
                request_id=request.pk,
                actor=self.pharmacist,
                operation_key=uuid.uuid4(),
                allocations=[
                    {
                        "request_item_id": request.items.get().pk,
                        "lot_id": lot.pk,
                        "quantity": Decimal("2"),
                    }
                ],
            )

        lot.refresh_from_db()
        self.assertEqual(lot.quantity_available, Decimal("1"))
