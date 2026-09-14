from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
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
)
from ..stock_services import create_lot, create_stock_item


class PharmacyAppendOnlyIntegrityTests(TestCase):
    def setUp(self):
        self.actor = make_user("rx-append-only-admin", role="ADM")
        self.actor.is_superuser = True
        self.actor.is_staff = True
        self.actor.save(update_fields=["is_superuser", "is_staff"])

        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="RX-APPEND-ONLY-PATIENT",
            full_name="Pessoa Sintética Append Only",
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
            code="RX-APPEND-ONLY-DRUG",
            name="Medicamento Sintético Append Only",
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
            storage_location="Farmácia append-only sintética",
            minimum_level=Decimal("0"),
        )
        self.lot = create_lot(
            actor=self.actor,
            stock_item_id=self.stock.pk,
            lot_number="APPEND-ONLY-LOT-001",
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

    def test_safety_review_cannot_be_bulk_deleted(self):
        review = self._review()

        with self.assertRaises(ValidationError):
            MedicationSafetyReview.objects.filter(pk=review.pk).delete()

        self.assertTrue(MedicationSafetyReview.objects.filter(pk=review.pk).exists())

    def test_safety_finding_cannot_be_bulk_deleted(self):
        review = self._review()
        finding = MedicationSafetyFinding.objects.create(
            review=review,
            kind=MedicationSafetyFinding.Kind.DOSE,
            request_item=self.request_item,
            severity="SYNTHETIC",
            blocking=False,
        )

        with self.assertRaises(ValidationError):
            MedicationSafetyFinding.objects.filter(pk=finding.pk).delete()

        self.assertTrue(MedicationSafetyFinding.objects.filter(pk=finding.pk).exists())

    def test_dispense_cannot_be_bulk_deleted(self):
        dispense = self._dispense()

        with self.assertRaises(ValidationError):
            MedicationDispense.objects.filter(pk=dispense.pk).delete()

        self.assertTrue(MedicationDispense.objects.filter(pk=dispense.pk).exists())

    def test_dispense_item_cannot_be_bulk_deleted(self):
        dispense = self._dispense()
        item = MedicationDispenseItem.objects.create(
            dispense=dispense,
            request_item=self.request_item,
            lot=self.lot,
            quantity=Decimal("1"),
        )

        with self.assertRaises(ValidationError):
            MedicationDispenseItem.objects.filter(pk=item.pk).delete()

        self.assertTrue(MedicationDispenseItem.objects.filter(pk=item.pk).exists())
