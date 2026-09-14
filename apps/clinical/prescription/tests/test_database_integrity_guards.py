from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.utils import timezone

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.models import Encounter, Patient

from ..models import (
    Drug,
    MedicationDispense,
    MedicationDispenseItem,
    MedicationRequest,
    MedicationRequestItem,
    MedicationSafetyFinding,
    MedicationSafetyReview,
    StockMovement,
)
from ..stock_services import create_lot, create_stock_item


class PharmacyDatabaseMutationGuardTests(TestCase):
    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Os guards de integridade desta suíte são específicos do PostgreSQL.")

        self.actor = make_user("rx-database-guard-admin", role="ADM")
        self.actor.is_superuser = True
        self.actor.is_staff = True
        self.actor.save(update_fields=["is_superuser", "is_staff"])

        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="RX-DATABASE-GUARD-PATIENT",
            full_name="Pessoa Sintética Database Guard",
            birth_date=timezone.localdate() - timedelta(days=365 * 30),
            created_by=self.actor,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            started_at=timezone.now() - timedelta(hours=1),
            responsible_professional=self.actor,
            created_by=self.actor,
        )
        self.drug = Drug.objects.create(
            code="RX-DATABASE-GUARD-DRUG",
            name="Medicamento Sintético Database Guard",
            presentation="Apresentação sintética",
            dispense_unit="unidade",
        )
        self.request = MedicationRequest.objects.create(
            encounter=self.encounter,
            authored_by=self.actor,
        )
        self.request_item = MedicationRequestItem.objects.create(
            medication_request=self.request,
            drug=self.drug,
            dose=Decimal("1"),
            dose_unit="unidade",
            route="via sintética",
            frequency="frequência sintética",
            sequence=1,
        )
        self.request.status = MedicationRequest.Status.VALIDATED
        self.request.submitted_at = timezone.now() - timedelta(minutes=20)
        self.request.validated_by = self.actor
        self.request.validated_at = timezone.now() - timedelta(minutes=10)
        self.request.save()

        self.stock = create_stock_item(
            actor=self.actor,
            drug_id=self.drug.pk,
            storage_location="Farmácia database guard sintética",
            minimum_level=Decimal("0"),
        )
        self.lot = create_lot(
            actor=self.actor,
            stock_item_id=self.stock.pk,
            lot_number="DATABASE-GUARD-LOT-001",
            expires_on=timezone.localdate() + timedelta(days=90),
            initial_quantity=Decimal("10"),
        )

    def _review(self):
        return MedicationSafetyReview.objects.create(
            medication_request=self.request,
            reviewed_by=self.actor,
            allergy_status=MedicationSafetyReview.AllergyStatus.UNAVAILABLE,
            dose_status=MedicationSafetyReview.DoseStatus.NOT_EVALUABLE,
            blocking_findings=0,
            warning_findings=0,
            reference_version="SYNTHETIC-TEST",
        )

    def _dispense(self):
        return MedicationDispense.objects.create(
            medication_request=self.request,
            dispensed_by=self.actor,
            dispensed_at=timezone.now(),
        )

    def _assert_update_rejected(self, queryset, **changes):
        with self.assertRaises(IntegrityError), transaction.atomic():
            queryset.update(**changes)

    def test_safety_review_bulk_update_is_rejected_by_database(self):
        review = self._review()

        self._assert_update_rejected(
            MedicationSafetyReview.objects.filter(pk=review.pk),
            reference_version="ALTERED",
        )

        review.refresh_from_db()
        self.assertEqual(review.reference_version, "SYNTHETIC-TEST")

    def test_safety_finding_bulk_update_is_rejected_by_database(self):
        review = self._review()
        finding = MedicationSafetyFinding.objects.create(
            review=review,
            kind=MedicationSafetyFinding.Kind.DOSE,
            request_item=self.request_item,
            severity="SYNTHETIC",
            blocking=False,
        )

        self._assert_update_rejected(
            MedicationSafetyFinding.objects.filter(pk=finding.pk),
            severity="ALTERED",
        )

        finding.refresh_from_db()
        self.assertEqual(finding.severity, "SYNTHETIC")

    def test_dispense_bulk_update_is_rejected_by_database(self):
        dispense = self._dispense()
        original_dispensed_at = dispense.dispensed_at

        self._assert_update_rejected(
            MedicationDispense.objects.filter(pk=dispense.pk),
            dispensed_at=timezone.now() + timedelta(hours=1),
        )

        dispense.refresh_from_db()
        self.assertEqual(dispense.dispensed_at, original_dispensed_at)

    def test_dispense_item_bulk_update_is_rejected_by_database(self):
        dispense = self._dispense()
        item = MedicationDispenseItem.objects.create(
            dispense=dispense,
            request_item=self.request_item,
            lot=self.lot,
            quantity=Decimal("1"),
        )

        self._assert_update_rejected(
            MedicationDispenseItem.objects.filter(pk=item.pk),
            quantity=Decimal("2"),
        )

        item.refresh_from_db()
        self.assertEqual(item.quantity, Decimal("1"))

    def test_stock_movement_bulk_update_is_rejected_by_database(self):
        movement = self.lot.movements.get(movement_type=StockMovement.Type.RECEIPT)
        original_reason = movement.reason

        self._assert_update_rejected(
            StockMovement.objects.filter(pk=movement.pk),
            reason="ALTERED",
        )

        movement.refresh_from_db()
        self.assertEqual(movement.reason, original_reason)

    def test_submitted_request_item_bulk_update_is_rejected_by_database(self):
        self._assert_update_rejected(
            MedicationRequestItem.objects.filter(pk=self.request_item.pk),
            dose=Decimal("2"),
        )

        self.request_item.refresh_from_db()
        self.assertEqual(self.request_item.dose, Decimal("1"))

    def test_draft_request_item_bulk_update_remains_allowed(self):
        draft_request = MedicationRequest.objects.create(
            encounter=self.encounter,
            authored_by=self.actor,
        )
        draft_item = MedicationRequestItem.objects.create(
            medication_request=draft_request,
            drug=self.drug,
            dose=Decimal("1"),
            dose_unit="unidade",
            route="via sintética",
            frequency="frequência sintética",
            sequence=1,
        )

        updated = MedicationRequestItem.objects.filter(pk=draft_item.pk).update(
            dose=Decimal("2")
        )

        self.assertEqual(updated, 1)
        draft_item.refresh_from_db()
        self.assertEqual(draft_item.dose, Decimal("2"))

    def test_draft_item_cannot_be_bulk_moved_to_non_draft_request(self):
        draft_request = MedicationRequest.objects.create(
            encounter=self.encounter,
            authored_by=self.actor,
        )
        draft_item = MedicationRequestItem.objects.create(
            medication_request=draft_request,
            drug=self.drug,
            dose=Decimal("1"),
            dose_unit="unidade",
            route="via sintética",
            frequency="frequência sintética",
            sequence=1,
        )

        self._assert_update_rejected(
            MedicationRequestItem.objects.filter(pk=draft_item.pk),
            medication_request_id=self.request.pk,
        )

        draft_item.refresh_from_db()
        self.assertEqual(draft_item.medication_request_id, draft_request.pk)
