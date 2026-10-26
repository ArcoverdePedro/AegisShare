import uuid

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.clinical.pep.tests.test_views import TEST_STORAGES

from ..models import SpecimenEvent
from ..services import (
    LisConflict,
    cancel_order,
    collect_specimen,
    receive_specimen,
    reject_specimen,
)
from . import test_workflow


@override_settings(STORAGES=TEST_STORAGES, SECURE_SSL_REDIRECT=False)
class SpecimenLifecycleTests(TestCase):
    setUpTestData = classmethod(test_workflow.LisTests.setUpTestData.__func__)
    setUp = test_workflow.LisTests.setUp
    order = test_workflow.LisTests.order

    def collect(self, order, code):
        return collect_specimen(
            user=self.user,
            order=order,
            accession_code=code,
            collected_at=timezone.now(),
            operation_key=uuid.uuid4(),
            confirmed=True,
        )

    def receive(self, code, key=None):
        return receive_specimen(
            user=self.user, accession_code=code, operation_key=key or uuid.uuid4()
        )

    def test_rejected_specimen_requires_recollection_with_link(self):
        order = self.order()
        first = self.collect(order, "AC-1")
        with self.assertRaises(LisConflict):
            self.collect(order, "AC-2")
        key = uuid.uuid4()
        received = self.receive("AC-1", key)
        self.assertEqual(self.receive("AC-1", key), received)
        with self.assertRaises(LisConflict):
            self.receive("AC-1")

        reject_specimen(
            user=self.user, specimen_id=first.pk, reason="Hemólise", operation_key=uuid.uuid4()
        )
        with self.assertRaises(LisConflict):
            self.receive("AC-1")
        with self.assertRaises(LisConflict):
            self.collect(order, "AC-1")  # código não é reaproveitado
        second = self.collect(order, "AC-2")

        self.assertEqual(second.replaces, first)
        order.refresh_from_db()
        self.assertEqual(order.specimen, second)
        self.assertEqual(first.events.get(kind=SpecimenEvent.Kind.REJECTED).reason, "Hemólise")

    def test_cancellation_blocks_flow_and_requires_rejecting_received_specimen(self):
        order = self.order()
        self.collect(order, "AC-9")
        self.receive("AC-9")
        with self.assertRaises(LisConflict):
            cancel_order(user=self.user, order_id=order.pk, reason="Pedido duplicado")
        reject_specimen(
            user=self.user,
            specimen_id=order.specimens.get().pk,
            reason="Pedido duplicado",
            operation_key=uuid.uuid4(),
        )
        cancel_order(user=self.user, order_id=order.pk, reason="Pedido duplicado")
        with self.assertRaises(LisConflict):
            self.collect(order, "AC-10")
        with self.assertRaises(LisConflict):
            cancel_order(user=self.user, order_id=order.pk, reason="de novo")

    def test_http_receive_and_scope(self):
        order = self.order()
        self.collect(order, "AC-HTTP")
        url = reverse("lis:specimen_receive")

        response = self.client.post(
            url, {"accession_code": " AC-HTTP ", "operation_key": uuid.uuid4()}
        )
        self.assertRedirects(response, url)
        self.assertEqual(
            self.client.post(
                url, {"accession_code": "AC-HTTP", "operation_key": uuid.uuid4()}
            ).status_code,
            409,
        )
        detail = self.client.get(reverse("lis:order_detail", args=[order.pk]))
        self.assertContains(detail, "recebida no laboratório")
        self.assertEqual(
            self.client.get(reverse("lis:specimen_label", args=[order.pk])).status_code, 200
        )

        self.client.force_login(self.other)
        self.assertEqual(
            self.client.post(
                url, {"accession_code": "AC-HTTP", "operation_key": uuid.uuid4()}
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("lis:specimen_label", args=[order.pk])).status_code, 404
        )
