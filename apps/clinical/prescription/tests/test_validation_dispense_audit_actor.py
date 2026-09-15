import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from auditlog.models import LogEntry
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.models import Encounter, Patient, PatientAccessGrant

from ..dispense_services import dispense_medication
from ..models import (
    Drug,
    MedicationDispense,
    MedicationDispenseItem,
    MedicationRequest,
    MedicationSafetyFinding,
    MedicationSafetyReview,
    StockMovement,
)
from ..services import (
    add_medication_request_item,
    create_medication_request,
    submit_medication_request,
    validate_medication_request,
)
from ..stock_services import create_lot, create_stock_item


class ValidationDispenseAuditActorTests(TestCase):
    def setUp(self):
        self.admin = make_user("rx-final-audit-admin", role="ADM")
        self.prescriber = make_user("rx-final-audit-prescriber", role="FUNC")
        self.pharmacist = make_user("rx-final-audit-pharmacist", role="FUNC")
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="RX-FINAL-AUDIT-PATIENT",
            full_name="Paciente Sintético Auditoria Final RX",
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
                reason="Cobertura sintética de auditoria final RX",
            )
        self._grant(self.prescriber, "prescribe_medication")
        for codename in (
            "validate_medication_request",
            "dispense_medication",
            "manage_pharmacy_stock",
        ):
            self._grant(self.pharmacist, codename)
        self.drug = Drug.objects.create(
            code="RX-FINAL-AUDIT-DRUG",
            name="Medicamento Sintético Auditoria Final",
            presentation="Comprimido sintético",
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

    def _entry(self, model, object_pk, action):
        return LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(model),
            object_pk=str(object_pk),
            action=action,
        ).latest("timestamp")

    def test_validation_and_dispense_writes_keep_explicit_pharmacist_actor(self):
        request = create_medication_request(
            encounter_id=self.encounter.pk,
            actor=self.prescriber,
        )
        item = add_medication_request_item(
            request_id=request.pk,
            actor=self.prescriber,
            drug_id=self.drug.pk,
            dose=Decimal("10"),
            dose_unit="mg",
            route="oral",
            frequency="1x ao dia",
            sequence=1,
        )
        with patch("apps.clinical.prescription.services.emit_prescription_event"):
            submit_medication_request(request_id=request.pk, actor=self.prescriber)

        with patch("apps.clinical.prescription.services.emit_prescription_event"):
            validated, review = validate_medication_request(
                request_id=request.pk,
                actor=self.pharmacist,
                manual_allergy_review_confirmed=True,
            )
        finding = review.findings.get()

        self.assertEqual(
            self._entry(
                MedicationSafetyReview,
                review.pk,
                LogEntry.Action.CREATE,
            ).actor,
            self.pharmacist,
        )
        self.assertEqual(
            self._entry(
                MedicationSafetyFinding,
                finding.pk,
                LogEntry.Action.CREATE,
            ).actor,
            self.pharmacist,
        )
        self.assertEqual(
            self._entry(
                MedicationRequest,
                validated.pk,
                LogEntry.Action.UPDATE,
            ).actor,
            self.pharmacist,
        )

        stock_item = create_stock_item(
            actor=self.pharmacist,
            drug_id=self.drug.pk,
            storage_location="Farmácia auditoria final",
        )
        lot = create_lot(
            actor=self.pharmacist,
            stock_item_id=stock_item.pk,
            lot_number="FINAL-AUDIT-LOT",
            expires_on=timezone.localdate() + timedelta(days=30),
            initial_quantity=Decimal("5"),
        )
        with (
            patch("apps.clinical.prescription.dispense_services.emit_medication_dispensed_event"),
            patch("apps.clinical.prescription.dispense_services.emit_stock_low_event"),
        ):
            dispense = dispense_medication(
                request_id=validated.pk,
                actor=self.pharmacist,
                operation_key=uuid.uuid4(),
                allocations=[
                    {
                        "request_item_id": item.pk,
                        "lot_id": lot.pk,
                        "quantity": Decimal("1"),
                    }
                ],
            )
        dispense_item = dispense.items.get()
        movement = StockMovement.objects.get(dispense_item=dispense_item)

        for model, object_pk in (
            (MedicationDispense, dispense.pk),
            (MedicationDispenseItem, dispense_item.pk),
            (StockMovement, movement.pk),
        ):
            with self.subTest(model=model.__name__):
                self.assertEqual(
                    self._entry(model, object_pk, LogEntry.Action.CREATE).actor,
                    self.pharmacist,
                )
