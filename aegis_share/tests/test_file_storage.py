import base64
import tempfile
import uuid
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from aegis_share.models import FileVersion, IPFSFile
from aegis_share.services.crypto import encrypt_file, sha256_hex
from aegis_share.services.files import (
    FileIntegrityError,
    _version_aad,
    create_file_from_upload,
    get_version_content,
    purge_file,
)
from aegis_share.services.storage import LocalStorageClient, StorageError
from aegis_share.tests.helpers import make_user

TEST_KEY = base64.urlsafe_b64encode(b"f" * 32).decode()
PLAIN = b"%PDF-1.7 laudo confidencial"


class LocalStorageMixin:
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        storage = override_settings(
            FILE_STORAGE_BACKEND="local",
            FILE_STORAGE_ROOT=self.root,
            FILE_ENCRYPTION_KEY=TEST_KEY,
            CLAMAV_ENABLED=False,
            PINATA_JWT_TOKEN="",
        )
        storage.enable()
        self.addCleanup(storage.disable)
        self.owner = make_user("client")
        self.employee = make_user("employee", role="FUNC")

    def _upload(self):
        return create_file_from_upload(
            uploaded_file=SimpleUploadedFile("laudo.pdf", PLAIN, content_type="application/pdf"),
            owner=self.owner,
            actor=self.employee,
        )


class LocalStorageTests(LocalStorageMixin, TestCase):
    def test_upload_without_pinata_stores_only_ciphertext(self):
        file = self._upload()
        version = file.current_version

        self.assertTrue(version.cid.startswith("local:"))
        stored = next(self.root.glob("*/*")).read_bytes()
        self.assertNotIn(PLAIN, stored)
        self.assertEqual(sha256_hex(stored), version.encrypted_sha256)
        self.assertEqual(get_version_content(version), PLAIN)

    def test_tampered_local_file_fails_integrity(self):
        version = self._upload().current_version
        next(self.root.glob("*/*")).write_bytes(b"AEGIS1corrompido")

        with self.assertRaises(FileIntegrityError):
            get_version_content(version)

    def test_reference_cannot_escape_root(self):
        with self.assertRaises(StorageError):
            LocalStorageClient().download_bytes("local:../../etc/passwd")

    def test_purge_removes_local_object(self):
        file = self._upload()

        self.assertEqual(purge_file(file), [])
        self.assertEqual(list(self.root.glob("*/*")), [])

    def test_health_reports_selected_backend(self):
        payload = self.client.get(reverse("health_services")).json()

        self.assertEqual(payload["checks"]["storage_backend"], "local")
        self.assertTrue(payload["checks"]["storage"])


@patch("aegis_share.services.pinata.PinataClient.download_bytes")
class MigrateFileStorageTests(LocalStorageMixin, TestCase):
    def _legacy(self, *, encrypted=True):
        version_id = uuid.uuid4()
        blob, wrapped, plain_hash, enc_hash = encrypt_file(PLAIN, aad=_version_aad(version_id))
        file = IPFSFile.objects.create(
            cid="bafy-legacy",
            pinata_id="pin-legacy",
            nome_arquivo="laudo.pdf",
            tamanho_arquivo=len(PLAIN),
            sha256=plain_hash,
            is_encrypted=encrypted,
            dono_arquivo=self.owner,
        )
        FileVersion.objects.create(
            id=version_id,
            file=file,
            version_number=1,
            cid="bafy-legacy",
            pinata_id="pin-legacy",
            original_size=len(PLAIN),
            sha256=plain_hash,
            encrypted_sha256=enc_hash if encrypted else "",
            is_encrypted=encrypted,
            wrapped_key=wrapped if encrypted else "",
        )
        return file, (blob if encrypted else PLAIN)

    def test_copies_verified_version_and_keeps_origin_reference(self, download):
        file, download.return_value = self._legacy()
        out = StringIO()

        call_command("migrate_file_storage", stdout=out)

        file.refresh_from_db()
        version = file.current_version
        self.assertTrue(file.cid.startswith("local:"))
        self.assertEqual(version.cid, file.cid)
        self.assertEqual(get_version_content(version), PLAIN)
        self.assertIn("origem_cid=bafy-legacy origem_id=pin-legacy", out.getvalue())

    def test_corrupted_origin_is_not_migrated(self, download):
        file, _ = self._legacy()
        download.return_value = b"AEGIS1outro-conteudo"

        with self.assertRaises(CommandError):
            call_command("migrate_file_storage", stdout=StringIO())

        file.refresh_from_db()
        self.assertEqual(file.current_version.cid, "bafy-legacy")
        self.assertEqual(list(self.root.glob("*/*")), [])

    def test_plaintext_legacy_requires_explicit_flag(self, download):
        file, download.return_value = self._legacy(encrypted=False)

        with self.assertRaises(CommandError):
            call_command("migrate_file_storage", stdout=StringIO())
        call_command("migrate_file_storage", "--encrypt-plaintext", stdout=StringIO())

        version = FileVersion.objects.get(file=file)
        self.assertTrue(version.is_encrypted)
        self.assertNotIn(PLAIN, next(self.root.glob("*/*")).read_bytes())
        self.assertEqual(get_version_content(version), PLAIN)
