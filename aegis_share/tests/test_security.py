import base64

import pyotp
from django.test import TestCase, override_settings

from aegis_share.services.security import (
    authenticate_api_token,
    begin_totp_setup,
    consume_recovery_code,
    create_api_token,
    enable_totp,
)

from .helpers import make_user


TEST_KEY = base64.urlsafe_b64encode(b"s" * 32).decode()


@override_settings(FILE_ENCRYPTION_KEY=TEST_KEY)
class SecurityServiceTests(TestCase):
    def setUp(self):
        self.user = make_user("secure-user")

    def test_totp_secret_is_encrypted_and_recovery_codes_are_hashed(self):
        secret, _ = begin_totp_setup(self.user)
        security = self.user.security_settings

        self.assertNotEqual(security.totp_secret_encrypted, secret)

        code = pyotp.TOTP(secret).now()
        recovery_plain = enable_totp(self.user, code)
        security.refresh_from_db()

        self.assertTrue(security.totp_enabled)
        self.assertEqual(len(recovery_plain), 8)
        for raw in recovery_plain:
            self.assertNotIn(raw, security.recovery_codes)

        self.assertTrue(consume_recovery_code(self.user, recovery_plain[0]))
        self.assertFalse(consume_recovery_code(self.user, recovery_plain[0]))

    def test_api_token_is_only_returned_once_and_authenticates(self):
        token, raw = create_api_token(self.user, name="Automacao")

        self.assertNotEqual(token.token_hash, raw)
        self.assertEqual(authenticate_api_token(raw), self.user)

        token.refresh_from_db()
        self.assertIsNotNone(token.last_used_at)

    def test_revoked_api_token_is_rejected(self):
        token, raw = create_api_token(self.user, name="Revogado")
        from django.utils import timezone

        token.revoked_at = timezone.now()
        token.save(update_fields=["revoked_at"])
        self.assertIsNone(authenticate_api_token(raw))
