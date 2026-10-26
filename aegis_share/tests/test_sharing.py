from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from aegis_share.models import CustomUser
from aegis_share.services.sharing import (
    SharedLinkError,
    consume_link_access,
    create_shared_link,
    resolve_shared_link,
    revoke_shared_link,
)

from .helpers import make_file, make_user

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES)
class SharedLinkTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner")
        self.other = make_user("other")
        self.file = make_file(self.owner, cid="bafy-sharing")
        # Sem superusuario o middleware de primeiro acesso redireciona tudo para /setup/.
        CustomUser.objects.create_superuser("root", "root@example.com", "RootPass123!")

    def test_token_is_not_stored_in_plain_text(self):
        link, token = create_shared_link(
            file=self.file,
            actor=self.owner,
            expires_in_hours=24,
            password="secret",
            max_downloads=2,
        )

        self.assertNotEqual(link.token_hash, token)
        self.assertFalse(hasattr(link, "token"))
        self.assertEqual(resolve_shared_link(token, password="secret"), link)

    def test_wrong_password_is_rejected(self):
        _, token = create_shared_link(
            file=self.file,
            actor=self.owner,
            password="secret",
        )
        with self.assertRaises(SharedLinkError):
            resolve_shared_link(token, password="wrong")

    def test_download_limit_is_enforced(self):
        link, token = create_shared_link(
            file=self.file,
            actor=self.owner,
            max_downloads=1,
        )
        consume_link_access(token, for_download=True)
        link.refresh_from_db()
        self.assertFalse(link.is_active)
        with self.assertRaises(SharedLinkError):
            consume_link_access(token, for_download=True)

    def test_revoked_link_stops_working(self):
        link, token = create_shared_link(file=self.file, actor=self.owner)
        revoke_shared_link(link, self.owner)
        with self.assertRaises(SharedLinkError):
            resolve_shared_link(token)

    def test_unrelated_user_cannot_create_link(self):
        with self.assertRaises(PermissionError):
            create_shared_link(file=self.file, actor=self.other)

    def test_preview_counts_toward_access_limit(self):
        _, token = create_shared_link(file=self.file, actor=self.owner, max_downloads=1)
        consume_link_access(token, for_download=False)
        with self.assertRaises(SharedLinkError):
            consume_link_access(token, for_download=True)

    def test_download_only_link_opens_its_landing_page(self):
        _, token = create_shared_link(file=self.file, actor=self.owner, allow_preview=False)
        response = self.client.get(reverse("shared_link", args=[token]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Baixar")

    def test_link_password_guessing_is_limited(self):
        _, token = create_shared_link(file=self.file, actor=self.owner, password="secret")
        url = reverse("shared_link", args=[token])
        with patch("aegis_share.services.sharing.check_password", return_value=False):
            statuses = [self.client.post(url, {"password": "x"}).status_code for _ in range(11)]
        self.assertEqual(statuses[:10], [403] * 10)
        self.assertEqual(statuses[10], 429)
