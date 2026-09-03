import base64
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from aegis_share.file_policy import FilePolicyError
from aegis_share.models import FileAccess, FileVersion
from aegis_share.services.files import create_file_from_upload, create_new_version
from aegis_share.tests.helpers import make_user

TEST_KEY = base64.urlsafe_b64encode(b"f" * 32).decode()


@override_settings(FILE_ENCRYPTION_KEY=TEST_KEY, CLAMAV_ENABLED=False)
class FileServiceTests(TestCase):
    def setUp(self):
        self.owner = make_user("client")
        self.employee = make_user("employee", role="FUNC")

    @patch("aegis_share.services.files.PinataClient")
    def test_upload_is_encrypted_before_pinata(self, pinata_cls):
        pinata = pinata_cls.return_value
        pinata.upload_bytes.return_value = {
            "id": "pinata-1",
            "cid": "bafy-encrypted-1",
        }
        plain = b"%PDF-1.7 confidential content"
        uploaded = SimpleUploadedFile(
            "contrato.pdf",
            plain,
            content_type="application/pdf",
        )

        file = create_file_from_upload(
            uploaded_file=uploaded,
            owner=self.owner,
            actor=self.employee,
            description="Contrato",
        )

        encrypted = pinata.upload_bytes.call_args.args[0]
        self.assertNotEqual(encrypted, plain)
        self.assertTrue(encrypted.startswith(b"AEGIS1"))
        self.assertTrue(file.is_encrypted)
        self.assertEqual(file.sha256, file.current_version.sha256)
        self.assertTrue(file.current_version.wrapped_key)
        self.assertEqual(file.current_version.version_number, 1)
        self.assertTrue(
            FileAccess.objects.filter(arquivo=file, user=self.employee).exists()
        )

    @patch("aegis_share.services.files.PinataClient")
    def test_new_version_updates_current_metadata(self, pinata_cls):
        pinata = pinata_cls.return_value
        pinata.upload_bytes.side_effect = [
            {"id": "pinata-1", "cid": "bafy-version-1"},
            {"id": "pinata-2", "cid": "bafy-version-2"},
        ]

        first = SimpleUploadedFile(
            "arquivo.pdf", b"%PDF first", content_type="application/pdf"
        )
        file = create_file_from_upload(
            uploaded_file=first,
            owner=self.owner,
            actor=self.owner,
        )
        second = SimpleUploadedFile(
            "arquivo.pdf", b"%PDF second", content_type="application/pdf"
        )

        version = create_new_version(
            file=file,
            uploaded_file=second,
            actor=self.owner,
        )
        file.refresh_from_db()

        self.assertEqual(version.version_number, 2)
        self.assertEqual(file.cid, "bafy-version-2")
        self.assertEqual(FileVersion.objects.filter(file=file).count(), 2)
        self.assertEqual(file.current_version.id, version.id)

    @patch("aegis_share.services.files.PinataClient")
    def test_invalid_mime_is_rejected_before_external_upload(self, pinata_cls):
        uploaded = SimpleUploadedFile(
            "malware.exe",
            b"MZ executable",
            content_type="application/x-msdownload",
        )

        with self.assertRaises(FilePolicyError):
            create_file_from_upload(
                uploaded_file=uploaded,
                owner=self.owner,
                actor=self.employee,
            )

        pinata_cls.assert_not_called()
