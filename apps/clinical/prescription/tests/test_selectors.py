from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.utils import timezone

from apps.clinical.pep.models import Encounter, Patient, PatientAccessGrant

from ..models import MedicationRequest
from ..selectors import visible_medication_requests

User = get_user_model()


class PrescriptionSelectorTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="rx-selector-admin",
            password="test-password",
            nivel_permissao="ADM",
        )
        self.employee = User.objects.create_user(
            username="rx-selector-employee",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="RX-SELECTOR-PATIENT",
            full_name="Paciente Selector",
            birth_date=timezone.localdate() - timedelta(days=365 * 40),
            created_by=self.admin,
        )
        encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            responsible_professional=self.admin,
            created_by=self.admin,
        )
        self.request = MedicationRequest.objects.create(
            encounter=encounter,
            authored_by=self.admin,
        )
        permission = Permission.objects.get(
            codename="view_prescription",
            content_type__app_label="prescription",
        )
        self.employee.user_permissions.add(permission)

    def test_permission_without_patient_scope_returns_empty_queryset(self):
        self.assertFalse(visible_medication_requests(self.employee).exists())

    def test_patient_grant_makes_request_visible(self):
        PatientAccessGrant.objects.create(
            patient=self.patient,
            user=self.employee,
            granted_by=self.admin,
            reason="Cobertura assistencial sintética",
        )
        self.assertQuerySetEqual(
            visible_medication_requests(self.employee),
            [self.request],
        )
