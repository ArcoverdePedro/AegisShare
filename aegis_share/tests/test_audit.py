from auditlog.models import LogEntry
from auditlog.signals import accessed
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from aegis_share.models import IPFSFile

from .helpers import make_file, make_user


class AuditLogTests(TestCase):
    def test_file_create_and_access_are_audited(self):
        owner = make_user("audit-owner")
        file = make_file(owner, cid="bafy-audit")
        content_type = ContentType.objects.get_for_model(IPFSFile)

        self.assertTrue(
            LogEntry.objects.filter(
                content_type=content_type,
                object_pk=str(file.pk),
                action=LogEntry.Action.CREATE,
            ).exists()
        )

        accessed.send(IPFSFile, instance=file)
        self.assertTrue(
            LogEntry.objects.filter(
                content_type=content_type,
                object_pk=str(file.pk),
                action=LogEntry.Action.ACCESS,
            ).exists()
        )
