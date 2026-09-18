import base64
import uuid
from io import BytesIO
from unittest.mock import patch

from auditlog.models import LogEntry
from cryptography.exceptions import InvalidTag
from django.contrib.auth.models import Permission
from django.core.exceptions import RequestDataTooBig, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connection
from django.test import Client, RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from aegis_share.services.crypto import CryptoConfigurationError, decrypt_file
from aegis_share.tests.helpers import make_user
from apps.clinical.pep.tests.test_views import TEST_STORAGES

from ..admin import LaboratorySourceForm
from ..lab_inbox import MAX_BODY_BYTES, MAX_FILE_BYTES, receive_laboratory_file
from ..models import LaboratoryInboxReceipt, LaboratorySource
from ..upload import LaboratoryUploadHandler, LimitedStream

SETTINGS = dict(
    STORAGES=TEST_STORAGES,
    SECURE_SSL_REDIRECT=False,
    FILE_ENCRYPTION_KEY=base64.urlsafe_b64encode(b"i" * 32).decode(),
)
PAYLOAD = b"SYNTHETIC-LAB-SENSITIVE-MARKER\x00\xff\r\n"


@override_settings(**SETTINGS)
class InboxTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user("inbox-admin", role="ADM")
        cls.admin.is_superuser = True
        cls.admin.save(update_fields=["is_superuser"])
        cls.user = make_user("inbox-operator", role="FUNC")
        cls.other = make_user("inbox-other", role="FUNC")
        cls.permissions = Permission.objects.filter(
            content_type__app_label="interoperability",
            codename__in=["view_lab_inbox", "receive_lab_file"],
        )
        for user in (cls.user, cls.other):
            user.user_permissions.add(*cls.permissions)
        cls.source = LaboratorySource.objects.create(code="SYNTH-ORIGIN", label="Technical label")
        cls.source.operators.add(cls.user)
        cls.url = reverse("interoperability:lab_inbox_receive")
        cls.list_url = reverse("interoperability:lab_inbox_list")

    def setUp(self):
        self.client.force_login(self.user)

    def upload(self, content=PAYLOAD, **changes):
        return self.client.post(
            self.url,
            {
                "source": self.source.pk,
                "confirmed": "on",
                "file": SimpleUploadedFile(
                    "NEVER-PERSISTED-PATIENT.hl7", content, "application/unknown"
                ),
                **changes,
            },
        )

    def receive(self, content=PAYLOAD):
        return receive_laboratory_file(
            user=self.user,
            source_id=self.source.pk,
            uploaded_file=SimpleUploadedFile("never.hl7", content),
        )

    def test_encryption_exact_bytes_and_immutable_receipt(self):
        self.assertEqual(self.upload().status_code, 302)
        item = LaboratoryInboxReceipt.objects.get()
        aad = f"aegisshare:lab-inbox:{item.pk}".encode()
        cipher = bytes(item.ciphertext)
        self.assertNotIn(PAYLOAD, cipher)
        self.assertEqual(decrypt_file(cipher, item.wrapped_key, aad=aad), PAYLOAD)
        with self.assertRaises(InvalidTag):
            decrypt_file(cipher, item.wrapped_key, aad=b"wrong")
        with self.assertRaises(InvalidTag):
            decrypt_file(cipher[:-1] + bytes([cipher[-1] ^ 1]), item.wrapped_key, aad=aad)
        for action in (item.save, item.delete):
            with self.assertRaises(ValidationError):
                action()
        self.assertEqual(item.received_by, self.user)
        self.assertEqual(item.size, len(PAYLOAD))

    def test_duplicate_preserves_original_actor_and_other_source_is_distinct(self):
        item = self.receive()
        self.source.operators.add(self.other)
        self.client.force_login(self.other)
        self.assertEqual(self.upload().status_code, 302)
        self.assertEqual(LaboratoryInboxReceipt.objects.count(), 1)
        item.refresh_from_db()
        self.assertEqual(item.received_by, self.user)
        self.assertTrue(
            LogEntry.objects.filter(
                object_pk=str(item.pk), actor=self.other, action=LogEntry.Action.ACCESS
            ).exists()
        )
        source = LaboratorySource.objects.create(code="OTHER", label="Other")
        source.operators.add(self.other)
        self.assertEqual(self.upload(source=source.pk).status_code, 302)
        self.assertEqual(LaboratoryInboxReceipt.objects.count(), 2)

    def test_revoked_source_hides_receipts_and_blocks_upload(self):
        item = self.receive()
        self.source.operators.remove(self.user)
        response = self.upload()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())
        self.assertEqual(
            self.client.get(
                reverse("interoperability:lab_inbox_detail", args=[item.pk])
            ).status_code,
            404,
        )
        self.assertNotContains(self.client.get(self.list_url), self.source.code)
        self.assertEqual(LaboratoryInboxReceipt.objects.count(), 1)

    def test_inactive_source_blocks_retry_but_keeps_history(self):
        item = self.receive()
        self.source.active = False
        self.source.save()
        self.assertEqual(self.upload().status_code, 200)
        self.assertEqual(LaboratoryInboxReceipt.objects.count(), 1)
        self.assertContains(
            self.client.get(reverse("interoperability:lab_inbox_detail", args=[item.pk])),
            self.source.code,
        )

    def test_capabilities_internal_role_and_preparse_auth(self):
        self.user.user_permissions.remove(Permission.objects.get(codename="receive_lab_file"))
        with patch("apps.interoperability.upload.LaboratoryUploadHandler") as handler:
            self.assertEqual(self.upload().status_code, 403)
            handler.assert_not_called()
        self.user.user_permissions.add(*self.permissions)
        self.user.nivel_permissao = "CLI"
        self.user.save(update_fields=["nivel_permissao"])
        self.assertEqual(self.upload().status_code, 403)
        self.client.logout()
        self.assertEqual(self.upload().status_code, 302)

    def test_permission_does_not_grant_origin_access(self):
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(self.url), self.source.code)
        self.assertEqual(self.upload().status_code, 200)
        self.assertFalse(LaboratoryInboxReceipt.objects.exists())

    def test_limits_empty_confirmation_multiple_files_and_no_disk_spill(self):
        self.assertEqual(self.upload(b"").status_code, 200)
        self.assertEqual(self.upload(confirmed="").status_code, 200)
        with patch(
            "django.core.files.uploadedfile.TemporaryUploadedFile.__init__",
            side_effect=AssertionError("disk"),
        ):
            self.assertEqual(self.upload(b"x" * (MAX_FILE_BYTES + 1)).status_code, 413)
            self.assertEqual(
                self.upload(
                    file=[SimpleUploadedFile("a", b"a"), SimpleUploadedFile("b", b"b")]
                ).status_code,
                413,
            )
            self.assertEqual(self.upload(b"x" * MAX_FILE_BYTES).status_code, 302)
        self.assertEqual(LaboratoryInboxReceipt.objects.count(), 1)

    def test_raw_body_and_actual_stream_limits(self):
        self.assertEqual(self.upload(extra="x" * MAX_BODY_BYTES).status_code, 413)
        stream = LimitedStream(BytesIO(b"x" * (MAX_BODY_BYTES + 1)))
        with self.assertRaises(RequestDataTooBig):
            stream.read()
        request = RequestFactory().post(self.url)
        handler = LaboratoryUploadHandler(request)
        handler.new_file("file", "x", "unknown", 1)
        from django.core.files.uploadhandler import StopUpload

        with self.assertRaises(StopUpload):
            handler.receive_data_chunk(b"x" * (MAX_FILE_BYTES + 1), 0)
        self.assertTrue(handler.rejected)
        self.assertTrue(handler.file.closed)

    def test_incomplete_read_is_rejected(self):
        uploaded = SimpleUploadedFile("x", PAYLOAD)
        uploaded.size += 1
        with self.assertRaises(ValidationError):
            receive_laboratory_file(
                user=self.user, source_id=self.source.pk, uploaded_file=uploaded
            )
        self.assertFalse(LaboratoryInboxReceipt.objects.exists())

    def test_crypto_and_audit_failure_prevent_creation(self):
        self.client.get(self.url)
        for target, error in [
            ("apps.interoperability.lab_inbox.encrypt_file", CryptoConfigurationError("secret")),
            ("auditlog.models.LogEntry.objects.log_create", DatabaseError("sensitive")),
        ]:
            with patch(target, side_effect=error):
                response = self.upload()
            self.assertEqual(response.status_code, 503)
            self.assertNotIn(b"secret", response.content)
            self.assertNotIn(b"sensitive", response.content)
            self.assertFalse(LaboratoryInboxReceipt.objects.exists())

    def test_bad_master_key_fails_without_receipt(self):
        with override_settings(FILE_ENCRYPTION_KEY=""):
            self.assertEqual(self.upload().status_code, 503)
        self.assertFalse(LaboratoryInboxReceipt.objects.exists())

    def test_audit_html_and_queries_exclude_payload_and_crypto(self):
        item = self.receive()
        url = reverse("interoperability:lab_inbox_detail", args=[item.pk])
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        body = response.content.decode()
        logs = str(
            list(
                LogEntry.objects.filter(content_type__app_label="interoperability").values(
                    "changes", "object_repr"
                )
            )
        )
        for value in (
            PAYLOAD.decode("latin1"),
            "NEVER-PERSISTED-PATIENT.hl7",
            item.wrapped_key,
            item.plaintext_sha256,
            item.ciphertext_sha256,
            self.source.label,
        ):
            self.assertNotIn(value, body)
            self.assertNotIn(value, logs)
        receipt_queries = [
            q["sql"]
            for q in queries
            if q["sql"].startswith("SELECT")
            and '"interoperability_laboratoryinboxreceipt"' in q["sql"]
        ]
        self.assertEqual(len(receipt_queries), 1)
        for field in ("ciphertext", "wrapped_key", "plaintext_sha256", "ciphertext_sha256"):
            self.assertNotIn(f'"{field}"', receipt_queries[0])

    def test_paginated_reads_and_invalid_filter_do_not_expand_scope(self):
        for i in range(26):
            self.receive(f"synthetic-{i}".encode())
        LogEntry.objects.filter(action=LogEntry.Action.ACCESS).delete()
        response = self.client.get(self.list_url)
        self.assertEqual(len(response.context["page_obj"]), 25)
        self.assertEqual(LogEntry.objects.filter(action=LogEntry.Action.ACCESS).count(), 25)
        self.assertEqual(len(self.client.get(self.list_url, {"page": 2}).context["page_obj"]), 1)
        self.assertEqual(
            len(self.client.get(self.list_url, {"source": uuid.uuid4()}).context["page_obj"]), 0
        )

    def test_private_csrf_denials_and_methods(self):
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        response = csrf.post(
            self.url,
            {"source": self.source.pk, "file": SimpleUploadedFile("x", b"x"), "confirmed": "on"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(LaboratoryInboxReceipt.objects.exists())
        responses = [response, self.upload(b"x" * (MAX_FILE_BYTES + 1)), self.client.put(self.url)]
        self.client.force_login(self.other)
        responses.append(
            self.client.get(reverse("interoperability:lab_inbox_detail", args=[uuid.uuid4()]))
        )
        for response in responses:
            self.assertEqual(response["Cache-Control"], "private, no-store")
            self.assertIn("Cookie", response["Vary"])
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_admin_source_requires_internal_operators_and_text(self):
        client = make_user("inbox-client", role="CLI")
        form = LaboratorySourceForm(
            {"code": "SOURCE", "label": "Label", "active": True, "operators": [client.pk]}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("operators", form.errors)
        with self.assertRaises(ValidationError):
            LaboratorySource.objects.create(code="   ", label="Label")
        self.source.operators.add(self.other)
        self.assertTrue(
            LogEntry.objects.filter(
                object_pk=str(self.source.pk), action=LogEntry.Action.UPDATE
            ).exists()
        )
