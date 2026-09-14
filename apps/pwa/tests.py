import json
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from pywebpush import WebPushException

from aegis_share.services.notifications import notify

from .models import PushSubscription
from .push import send_generic_push

WEBPUSH_TEST_SETTINGS = {
    "WEBPUSH_ENABLED": True,
    "WEBPUSH_VAPID_PUBLIC_KEY": "BTEST_PUBLIC_KEY",
    "WEBPUSH_VAPID_PRIVATE_KEY": "TEST_PRIVATE_KEY",
    "WEBPUSH_VAPID_SUBJECT": "mailto:security@example.invalid",
    "WEBPUSH_SEND_TIMEOUT_SECONDS": 3,
}


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

    def test_service_worker_push_content_is_generic_and_local(self):
        response = self.client.get(reverse("pwa:service_worker"))

        body = response.content.decode()
        self.assertIn("self.addEventListener('push'", body)
        self.assertIn("Você tem uma nova notificação.", body)
        self.assertIn("GENERIC_NOTIFICATION_URL", body)
        push_handler = body.split("self.addEventListener(\'push\'", 1)[1].split(
            "self.addEventListener(\'notificationclick\'", 1
        )[0]
        self.assertNotIn("event.data", push_handler)
        self.assertNotIn("patient_name", body)
        self.assertNotIn("diagnosis", body)

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

    def test_logout_revokes_only_push_bound_to_current_session(self):
        current_fingerprint = PushSubscription.hash_session_key(self.client.session.session_key)
        current = PushSubscription.objects.create(
            user=self.user,
            endpoint="https://push.example.invalid/current-session",
            session_fingerprint=current_fingerprint,
            p256dh="current-p256dh",
            auth="current-auth",
        )
        other = PushSubscription.objects.create(
            user=self.user,
            endpoint="https://push.example.invalid/other-session",
            session_fingerprint=PushSubscription.hash_session_key("other-session-key"),
            p256dh="other-p256dh",
            auth="other-auth",
        )

        self.client.post(reverse("logout"))

        current.refresh_from_db()
        other.refresh_from_db()
        self.assertFalse(current.active)
        self.assertIsNotNone(current.disabled_at)
        self.assertTrue(other.active)
        self.assertIsNone(other.disabled_at)


@override_settings(**WEBPUSH_TEST_SETTINGS)
class WebPushSubscriptionViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="push-admin",
            email="push-admin@example.invalid",
            password="StrongPass!2026",
        )
        self.client.force_login(self.user)
        self.subscription = {
            "endpoint": "https://push.example.invalid/subscription/abc123",
            "keys": {
                "p256dh": "p256dh-test-key",
                "auth": "auth-test-key",
            },
        }

    def post_json(self, route, payload):
        return self.client.post(
            reverse(route),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_config_exposes_only_public_vapid_key(self):
        response = self.client.get(reverse("pwa:push_config"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(
            response.json(),
            {"enabled": True, "public_key": "BTEST_PUBLIC_KEY"},
        )
        self.assertNotContains(response, "TEST_PRIVATE_KEY")

    def test_subscribe_persists_authenticated_subscription(self):
        response = self.post_json("pwa:push_subscribe", self.subscription)

        self.assertEqual(response.status_code, 201)
        stored = PushSubscription.objects.get()
        self.assertEqual(stored.user, self.user)
        self.assertEqual(stored.endpoint, self.subscription["endpoint"])
        self.assertEqual(
            stored.endpoint_hash,
            PushSubscription.hash_endpoint(self.subscription["endpoint"]),
        )
        self.assertEqual(
            stored.session_fingerprint,
            PushSubscription.hash_session_key(self.client.session.session_key),
        )
        self.assertNotEqual(stored.session_fingerprint, self.client.session.session_key)
        self.assertTrue(stored.active)

    def test_subscribe_rejects_non_https_endpoint(self):
        payload = {
            **self.subscription,
            "endpoint": "http://push.example.invalid/subscription/abc123",
        }

        response = self.post_json("pwa:push_subscribe", payload)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(PushSubscription.objects.exists())

    def test_unsubscribe_deactivates_only_current_users_endpoint(self):
        stored = PushSubscription.objects.create(
            user=self.user,
            endpoint=self.subscription["endpoint"],
            session_fingerprint=PushSubscription.hash_session_key(
                self.client.session.session_key
            ),
            p256dh=self.subscription["keys"]["p256dh"],
            auth=self.subscription["keys"]["auth"],
        )

        response = self.post_json(
            "pwa:push_unsubscribe",
            {"endpoint": self.subscription["endpoint"]},
        )

        self.assertEqual(response.status_code, 200)
        stored.refresh_from_db()
        self.assertFalse(stored.active)
        self.assertIsNotNone(stored.disabled_at)


@override_settings(**WEBPUSH_TEST_SETTINGS)
class WebPushDeliveryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="push-recipient",
            email="push-recipient@example.invalid",
            password="StrongPass!2026",
        )
        self.subscription = PushSubscription.objects.create(
            user=self.user,
            endpoint="https://push.example.invalid/subscription/recipient",
            session_fingerprint=PushSubscription.hash_session_key("delivery-session"),
            p256dh="p256dh-recipient-key",
            auth="auth-recipient-key",
        )

    @patch("apps.pwa.push.webpush")
    def test_delivery_contains_no_notification_or_clinical_payload(self, webpush_mock):
        result = send_generic_push(self.user.pk)

        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["failed"], 0)
        kwargs = webpush_mock.call_args.kwargs
        self.assertIsNone(kwargs["data"])
        self.assertEqual(
            kwargs["vapid_claims"],
            {"sub": "mailto:security@example.invalid"},
        )
        self.assertNotIn("title", kwargs)
        self.assertNotIn("body", kwargs)

    @patch("apps.pwa.push.webpush")
    def test_gone_subscription_is_disabled(self, webpush_mock):
        error = WebPushException("gone")
        error.response = SimpleNamespace(status_code=410)
        webpush_mock.side_effect = error

        result = send_generic_push(self.user.pk)

        self.assertEqual(result["disabled"], 1)
        self.subscription.refresh_from_db()
        self.assertFalse(self.subscription.active)
        self.assertIsNotNone(self.subscription.disabled_at)

    @patch("aegis_share.services.notifications._send_webpush_after_commit")
    def test_notification_schedules_push_without_forwarding_its_content(self, push_mock):
        with self.captureOnCommitCallbacks(execute=True):
            notification = notify(
                self.user,
                kind="SYSTEM",
                title="Paciente Sintético Confidencial",
                body="Diagnóstico Sintético Confidencial",
                link="/notificacoes/",
            )

        self.assertIsNotNone(notification)
        push_mock.assert_called_once_with(self.user.pk)
