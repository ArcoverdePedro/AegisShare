from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.utils import timezone

from apps.clinical.pep.models import Encounter, Patient, PatientAccessGrant

from ..models import MedicationRequest
from ..permissions import (
    can_dispense_prescription,
    can_prescribe_for_encounter,
    can_validate_prescription,
    can_view_prescription,
)

User = get_user_model()


class PrescriptionPermissionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="rx-admin",
            password="test-password",
            nivel_permissao="ADM",
        )
        self.employee = User.objects.create_user(
            username="rx-employee",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.client_user = User.objects.create_user(
            username="rx-client",
            password="test-password",
            nivel_permissao="CLI",
        )
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="RX-PERM-PATIENT",
            full_name="Paciente Permissão",
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
        self.request = MedicationRequest.objects.create(
            encounter=self.encounter,
            authored_by=self.admin,
        )

    def _grant_permission(self, user, codename):
        permission = Permission.objects.get(
            codename=codename,
            content_type__app_label="prescription",
        )
        user.user_permissions.add(permission)
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            if hasattr(user, cache_name):
                delattr(user, cache_name)

    def _grant_patient(self, user):
        PatientAccessGrant.objects.create(
            patient=self.patient,
            user=user,
            granted_by=self.admin,
            reason="Cobertura assistencial sintética",
        )

    def test_admin_role_alone_does_not_grant_clinical_capability(self):
        self.assertFalse(can_prescribe_for_encounter(self.admin, self.encounter))
        self.assertFalse(can_view_prescription(self.admin, self.request))
        self.assertFalse(can_validate_prescription(self.admin, self.request))
        self.assertFalse(can_dispense_prescription(self.admin, self.request))

    def test_admin_with_explicit_capability_keeps_global_pep_scope(self):
        self._grant_permission(self.admin, "view_medication_request")
        self._grant_permission(self.admin, "prescribe_medication")
        self.assertTrue(can_view_prescription(self.admin, self.request))
        self.assertTrue(can_prescribe_for_encounter(self.admin, self.encounter))

    def test_employee_role_alone_does_not_grant_capability(self):
        self._grant_patient(self.employee)
        self.assertFalse(can_prescribe_for_encounter(self.employee, self.encounter))
        self.assertFalse(can_view_prescription(self.employee, self.request))

    def test_permission_without_pep_scope_does_not_expose_prescription(self):
        self._grant_permission(self.employee, "view_medication_request")
        self.assertFalse(can_view_prescription(self.employee, self.request))

    def test_permission_and_pep_scope_are_both_required(self):
        self._grant_permission(self.employee, "view_medication_request")
        self._grant_permission(self.employee, "prescribe_medication")
        self._grant_patient(self.employee)
        self.assertTrue(can_view_prescription(self.employee, self.request))
        self.assertTrue(can_prescribe_for_encounter(self.employee, self.encounter))

    def test_client_remains_denied_even_if_permission_is_misassigned(self):
        self._grant_permission(self.client_user, "view_medication_request")
        self._grant_permission(self.client_user, "prescribe_medication")
        self._grant_patient(self.client_user)
        self.assertFalse(can_view_prescription(self.client_user, self.request))
        self.assertFalse(can_prescribe_for_encounter(self.client_user, self.encounter))
