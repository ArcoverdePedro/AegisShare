from django.test import TestCase
from django.urls import reverse

from aegis_share.services.security import create_api_token

from .helpers import make_file, make_user


class WebSurfaceTests(TestCase):
    def setUp(self):
        self.admin = make_user("root", role="ADM")
        self.admin.is_superuser = True
        self.admin.is_staff = True
        self.admin.save(update_fields=["is_superuser", "is_staff"])

    def test_health_endpoints_are_available_without_login(self):
        live = self.client.get(reverse("health_live"))
        ready = self.client.get(reverse("health_ready"))

        self.assertEqual(live.status_code, 200)
        self.assertEqual(live.json()["status"], "ok")
        self.assertEqual(ready.status_code, 200)
        self.assertTrue(ready.json()["checks"]["database"])
        self.assertTrue(ready.json()["checks"]["cache"])

    def test_api_requires_bearer_token(self):
        response = self.client.get(reverse("api_files"))
        self.assertEqual(response.status_code, 401)

    def test_api_token_only_lists_accessible_files(self):
        owner = make_user("api-owner")
        other = make_user("api-other")
        visible = make_file(owner, cid="bafy-api-visible", name="visivel.pdf")
        make_file(other, cid="bafy-api-hidden", name="oculto.pdf")
        _, raw = create_api_token(owner, name="Teste")

        response = self.client.get(
            reverse("api_files"),
            HTTP_AUTHORIZATION=f"Bearer {raw}",
        )

        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual([item["id"] for item in results], [visible.id])

    def test_client_cannot_open_another_clients_file(self):
        owner = make_user("owner-web")
        intruder = make_user("intruder-web")
        file = make_file(owner, cid="bafy-private")
        self.client.force_login(intruder)

        response = self.client.get(reverse("file_detail", args=[file.id]))
        self.assertEqual(response.status_code, 404)
