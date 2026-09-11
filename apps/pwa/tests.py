from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from PIL import Image


class PwaSurfaceTests(TestCase):
    def test_manifest_matches_install_contract(self):
        response = self.client.get(reverse("pwa:manifest"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/manifest+json")
        manifest = response.json()
        self.assertEqual(manifest["name"], "AegisShare HIS")
        self.assertEqual(manifest["short_name"], "AegisShare")
        self.assertEqual(manifest["description"], "Sistema Hospitalar Interno")
        self.assertEqual(manifest["start_url"], "/")
        self.assertEqual(manifest["scope"], "/")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["orientation"], "portrait")
        self.assertEqual(
            [(icon["sizes"], icon["type"]) for icon in manifest["icons"]],
            [("192x192", "image/png"), ("512x512", "image/png")],
        )
        self.assertNotIn("user", response.content.decode().lower())

    def test_manifest_icons_are_real_pngs_with_declared_sizes(self):
        for size in (192, 512):
            with self.subTest(size=size):
                response = self.client.get(reverse("pwa:icon", kwargs={"size": size}))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "image/png")
                with Image.open(BytesIO(response.content)) as image:
                    self.assertEqual(image.format, "PNG")
                    self.assertEqual(image.size, (size, size))

    def test_invalid_icon_size_is_not_exposed(self):
        response = self.client.get(reverse("pwa:icon", kwargs={"size": 256}))
        self.assertEqual(response.status_code, 404)

    def test_service_worker_is_deny_by_default_for_application_pages(self):
        response = self.client.get(reverse("pwa:service_worker"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        body = response.content.decode()
        self.assertIn("request.mode === 'navigate'", body)
        self.assertIn("fetch(request, { cache: 'no-store' })", body)
        self.assertIn("url.pathname.startsWith('/static/')", body)
        self.assertIn("CLEAR_LOCAL_DATA", body)
        self.assertIn("indexedDB.deleteDatabase", body)
        self.assertNotIn("/pacientes/", body)
        self.assertNotIn("/arquivos/", body)

    def test_offline_fallback_contains_no_patient_context(self):
        response = self.client.get(reverse("pwa:offline"))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("Você está sem conexão", body)
        self.assertIn("Nenhum dado clínico identificável", body)
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_pwa_shell_is_available_before_initial_admin_setup(self):
        self.assertFalse(get_user_model().objects.filter(is_superuser=True).exists())

        for route in (
            reverse("pwa:manifest"),
            reverse("pwa:service_worker"),
            reverse("pwa:offline"),
            reverse("pwa:icon", kwargs={"size": 192}),
        ):
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)


class PwaLogoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="pwa-admin",
            email="pwa-admin@example.invalid",
            password="StrongPass!2026",
        )
        self.client.force_login(self.user)

    def test_logout_requests_browser_storage_cleanup(self):
        response = self.client.post(reverse("logout"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Clear-Site-Data"], '"cache", "storage"')
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertNotIn("_auth_user_id", self.client.session)
