from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from aegis_share.models import CustomUser

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES)
class ClinicalNavbarTests(TestCase):
    def setUp(self):
        # FirstAccessRedirectMiddleware só considera a instalação configurada
        # quando existe um superusuário. Este ator é apenas infraestrutura do teste;
        # as permissões exercitadas continuam nos usuários FUNC/CLI abaixo.
        CustomUser.objects.create_superuser(
            username="nav-system-admin",
            password="test-password",
            nivel_permissao="ADM",
        )

    def _make_user(self, username, role):
        return CustomUser.objects.create_user(
            username=username,
            password="test-password",
            nivel_permissao=role,
        )

    def _grant(self, user, app_label, codename):
        permission = Permission.objects.get(
            content_type__app_label=app_label,
            codename=codename,
        )
        user.user_permissions.add(permission)

    def _assert_clinical_link(self, response, url_name, present):
        link = f'href="{reverse(url_name)}"'
        if present:
            self.assertContains(response, link)
        else:
            self.assertNotContains(response, link)

    def test_employee_without_capabilities_hides_specialized_clinical_links(self):
        employee = self._make_user("nav-employee-basic", "FUNC")
        self.client.force_login(employee)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self._assert_clinical_link(response, "pep:patient_list", True)
        self._assert_clinical_link(response, "adt:bed_map", False)
        self._assert_clinical_link(response, "prescription:prescription_list", False)
        self._assert_clinical_link(response, "nursing:worklist", False)

    def test_employee_sees_only_explicitly_granted_clinical_modules(self):
        employee = self._make_user("nav-employee-clinical", "FUNC")
        self._grant(employee, "adt", "view_bed_map")
        self._grant(employee, "prescription", "view_medication_request")
        self._grant(employee, "nursing", "view_nursing")
        self.client.force_login(employee)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self._assert_clinical_link(response, "pep:patient_list", True)
        self._assert_clinical_link(response, "adt:bed_map", True)
        self._assert_clinical_link(response, "prescription:prescription_list", True)
        self._assert_clinical_link(response, "nursing:worklist", True)

    def test_client_with_misassigned_capabilities_gets_no_clinical_navigation(self):
        client_user = self._make_user("nav-client", "CLI")
        self._grant(client_user, "adt", "view_bed_map")
        self._grant(client_user, "prescription", "view_medication_request")
        self._grant(client_user, "nursing", "view_nursing")
        self.client.force_login(client_user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self._assert_clinical_link(response, "pep:patient_list", False)
        self._assert_clinical_link(response, "adt:bed_map", False)
        self._assert_clinical_link(response, "prescription:prescription_list", False)
        self._assert_clinical_link(response, "nursing:worklist", False)
