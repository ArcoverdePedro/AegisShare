from queue import Queue
from threading import Barrier, Thread

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connections
from django.test import TransactionTestCase, override_settings, skipUnlessDBFeature

from ..lab_inbox import receive_laboratory_file
from ..models import LaboratoryInboxReceipt, LaboratorySource


@override_settings(FILE_ENCRYPTION_KEY="aWlpaWlpaWlpaWlpaWlpaWlpaWlpaWlpaWlpaWlpaWk=")
@skipUnlessDBFeature("has_select_for_update")
class InboxConcurrencyTests(TransactionTestCase):
    def test_identical_parallel_receipts_share_original_record(self):
        actor = get_user_model().objects.create(
            username="inbox-concurrent", nivel_permissao="ADM", is_superuser=True
        )
        source = LaboratorySource.objects.create(code="CONCURRENT", label="Sintética")
        barrier, results = Barrier(2), Queue()

        def worker():
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=actor.pk)
                barrier.wait(timeout=10)
                receipt = receive_laboratory_file(
                    user=user,
                    source_id=source.pk,
                    uploaded_file=SimpleUploadedFile("ignored", b"synthetic-concurrent"),
                )
                results.put(str(receipt.pk))
            except Exception as exc:
                results.put(repr(exc))
            finally:
                connections.close_all()

        threads = [Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(LaboratoryInboxReceipt.objects.count(), 1)
        self.assertEqual(
            [results.get(timeout=2) for _ in threads],
            [str(LaboratoryInboxReceipt.objects.get().pk)] * 2,
        )
