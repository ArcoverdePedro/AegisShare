import uuid

from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.urls import reverse

from ..lifecycle import change_bed_status, discharge_patient, transfer_patient
from ..models import Bed, BedStatusChange, Discharge
from ..services import AdtConflictError, BedUnavailableError
from . import test_lifecycle


@override_settings(STORAGES=test_lifecycle.TEST_STORAGES)
class BedStatusTests(TestCase):
    setUp = test_lifecycle.AdtLifecycleTests.setUp
    _grant = test_lifecycle.AdtLifecycleTests._grant

    def discharge(self):
        self._grant("discharge_patient")
        return discharge_patient(
            admission_id=self.admission.pk,
            disposition=Discharge.Disposition.HOME,
            actor=self.employee,
            operation_key=uuid.uuid4(),
            reason="Alta",
        )

    def test_discharge_leaves_bed_pending_cleaning_until_released(self):
        self.discharge()
        self.source_bed.refresh_from_db()
        self.assertEqual(self.source_bed.operational_status, Bed.OperationalStatus.CLEANING)
        self.assertEqual(BedStatusChange.objects.get().to_status, "CLEANING")

        self._grant("transfer_patient")
        with self.assertRaises(PermissionDenied):
            change_bed_status(
                actor=self.employee, bed_id=self.source_bed.pk, status="AVAILABLE", reason="ok"
            )
        self._grant("manage_bed_status")
        change_bed_status(
            actor=self.employee, bed_id=self.source_bed.pk, status="AVAILABLE", reason="Limpo"
        )
        self.source_bed.refresh_from_db()
        self.assertEqual(self.source_bed.operational_status, Bed.OperationalStatus.AVAILABLE)
        self.assertEqual(BedStatusChange.objects.count(), 2)

    def test_cleaning_bed_cannot_receive_transfer(self):
        self.destination_bed.operational_status = Bed.OperationalStatus.CLEANING
        self.destination_bed.save()
        self._grant("transfer_patient")

        with self.assertRaises(BedUnavailableError):
            transfer_patient(
                admission_id=self.admission.pk,
                destination_bed_id=self.destination_bed.pk,
                actor=self.employee,
                operation_key=uuid.uuid4(),
                reason="Mudança",
            )

    def test_occupied_bed_and_missing_reason_are_refused(self):
        self._grant("manage_bed_status")
        for status, reason in (("BLOCKED", "Manutenção"), ("CLEANING", " ")):
            with self.subTest(status=status), self.assertRaises(AdtConflictError):
                change_bed_status(
                    actor=self.employee, bed_id=self.source_bed.pk, status=status, reason=reason
                )
        with self.assertRaises(PermissionDenied):
            change_bed_status(
                actor=self.employee, bed_id=self.denied_bed.pk, status="BLOCKED", reason="x"
            )

    def test_http_status_change(self):
        self._grant("manage_bed_status")
        self.client.force_login(self.employee)
        url = reverse("adt:bed_status_change", args=[self.destination_bed.pk])

        response = self.client.post(url, {"status": "BLOCKED", "reason": "Isolamento"})

        self.assertRedirects(response, reverse("adt:bed_map"), fetch_redirect_response=False)
        self.destination_bed.refresh_from_db()
        self.assertEqual(self.destination_bed.operational_status, "BLOCKED")
        self.assertEqual(self.client.get(url)["Cache-Control"], "private, no-store, max-age=0")
        denied = reverse("adt:bed_status_change", args=[self.denied_bed.pk])
        self.assertEqual(self.client.get(denied).status_code, 403)
