import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse
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

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES)
class MedicationAdministrationViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.bootstrap_admin = user_model.objects.create_superuser(
            username="nursing-admin-bootstrap",
            email="nursing-admin-bootstrap@example.invalid",
            password="StrongPass!2026",
        )
        self.nurse = user_model.objects.create_user(
            username="nursing-admin-view",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.other = user_model.objects.create_user(
            username="nursing-admin-view-other",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.administer_permission = Permission.objects.get(
            content_type__app_label="nursing",
            codename="administer_medication",
        )
        self.nurse.user_permissions.add(self.administer_permission)

        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="NUR-ADMIN-VIEW",
            full_name="Paciente Administração View",
            birth_date=date(1989, 2, 3),
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
            code="NUR-ADMIN-VIEW-DRUG",
            name="Medicamento Administração View",
            presentation="Comprimido sintético",
            dispense_unit="comprimido",
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
            storage_location="Farmácia Administração View",
        )
        self.lot = Lot.objects.create(
            stock_item=self.stock,
            lot_number="NUR-ADMIN-VIEW-LOT",
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
        self.client.force_login(self.nurse)

    def _administered_at(self):
        return timezone.localtime(timezone.now() - timedelta(minutes=2)).strftime(
            "%Y-%m-%dT%H:%M:%S"
        )

    def _post_data(self, *, operation_key=None, **overrides):
        data = {
            "operation_key": str(operation_key or uuid.uuid4()),
            "administered_at": self._administered_at(),
            "administered_dose": "10.0000",
            "administered_dose_unit": "mg",
        }
        data.update(overrides)
        return data

    def _clear_permission_cache(self):
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            if hasattr(self.nurse, cache_name):
                delattr(self.nurse, cache_name)

    def test_medication_list_is_scoped_and_no_store(self):
        response = self.client.get(
            reverse("nursing:medication_list", kwargs={"encounter_id": self.encounter.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertContains(response, self.drug.name)
        self.assertContains(response, self.lot.lot_number)
        self.assertContains(response, "Confirmar administração")

    def test_administration_form_is_network_only_and_does_not_infer_dose(self):
        response = self.client.get(
            reverse(
                "nursing:medication_administer",
                kwargs={"dispense_item_id": self.dispense_item.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertNotIn("administered_dose", form.initial)
        self.assertNotIn("administered_dose_unit", form.initial)
        self.assertContains(response, "exclusivamente online")
        self.assertNotContains(response, "offline_queue.js")
        self.assertNotContains(response, "vitals_offline.js")
        self.assertNotContains(response, "data-nursing-vitals-offline")

    def test_post_creates_traceable_administration(self):
        response = self.client.post(
            reverse(
                "nursing:medication_administer",
                kwargs={"dispense_item_id": self.dispense_item.pk},
            ),
            data=self._post_data(administered_dose="7.5000", administered_dose_unit="mL"),
        )

        self.assertRedirects(
            response,
            reverse("nursing:medication_list", kwargs={"encounter_id": self.encounter.pk}),
            fetch_redirect_response=False,
        )
        administration = MedicationAdministration.objects.get()
        self.assertEqual(administration.dispense_item, self.dispense_item)
        self.assertEqual(administration.dispense_item.lot, self.lot)
        self.assertEqual(administration.administered_by, self.nurse)
        self.assertEqual(administration.administered_dose, Decimal("7.5000"))
        self.assertEqual(administration.administered_dose_unit, "mL")

    def test_exact_post_retry_does_not_duplicate_administration(self):
        operation_key = uuid.uuid4()
        data = self._post_data(operation_key=operation_key)
        url = reverse(
            "nursing:medication_administer",
            kwargs={"dispense_item_id": self.dispense_item.pk},
        )

        first = self.client.post(url, data=data)
        second = self.client.post(url, data=data)

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(MedicationAdministration.objects.count(), 1)
        self.assertEqual(MedicationAdministration.objects.get().operation_key, operation_key)

    def test_same_operation_key_with_changed_dose_returns_safe_conflict(self):
        operation_key = uuid.uuid4()
        url = reverse(
            "nursing:medication_administer",
            kwargs={"dispense_item_id": self.dispense_item.pk},
        )
        self.client.post(url, data=self._post_data(operation_key=operation_key))

        response = self.client.post(
            url,
            data=self._post_data(
                operation_key=operation_key,
                administered_dose="5.0000",
            ),
        )

        self.assertEqual(response.status_code, 409)
        self.assertContains(
            response,
            "não corresponde à operação já registrada",
            status_code=409,
        )
        self.assertEqual(MedicationAdministration.objects.count(), 1)

    def test_missing_capability_returns_403(self):
        self.nurse.user_permissions.remove(self.administer_permission)
        self._clear_permission_cache()

        response = self.client.get(
            reverse("nursing:medication_list", kwargs={"encounter_id": self.encounter.pk})
        )

        self.assertEqual(response.status_code, 403)

    def test_item_outside_pep_scope_returns_404(self):
        outside_patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="NUR-ADMIN-OUTSIDE",
            full_name="Paciente Fora do Escopo",
            birth_date=date(1991, 3, 4),
            created_by=self.other,
        )
        outside_encounter = Encounter.objects.create(
            patient=outside_patient,
            status=Encounter.Status.OPEN,
            started_at=timezone.now() - timedelta(hours=1),
            responsible_professional=self.other,
            created_by=self.other,
        )
        outside_request = MedicationRequest.objects.create(
            encounter=outside_encounter,
            authored_by=self.other,
        )
        outside_item = MedicationRequestItem.objects.create(
            medication_request=outside_request,
            drug=self.drug,
            dose=Decimal("10"),
            dose_unit="mg",
            route="oral",
            frequency="1x ao dia",
            sequence=1,
        )
        outside_request.status = MedicationRequest.Status.VALIDATED
        outside_request.submitted_at = timezone.now() - timedelta(minutes=30)
        outside_request.validated_by = self.other
        outside_request.validated_at = timezone.now() - timedelta(minutes=20)
        outside_request.save()
        outside_dispense = MedicationDispense.objects.create(
            medication_request=outside_request,
            dispensed_by=self.other,
            dispensed_at=timezone.now() - timedelta(minutes=10),
        )
        outside_dispense_item = MedicationDispenseItem.objects.create(
            dispense=outside_dispense,
            request_item=outside_item,
            lot=self.lot,
            quantity=Decimal("1"),
        )

        response = self.client.get(
            reverse(
                "nursing:medication_administer",
                kwargs={"dispense_item_id": outside_dispense_item.pk},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_cancelled_prescription_is_not_listed_and_cannot_be_administered(self):
        self.request.status = MedicationRequest.Status.CANCELLED
        self.request.cancelled_by = self.nurse
        self.request.cancelled_at = timezone.now()
        self.request.cancellation_reason = "Cancelamento sintético"
        self.request.save()

        list_response = self.client.get(
            reverse("nursing:medication_list", kwargs={"encounter_id": self.encounter.pk})
        )
        administer_response = self.client.get(
            reverse(
                "nursing:medication_administer",
                kwargs={"dispense_item_id": self.dispense_item.pk},
            )
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertNotContains(list_response, self.drug.name)
        self.assertEqual(administer_response.status_code, 403)

    def test_closed_encounter_blocks_medication_list(self):
        self.encounter.status = Encounter.Status.CLOSED
        self.encounter.ended_at = timezone.now()
        self.encounter.save()

        response = self.client.get(
            reverse("nursing:medication_list", kwargs={"encounter_id": self.encounter.pk})
        )

        self.assertEqual(response.status_code, 403)

    def test_post_requires_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.nurse)

        response = csrf_client.post(
            reverse(
                "nursing:medication_administer",
                kwargs={"dispense_item_id": self.dispense_item.pk},
            ),
            data=self._post_data(),
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(MedicationAdministration.objects.exists())
