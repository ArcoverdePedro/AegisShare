from datetime import date
from queue import Queue
from threading import Barrier, Thread

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.db import close_old_connections, connections
from django.test import RequestFactory, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse

from apps.clinical.pep.models import Patient
from apps.clinical.pep.tests.test_views import TEST_STORAGES

from ..models import DataSubjectRequest, DataSubjectRequestEvent
from ..views import request_transition


@skipUnlessDBFeature("has_select_for_update")
@override_settings(STORAGES=TEST_STORAGES)
class RequestConcurrencyTests(TransactionTestCase):
    def test_two_operators_produce_one_transition_and_one_conflict(self):
        actor = get_user_model().objects.create(
            username="lgp-concurrency",
            nivel_permissao="ADM",
            is_superuser=True,
        )
        patient = Patient.objects.create(
            identifier_type="OTHER",
            identifier="LGP-CONC",
            full_name="Pessoa Sintética",
            birth_date=date(1990, 1, 15),
            created_by=actor,
        )
        item = DataSubjectRequest.objects.create(
            patient=patient,
            created_by=actor,
            category="ACCESS",
            summary="Pedido sintético",
        )
        DataSubjectRequestEvent.objects.create(request=item, to_status="RECEIVED", actor=actor)
        barrier = Barrier(2)
        results = Queue()

        def worker(note):
            close_old_connections()
            try:
                request = RequestFactory().post(
                    reverse("compliance:request_transition", args=[item.pk]),
                    {
                        "expected_status": "RECEIVED",
                        "target_status": "IN_REVIEW",
                        "note": note,
                    },
                )
                request.user = get_user_model().objects.get(pk=actor.pk)
                request.session = {}
                request._messages = FallbackStorage(request)
                barrier.wait(timeout=10)
                response = request_transition(request, pk=item.pk)
                results.put(response.status_code)
            except Exception as error:
                results.put(repr(error))
            finally:
                connections.close_all()

        threads = [
            Thread(target=worker, args=(note,))
            for note in ("Primeiro operador", "Segundo operador")
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        outcomes = [results.get(timeout=2) for _ in threads]
        self.assertCountEqual(outcomes, [302, 409])
        item.refresh_from_db()
        self.assertEqual(item.status, "IN_REVIEW")
        self.assertEqual(item.events.count(), 2)
        self.assertIn(
            item.events.get(to_status="IN_REVIEW").note, ["Primeiro operador", "Segundo operador"]
        )
