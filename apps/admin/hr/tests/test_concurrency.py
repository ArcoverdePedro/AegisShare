from queue import Queue
from threading import Barrier, Thread

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connections
from django.test import TransactionTestCase, skipUnlessDBFeature

from ..models import Employee


@skipUnlessDBFeature("has_select_for_update")
class EmployeeConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(
            username="hr-concurrent", nivel_permissao="FUNC"
        )

    def test_parallel_creation_keeps_one_profile(self):
        barrier, results = Barrier(2), Queue()

        def worker():
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=self.user.pk)
                barrier.wait(timeout=10)
                results.put(
                    str(
                        Employee.objects.create(
                            user=user, department="Setor", job_title="Função"
                        ).pk
                    )
                )
            except IntegrityError, ValidationError:
                results.put("conflict")
            finally:
                connections.close_all()

        threads = [Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(Employee.objects.count(), 1)
        self.assertCountEqual(
            [results.get(timeout=2) for _ in threads],
            [str(Employee.objects.get().pk), "conflict"],
        )
