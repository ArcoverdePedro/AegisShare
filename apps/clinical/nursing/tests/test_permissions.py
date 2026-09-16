from datetime import date, timedelta
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.utils import timezone

from apps.clinical.pep.models import Encounter, Patient
from apps.clinical.prescription.models import MedicationRequest

from ..permissions import (
    can_administer_dispense_item,
    can_record_vitals,
    can_view_nursing,
)


class NursingPermissionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.nurse = user_model.objects.create_user(
            username="nurse-permissions",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.other_employee = user_model.objects.create_user(
            username="other-employee",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.client = user_model.objects.create_user(
            username="client-with-wrong-perm",
            password="test-password",
            nivel_permissao="CLI",
        )
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="NUR-PERM-1",
            full_name="Paciente Permissão",
            birth_date=date(1985, 5, 10),
            created_by=self.nurse,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            responsible_professional=self.nurse,
            created_by=self.nurse,
        )

        self.view_permission = Permission.objects.get(
            content_type__app_label="nursing",
            codename="view_nursing",
        )
        self.record_permission = Permission.objects.get(
            content_type__app_label="nursing",
            codename="record_vitals",
        )
        self.administer_permission = Permission.objects.get(
            content_type__app_label="nursing",
            codename="administer_medication",
        )

    def test_view_requires_capability_and_pep_scope(self):
        self.nurse.user_permissions.add(self.view_permission)
        self.other_employee.user_permissions.add(self.view_permission)

        self.assertTrue(can_view_nursing(self.nurse, self.encounter))
        self.assertFalse(can_view_nursing(self.other_employee, self.encounter))

    def test_record_requires_open_encounter(self):
        self.nurse.user_permissions.add(self.record_permission)
        self.assertTrue(can_record_vitals(self.nurse, self.encounter))

        ended_at = timezone.now()
        closed_encounter = Encounter.objects.create(
            patient=self.patient,
            status=Encounter.Status.CLOSED,
            started_at=ended_at - timedelta(minutes=1),
            ended_at=ended_at,
            responsible_professional=self.nurse,
            created_by=self.nurse,
        )
        self.assertFalse(can_record_vitals(self.nurse, closed_encounter))

    def test_client_remains_denied_even_with_nursing_permission(self):
        self.client.user_permissions.add(
            self.view_permission,
            self.record_permission,
            self.administer_permission,
        )

        self.assertFalse(can_view_nursing(self.client, self.encounter))
        self.assertFalse(can_record_vitals(self.client, self.encounter))

    def test_administer_uses_dispense_item_encounter_scope_and_validated_request(self):
        self.nurse.user_permissions.add(self.administer_permission)
        self.other_employee.user_permissions.add(self.administer_permission)
        medication_request = SimpleNamespace(
            encounter=self.encounter,
            status=MedicationRequest.Status.VALIDATED,
        )
        dispense_item = SimpleNamespace(
            dispense=SimpleNamespace(medication_request=medication_request)
        )

        self.assertTrue(can_administer_dispense_item(self.nurse, dispense_item))
        self.assertFalse(can_administer_dispense_item(self.other_employee, dispense_item))

        medication_request.status = MedicationRequest.Status.CANCELLED
        self.assertFalse(can_administer_dispense_item(self.nurse, dispense_item))
