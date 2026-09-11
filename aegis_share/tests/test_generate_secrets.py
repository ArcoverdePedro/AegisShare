import stat
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from scripts import generate_secrets


class SecretGeneratorTests(SimpleTestCase):
    GENERATED = {
        "SECRET_KEY": "generated-secret-key-" + ("x" * 64),
        "FILE_ENCRYPTION_KEY": "A" * 43 + "=",
    }

    def test_install_replaces_only_placeholders_and_sets_private_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            env_path = Path(temporary) / ".env"
            env_path.write_text(
                "DEBUG=false\n"
                "SECRET_KEY=CHANGE_ME_SECRET\n"
                "FILE_ENCRYPTION_KEY=CHANGE_ME_FILE_KEY\n"
                "POSTGRES_PASSWORD=keep-me\n",
                encoding="utf-8",
            )
            env_path.chmod(0o644)

            with patch.object(
                generate_secrets,
                "_generate_secrets",
                return_value=self.GENERATED,
            ):
                changed = generate_secrets._install_into_env(env_path)

            content = env_path.read_text(encoding="utf-8")
            self.assertEqual(changed, ["SECRET_KEY", "FILE_ENCRYPTION_KEY"])
            self.assertIn(f"SECRET_KEY={self.GENERATED['SECRET_KEY']}", content)
            self.assertIn(
                f"FILE_ENCRYPTION_KEY={self.GENERATED['FILE_ENCRYPTION_KEY']}",
                content,
            )
            self.assertIn("POSTGRES_PASSWORD=keep-me", content)
            self.assertEqual(stat.S_IMODE(env_path.stat().st_mode), 0o600)

    def test_install_does_not_rotate_existing_valid_secret(self):
        with tempfile.TemporaryDirectory() as temporary:
            env_path = Path(temporary) / ".env"
            current_secret = "already-valid-secret-" + ("y" * 64)
            env_path.write_text(
                f"SECRET_KEY={current_secret}\n"
                "FILE_ENCRYPTION_KEY=CHANGE_ME_FILE_KEY\n",
                encoding="utf-8",
            )

            with patch.object(
                generate_secrets,
                "_generate_secrets",
                return_value=self.GENERATED,
            ):
                changed = generate_secrets._install_into_env(env_path)

            content = env_path.read_text(encoding="utf-8")
            self.assertEqual(changed, ["FILE_ENCRYPTION_KEY"])
            self.assertIn(f"SECRET_KEY={current_secret}", content)
            self.assertNotIn(f"SECRET_KEY={self.GENERATED['SECRET_KEY']}", content)

    def test_install_refuses_duplicate_secret_keys_without_modifying_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            env_path = Path(temporary) / ".env"
            original = (
                "SECRET_KEY=CHANGE_ME_FIRST\n"
                "SECRET_KEY=CHANGE_ME_SECOND\n"
                "FILE_ENCRYPTION_KEY=CHANGE_ME_FILE_KEY\n"
            )
            env_path.write_text(original, encoding="utf-8")

            with self.assertRaises(SystemExit):
                generate_secrets._install_into_env(env_path)

            self.assertEqual(env_path.read_text(encoding="utf-8"), original)

    def test_install_adds_missing_keys_without_touching_other_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            env_path = Path(temporary) / ".env"
            env_path.write_text("DEBUG=false\nLOG_LEVEL=INFO\n", encoding="utf-8")

            with patch.object(
                generate_secrets,
                "_generate_secrets",
                return_value=self.GENERATED,
            ):
                changed = generate_secrets._install_into_env(env_path)

            content = env_path.read_text(encoding="utf-8")
            self.assertEqual(changed, ["SECRET_KEY", "FILE_ENCRYPTION_KEY"])
            self.assertTrue(content.startswith("DEBUG=false\nLOG_LEVEL=INFO\n"))
            self.assertIn(f"SECRET_KEY={self.GENERATED['SECRET_KEY']}", content)
            self.assertIn(
                f"FILE_ENCRYPTION_KEY={self.GENERATED['FILE_ENCRYPTION_KEY']}",
                content,
            )
