from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.clinical.pep.models import Encounter, Patient

from ..models import (
    Drug,
    Lot,
    MedicationDispense,
    MedicationDispenseItem,
    MedicationRequest,
    MedicationRequestItem,
    StockItem,
)

User = get_user_model()

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES)
class AnonymousRxBoundaryTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="rx-anonymous-boundary-admin",
            password="test-password",
            nivel_permissao="ADM",
        )
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="RX-ANON-PATIENT-SECRET",
            full_name="Paciente Sentinela Anônimo",
            birth_date=timezone.localdate() - timedelta(days=365 * 30),
            created_by=self.admin,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            responsible_professional=self.admin,
            created_by=self.admin,
        )
        self.drug = Drug.objects.create(
            code="RX-ANON-BOUNDARY",
            name="Medicamento Sentinela Anônimo",
            presentation="Apresentação sigilosa sintética",
            dispense_unit="unidade",
        )
        self.stock = StockItem.objects.create(
            drug=self.drug,
            storage_location="Farmácia Sentinela Anônima",
            minimum_level=Decimal("1"),
        )
        self.lot = Lot.objects.create(
            stock_item=self.stock,
            lot_number="ANON-LOT-SECRET",
            expires_on=timezone.localdate() + timedelta(days=30),
            quantity_available=Decimal("5"),
        )
        self.prescription = MedicationRequest.objects.create(
            encounter=self.encounter,
            authored_by=self.admin,
        )
        self.request_item = MedicationRequestItem.objects.create(
            medication_request=self.prescription,
            drug=self.drug,
            dose=Decimal("1"),
            dose_unit="mg",
            route="oral",
            frequency="1x ao dia",
            sequence=1,
        )
        now = timezone.now()
        self.prescription.status = MedicationRequest.Status.VALIDATED
        self.prescription.submitted_at = now
        self.prescription.validated_by = self.admin
        self.prescription.validated_at = now
        self.prescription.save()
        self.dispense = MedicationDispense.objects.create(
            medication_request=self.prescription,
            dispensed_by=self.admin,
            dispensed_at=now,
        )
        MedicationDispenseItem.objects.create(
            dispense=self.dispense,
            request_item=self.request_item,
            lot=self.lot,
            quantity=Decimal("1"),
        )

    def test_current_rx_get_surfaces_redirect_anonymous_without_data_leak(self):
        paths = [
            reverse("prescription:prescription_list"),
            reverse("prescription:prescription_create"),
            reverse("prescription:prescription_detail", kwargs={"pk": self.prescription.pk}),
            reverse("prescription:prescription_validate", kwargs={"pk": self.prescription.pk}),
            reverse("prescription:dispense_create", kwargs={"pk": self.prescription.pk}),
            reverse("prescription:dispense_list"),
            reverse("prescription:dispense_detail", kwargs={"pk": self.dispense.pk}),
            reverse("prescription:drug_catalog"),
            reverse("prescription:drug_create"),
            reverse("prescription:drug_update", kwargs={"pk": self.drug.pk}),
            reverse("prescription:pharmacy_stock"),
        ]
        forbidden_markers = [
            self.patient.identifier,
            self.patient.full_name,
            self.drug.code,
            self.drug.name,
            self.drug.presentation,
            self.stock.storage_location,
            self.lot.lot_number,
        ]

        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path, follow=True)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.redirect_chain)
                redirect_url, redirect_status = response.redirect_chain[0]
                self.assertEqual(redirect_status, 302)
                self.assertTrue(redirect_url.startswith("/login/?next="))
                self.assertEqual(response.resolver_match.url_name, "login")

                body = response.content.decode("utf-8")
                for marker in forbidden_markers:
                    self.assertNotIn(marker, body)

    def test_post_only_rx_surfaces_redirect_anonymous_before_processing(self):
        for path in [
            reverse("prescription:prescription_submit", kwargs={"pk": self.prescription.pk}),
            reverse("prescription:prescription_cancel", kwargs={"pk": self.prescription.pk}),
        ]:
            with self.subTest(path=path):
                response = self.client.post(path, follow=True)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.redirect_chain)
                self.assertEqual(response.resolver_match.url_name, "login")
