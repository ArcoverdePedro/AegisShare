import base64

import pyotp
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from aegis_share.models import CustomUser
from aegis_share.services.security import (
    authenticate_api_token,
    begin_totp_setup,
    consume_recovery_code,
    create_api_token,
    enable_totp,
    too_many_attempts,
)
from aegis_share.tests.helpers import make_user

TEST_KEY = base64.urlsafe_b64encode(b"s" * 32).decode()

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


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
        token.revoked_at = timezone.now()
        token.save(update_fields=["revoked_at"])
        self.assertIsNone(authenticate_api_token(raw))


@override_settings(FILE_ENCRYPTION_KEY=TEST_KEY, STORAGES=TEST_STORAGES)
class TwoFactorFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        CustomUser.objects.create_superuser("root", "root@example.com", "RootPass123!")
        self.user = make_user("twofa-user")
        secret, _ = begin_totp_setup(self.user)
        enable_totp(self.user, pyotp.TOTP(secret).now())

    def test_attempt_counter_blocks_after_limit(self):
        results = [too_many_attempts("test-key", limit=3) for _ in range(4)]
        self.assertEqual(results, [False, False, False, True])

    def test_restarting_2fa_setup_requires_password(self):
        self.client.force_login(self.user)
        self.client.post(reverse("begin_2fa"), {"password": "wrong"})
        self.user.security_settings.refresh_from_db()
        self.assertTrue(self.user.security_settings.totp_enabled)

        self.client.post(reverse("begin_2fa"), {"password": "StrongTestPass123!"})
        self.user.security_settings.refresh_from_db()
        self.assertFalse(self.user.security_settings.totp_enabled)

    def test_2fa_code_guessing_is_limited(self):
        self.client.post(
            reverse("login"), {"username": "twofa-user", "password": "StrongTestPass123!"}
        )
        for _ in range(8):
            self.client.post(reverse("login_2fa"), {"code": "000000"})
        response = self.client.post(reverse("login_2fa"), {"code": "000000"})
        self.assertContains(response, "Muitas tentativas de 2FA")
