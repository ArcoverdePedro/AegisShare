from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.utils import timezone

from apps.clinical.pep.models import Patient, PatientAccessGrant

from ..permissions import can_admit, can_view_bed_map, can_view_occupant_phi

User = get_user_model()


class AdtPermissionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="adt-admin",
            password="test-password",
            nivel_permissao="ADM",
        )
        self.employee = User.objects.create_user(
            username="adt-employee",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.client_user = User.objects.create_user(
            username="adt-client",
            password="test-password",
            nivel_permissao="CLI",
        )
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="ADT-PATIENT-1",
            full_name="Paciente de Teste",
            birth_date=timezone.localdate() - timedelta(days=365 * 25),
            created_by=self.admin,
        )

    def _grant_permission(self, user, codename):
        permission = Permission.objects.get(
            codename=codename,
            content_type__app_label="adt",
        )
        user.user_permissions.add(permission)
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            if hasattr(user, cache_name):
                delattr(user, cache_name)

    def test_administrator_has_operational_access_without_group_permission(self):
        self.assertTrue(can_view_bed_map(self.admin))
        self.assertTrue(can_admit(self.admin))

    def test_employee_does_not_receive_adt_capability_from_role_alone(self):
        self.assertFalse(can_view_bed_map(self.employee))
        self.assertFalse(can_admit(self.employee))

    def test_employee_can_receive_specific_adt_capability(self):
        self._grant_permission(self.employee, "view_bed_map")
        self.assertTrue(can_view_bed_map(self.employee))
        self.assertFalse(can_admit(self.employee))

    def test_client_remains_denied_even_if_permission_is_misassigned(self):
        self._grant_permission(self.client_user, "view_bed_map")
        self.assertFalse(can_view_bed_map(self.client_user))

    def test_operational_bed_map_permission_does_not_grant_patient_phi(self):
        self._grant_permission(self.employee, "view_bed_map")
        self.assertTrue(can_view_bed_map(self.employee))
        self.assertFalse(can_view_occupant_phi(self.employee, self.patient))

        PatientAccessGrant.objects.create(
            patient=self.patient,
            user=self.employee,
            granted_by=self.admin,
            reason="Cobertura assistencial",
        )
        self.assertTrue(can_view_occupant_phi(self.employee, self.patient))
