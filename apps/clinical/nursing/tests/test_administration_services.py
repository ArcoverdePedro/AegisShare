import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.clinical.pep.models import Encounter, Patient
from apps.clinical.prescription.models import (
    Drug,
    Lot,
    MedicationDispense,
    MedicationDispenseItem,
    MedicationRequest,
    MedicationRequestItem,
    StockItem,
)

from ..models import MedicationAdministration
from ..services import (
    MedicationAdministrationIdempotencyConflictError,
    MedicationAdministrationStateError,
    administer_medication,
)


class MedicationAdministrationServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.nurse = user_model.objects.create_user(
            username="nursing-admin-service",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.other = user_model.objects.create_user(
            username="nursing-admin-service-other",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.permission = Permission.objects.get(
            content_type__app_label="nursing",
            codename="administer_medication",
        )
        self.nurse.user_permissions.add(self.permission)

        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="NUR-ADMIN-SVC",
            full_name="Paciente Administração Serviço",
            birth_date=date(1990, 1, 1),
            created_by=self.nurse,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            status=Encounter.Status.OPEN,
            started_at=timezone.now() - timedelta(hours=1),
            responsible_professional=self.nurse,
            created_by=self.nurse,
        )
        self.drug = Drug.objects.create(
            code="NUR-ADMIN-SVC-DRUG",
            name="Medicamento Administração Serviço",
            presentation="Apresentação sintética",
            dispense_unit="unidade",
        )
        self.request = MedicationRequest.objects.create(
            encounter=self.encounter,
            authored_by=self.nurse,
        )
        self.request_item = MedicationRequestItem.objects.create(
            medication_request=self.request,
            drug=self.drug,
            dose=Decimal("10"),
            dose_unit="mg",
            route="oral",
            frequency="1x ao dia",
            sequence=1,
        )
        self.request.status = MedicationRequest.Status.VALIDATED
        self.request.submitted_at = timezone.now() - timedelta(minutes=30)
        self.request.validated_by = self.nurse
        self.request.validated_at = timezone.now() - timedelta(minutes=20)
        self.request.save()

        self.stock = StockItem.objects.create(
            drug=self.drug,
            storage_location="Farmácia Enfermagem Serviço",
        )
        self.lot = Lot.objects.create(
            stock_item=self.stock,
            lot_number="NUR-ADMIN-LOT-001",
            expires_on=timezone.localdate() + timedelta(days=90),
            quantity_available=Decimal("10"),
        )
        self.dispense = MedicationDispense.objects.create(
            medication_request=self.request,
            dispensed_by=self.nurse,
            dispensed_at=timezone.now() - timedelta(minutes=10),
        )
        self.dispense_item = MedicationDispenseItem.objects.create(
            dispense=self.dispense,
            request_item=self.request_item,
            lot=self.lot,
            quantity=Decimal("2"),
        )
        self.administered_at = timezone.now().replace(microsecond=0) - timedelta(minutes=2)

    def _data(self, **overrides):
        data = {
            "administered_at": self.administered_at,
            "administered_dose": Decimal("10"),
            "administered_dose_unit": "mg",
        }
        data.update(overrides)
        return data

    def _clear_permission_cache(self):
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            if hasattr(self.nurse, cache_name):
                delattr(self.nurse, cache_name)

    def test_same_operation_retry_returns_existing_administration(self):
        operation_key = uuid.uuid4()
        data = self._data()

        first = administer_medication(
            dispense_item_id=self.dispense_item.pk,
            actor=self.nurse,
            data=data,
            operation_key=operation_key,
        )
        second = administer_medication(
            dispense_item_id=self.dispense_item.pk,
            actor=self.nurse,
            data=data,
            operation_key=operation_key,
        )

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(MedicationAdministration.objects.count(), 1)

    def test_same_operation_key_with_different_payload_is_conflict(self):
        operation_key = uuid.uuid4()
        administer_medication(
            dispense_item_id=self.dispense_item.pk,
            actor=self.nurse,
            data=self._data(),
            operation_key=operation_key,
        )

        with self.assertRaises(MedicationAdministrationIdempotencyConflictError):
            administer_medication(
                dispense_item_id=self.dispense_item.pk,
                actor=self.nurse,
                data=self._data(administered_dose=Decimal("5")),
                operation_key=operation_key,
            )

        self.assertEqual(MedicationAdministration.objects.count(), 1)

    def test_retry_revalidates_permission_before_acknowledging_existing_record(self):
        operation_key = uuid.uuid4()
        administer_medication(
            dispense_item_id=self.dispense_item.pk,
            actor=self.nurse,
            data=self._data(),
            operation_key=operation_key,
        )
        self.nurse.user_permissions.remove(self.permission)
        self._clear_permission_cache()

        with self.assertRaises(PermissionDenied):
            administer_medication(
                dispense_item_id=self.dispense_item.pk,
                actor=self.nurse,
                data=self._data(),
                operation_key=operation_key,
            )

        self.assertEqual(MedicationAdministration.objects.count(), 1)

    def test_cancelled_prescription_blocks_new_administration(self):
        self.request.status = MedicationRequest.Status.CANCELLED
        self.request.cancelled_by = self.nurse
        self.request.cancelled_at = timezone.now()
        self.request.cancellation_reason = "Cancelamento sintético de teste"
        self.request.save()

        with self.assertRaises(PermissionDenied):
            administer_medication(
                dispense_item_id=self.dispense_item.pk,
                actor=self.nurse,
                data=self._data(),
                operation_key=uuid.uuid4(),
            )

        self.assertFalse(MedicationAdministration.objects.exists())

    def test_closed_encounter_blocks_new_administration(self):
        self.encounter.status = Encounter.Status.CLOSED
        self.encounter.ended_at = timezone.now()
        self.encounter.save()

        with self.assertRaises(PermissionDenied):
            administer_medication(
                dispense_item_id=self.dispense_item.pk,
                actor=self.nurse,
                data=self._data(),
                operation_key=uuid.uuid4(),
            )

        self.assertFalse(MedicationAdministration.objects.exists())

    def test_incompatible_request_item_chain_is_rejected(self):
        other_request = MedicationRequest.objects.create(
            encounter=self.encounter,
            authored_by=self.nurse,
        )
        other_item = MedicationRequestItem.objects.create(
            medication_request=other_request,
            drug=self.drug,
            dose=Decimal("5"),
            dose_unit="mg",
            route="oral",
            frequency="1x ao dia",
            sequence=1,
        )
        incompatible = MedicationDispenseItem.objects.create(
            dispense=self.dispense,
            request_item=other_item,
            lot=self.lot,
            quantity=Decimal("1"),
        )

        with self.assertRaises(MedicationAdministrationStateError):
            administer_medication(
                dispense_item_id=incompatible.pk,
                actor=self.nurse,
                data=self._data(),
                operation_key=uuid.uuid4(),
            )

    def test_unit_is_normalized_without_converting_dose(self):
        administration = administer_medication(
            dispense_item_id=self.dispense_item.pk,
            actor=self.nurse,
            data=self._data(
                administered_dose=Decimal("1.2500"),
                administered_dose_unit="  mL   sintético  ",
            ),
            operation_key=uuid.uuid4(),
        )

        self.assertEqual(administration.administered_dose, Decimal("1.2500"))
        self.assertEqual(administration.administered_dose_unit, "mL sintético")

    def test_administration_before_dispense_is_rejected(self):
        with self.assertRaises(MedicationAdministrationStateError):
            administer_medication(
                dispense_item_id=self.dispense_item.pk,
                actor=self.nurse,
                data=self._data(
                    administered_at=self.dispense.dispensed_at.replace(microsecond=0)
                    - timedelta(seconds=1)
                ),
                operation_key=uuid.uuid4(),
            )

        self.assertFalse(MedicationAdministration.objects.exists())

    def test_invalid_operation_key_is_safe_conflict(self):
        with self.assertRaises(MedicationAdministrationIdempotencyConflictError):
            administer_medication(
                dispense_item_id=self.dispense_item.pk,
                actor=self.nurse,
                data=self._data(),
                operation_key="invalid-key",
            )

        self.assertFalse(MedicationAdministration.objects.exists())

    def test_confirmed_administration_is_append_only(self):
        administration = administer_medication(
            dispense_item_id=self.dispense_item.pk,
            actor=self.nurse,
            data=self._data(),
            operation_key=uuid.uuid4(),
        )
        administration.administered_dose = Decimal("5")

        with self.assertRaisesMessage(ValidationError, "append-only"):
            administration.save()

        with self.assertRaisesMessage(ValidationError, "não podem ser excluídas"):
            administration.delete()
