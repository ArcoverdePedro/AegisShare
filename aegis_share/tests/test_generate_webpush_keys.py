import stat
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from scripts import generate_webpush_keys


class WebPushKeyGeneratorTests(SimpleTestCase):
    GENERATED_PAIR = ("BTEST-PUBLIC-KEY", "TEST-PRIVATE-KEY")

    def test_install_sets_pair_subject_and_private_file_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            env_path = Path(temporary) / ".env"
            env_path.write_text(
                "WEBPUSH_VAPID_PUBLIC_KEY=\n"
                "WEBPUSH_VAPID_PRIVATE_KEY=\n"
                "WEBPUSH_VAPID_SUBJECT=\n",
                encoding="utf-8",
            )
            env_path.chmod(0o644)

            with patch.object(
                generate_webpush_keys,
                "_generate_key_pair",
                return_value=self.GENERATED_PAIR,
            ):
                changed = generate_webpush_keys.install(
                    env_path,
                    subject="mailto:security@example.invalid",
                    rotate=False,
                )

            content = env_path.read_text(encoding="utf-8")
            self.assertEqual(
                changed,
                [
                    "WEBPUSH_VAPID_PUBLIC_KEY",
                    "WEBPUSH_VAPID_PRIVATE_KEY",
                    "WEBPUSH_VAPID_SUBJECT",
                ],
            )
            self.assertIn("WEBPUSH_VAPID_PUBLIC_KEY=BTEST-PUBLIC-KEY", content)
            self.assertIn("WEBPUSH_VAPID_PRIVATE_KEY=TEST-PRIVATE-KEY", content)
            self.assertIn(
                "WEBPUSH_VAPID_SUBJECT=mailto:security@example.invalid",
                content,
            )
            self.assertEqual(stat.S_IMODE(env_path.stat().st_mode), 0o600)

    def test_install_preserves_existing_pair_without_rotation(self):
        with tempfile.TemporaryDirectory() as temporary:
            env_path = Path(temporary) / ".env"
            env_path.write_text(
                "WEBPUSH_VAPID_PUBLIC_KEY=existing-public\n"
                "WEBPUSH_VAPID_PRIVATE_KEY=existing-private\n"
                "WEBPUSH_VAPID_SUBJECT=mailto:existing@example.invalid\n",
                encoding="utf-8",
            )

            with patch.object(generate_webpush_keys, "_generate_key_pair") as generator:
                changed = generate_webpush_keys.install(
                    env_path,
                    subject=None,
                    rotate=False,
                )

            self.assertEqual(changed, [])
            generator.assert_not_called()
            content = env_path.read_text(encoding="utf-8")
            self.assertIn("WEBPUSH_VAPID_PUBLIC_KEY=existing-public", content)
            self.assertIn("WEBPUSH_VAPID_PRIVATE_KEY=existing-private", content)

    def test_install_refuses_partial_pair_without_explicit_rotation(self):
        with tempfile.TemporaryDirectory() as temporary:
            env_path = Path(temporary) / ".env"
            original = (
                "WEBPUSH_VAPID_PUBLIC_KEY=existing-public\n"
                "WEBPUSH_VAPID_PRIVATE_KEY=\n"
                "WEBPUSH_VAPID_SUBJECT=mailto:existing@example.invalid\n"
            )
            env_path.write_text(original, encoding="utf-8")

            with self.assertRaises(SystemExit):
                generate_webpush_keys.install(
                    env_path,
                    subject=None,
                    rotate=False,
                )

            self.assertEqual(env_path.read_text(encoding="utf-8"), original)

    def test_rotate_replaces_pair_but_preserves_existing_subject(self):
        with tempfile.TemporaryDirectory() as temporary:
            env_path = Path(temporary) / ".env"
            env_path.write_text(
                "WEBPUSH_VAPID_PUBLIC_KEY=old-public\n"
                "WEBPUSH_VAPID_PRIVATE_KEY=old-private\n"
                "WEBPUSH_VAPID_SUBJECT=https://example.invalid/security\n",
                encoding="utf-8",
            )

            with patch.object(
                generate_webpush_keys,
                "_generate_key_pair",
                return_value=self.GENERATED_PAIR,
            ):
                changed = generate_webpush_keys.install(
                    env_path,
                    subject=None,
                    rotate=True,
                )

            self.assertEqual(
                changed,
                ["WEBPUSH_VAPID_PUBLIC_KEY", "WEBPUSH_VAPID_PRIVATE_KEY"],
            )
            content = env_path.read_text(encoding="utf-8")
            self.assertIn("WEBPUSH_VAPID_PUBLIC_KEY=BTEST-PUBLIC-KEY", content)
            self.assertIn("WEBPUSH_VAPID_PRIVATE_KEY=TEST-PRIVATE-KEY", content)
            self.assertIn(
                "WEBPUSH_VAPID_SUBJECT=https://example.invalid/security",
                content,
            )
