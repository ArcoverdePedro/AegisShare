from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.models import Encounter, Patient, PatientAccessGrant

from ..models import (
    Drug,
    Lot,
    MedicationDispense,
    MedicationDispenseItem,
    MedicationRequest,
    MedicationRequestItem,
    StockItem,
)
from .surface_contract import RX_GET_SURFACE_NAMES

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES)
class PrescriptionResponseCachePolicyTests(TestCase):
    def setUp(self):
        self.admin = make_user("rx-cache-admin", role="ADM")
        self.admin.is_superuser = True
        self.admin.is_staff = True
        self.admin.save(update_fields=["is_superuser", "is_staff"])

        self.user = make_user("rx-cache-user", role="FUNC")
        self._grant_permissions(
            "view_medication_request",
            "prescribe_medication",
            "validate_medication_request",
            "view_medication_dispense",
            "dispense_medication",
            "view_drug",
            "manage_drug_catalog",
            "view_pharmacy_stock",
        )
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="RX-CACHE-PATIENT",
            full_name="Paciente Sintético Cache",
            birth_date=timezone.localdate() - timedelta(days=365 * 30),
            created_by=self.admin,
        )
        PatientAccessGrant.objects.create(
            patient=self.patient,
            user=self.user,
            granted_by=self.admin,
            reason="Cobertura sintética cache",
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            responsible_professional=self.user,
            created_by=self.admin,
        )
        self.drug = Drug.objects.create(
            code="RX-CACHE-001",
            name="Medicamento Sintético Cache",
            presentation="Apresentação sintética",
            dispense_unit="unidade",
        )
        self.prescription = MedicationRequest.objects.create(
            encounter=self.encounter,
            authored_by=self.user,
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
        self.prescription.validated_by = self.user
        self.prescription.validated_at = now
        self.prescription.save()
        stock_item = StockItem.objects.create(
            drug=self.drug,
            storage_location="Farmácia cache",
        )
        lot = Lot.objects.create(
            stock_item=stock_item,
            lot_number="CACHE-LOT",
            expires_on=timezone.localdate() + timedelta(days=30),
            quantity_available=Decimal("5"),
        )
        self.dispense = MedicationDispense.objects.create(
            medication_request=self.prescription,
            dispensed_by=self.user,
            dispensed_at=now,
        )
        MedicationDispenseItem.objects.create(
            dispense=self.dispense,
            request_item=self.request_item,
            lot=lot,
            quantity=Decimal("1"),
        )
        self.client.force_login(self.user)

    def _grant_permissions(self, *codenames):
        permissions = Permission.objects.filter(
            content_type__app_label="prescription",
            codename__in=codenames,
        )
        self.user.user_permissions.add(*permissions)
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            if hasattr(self.user, cache_name):
                delattr(self.user, cache_name)

    def assert_private_no_store(self, response):
        self.assertEqual(response.status_code, 200)
        cache_control = {
            directive.strip()
            for directive in response["Cache-Control"].split(",")
        }
        self.assertEqual(cache_control, {"private", "no-store", "max-age=0"})

        vary = {value.strip().lower() for value in response["Vary"].split(",")}
        self.assertIn("cookie", vary)
        self.assertIn("hx-request", vary)

    def test_every_reviewed_rx_get_surface_is_private_and_no_store(self):
        routes = {
            "prescription_list": reverse("prescription:prescription_list"),
            "prescription_create": reverse("prescription:prescription_create"),
            "prescription_detail": reverse(
                "prescription:prescription_detail",
                kwargs={"pk": self.prescription.pk},
            ),
            "prescription_validate": reverse(
                "prescription:prescription_validate",
                kwargs={"pk": self.prescription.pk},
            ),
            "dispense_create": reverse(
                "prescription:dispense_create",
                kwargs={"pk": self.prescription.pk},
            ),
            "dispense_list": reverse("prescription:dispense_list"),
            "dispense_detail": reverse(
                "prescription:dispense_detail",
                kwargs={"pk": self.dispense.pk},
            ),
            "drug_catalog": reverse("prescription:drug_catalog"),
            "drug_create": reverse("prescription:drug_create"),
            "drug_update": reverse(
                "prescription:drug_update",
                kwargs={"pk": self.drug.pk},
            ),
            "pharmacy_stock": reverse("prescription:pharmacy_stock"),
        }
        self.assertEqual(set(routes), RX_GET_SURFACE_NAMES)

        for name, route in routes.items():
            with self.subTest(name=name, route=route):
                self.assert_private_no_store(self.client.get(route))
