from django.test import TestCase

from aegis_share.services.sharing import (
    SharedLinkError,
    consume_download,
    create_shared_link,
    resolve_shared_link,
    revoke_shared_link,
)

from .helpers import make_file, make_user


class SharedLinkTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner")
        self.other = make_user("other")
        self.file = make_file(self.owner, cid="bafy-sharing")

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
        consume_download(token)
        link.refresh_from_db()
        self.assertFalse(link.is_active)
        with self.assertRaises(SharedLinkError):
            consume_download(token)

    def test_revoked_link_stops_working(self):
        link, token = create_shared_link(file=self.file, actor=self.owner)
        revoke_shared_link(link, self.owner)
        with self.assertRaises(SharedLinkError):
            resolve_shared_link(token)

    def test_unrelated_user_cannot_create_link(self):
        with self.assertRaises(PermissionError):
            create_shared_link(file=self.file, actor=self.other)
