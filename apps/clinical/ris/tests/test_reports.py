from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.clinical.pep.models import Encounter, PatientAccessGrant
from apps.clinical.pep.tests.test_views import TEST_STORAGES

from ..services import RisConflict, release_report, write_report
from . import test_workflow


@override_settings(STORAGES=TEST_STORAGES, SECURE_SSL_REDIRECT=False)
class ImagingReportTests(TestCase):
    order = test_workflow.RisTests.order

    @classmethod
    def setUpTestData(cls):
        test_workflow.RisTests.setUpTestData.__func__(cls)
        cls.user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="ris", codename__in=["write_report", "release_report"]
            )
        )
        PatientAccessGrant.objects.create(
            patient=cls.patient, user=cls.other, reason="x", granted_by=cls.user
        )

    def write(self, order, **extra):
        data = {"findings": "Sem alterações sintéticas", "impression": "Normal sintético"}
        return write_report(
            user=self.user, order=order, performed_at=timezone.now(), **{**data, **extra}
        )

    def test_release_rectification_and_visibility(self):
        order = self.order()
        first = self.write(order)
        with self.assertRaises(RisConflict):
            self.write(order, reason="x")  # anterior não liberado
        url = reverse("ris:order_detail", args=[order.pk])
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(url), "Normal sintético")

        release_report(user=self.user, report_id=first.pk)
        self.assertContains(self.client.get(url), "Normal sintético")
        with self.assertRaises(RisConflict):
            release_report(user=self.user, report_id=first.pk)
        with self.assertRaises(RisConflict):
            self.write(order)  # retificação sem motivo

        Encounter.objects.filter(pk=self.encounter.pk).update(
            status=Encounter.Status.CLOSED, ended_at=timezone.now()
        )
        fixed = self.write(order, reason="Lateralidade", impression="Corrigido")
        first.refresh_from_db()
        self.assertEqual((fixed.supersedes, first.impression), (first, "Normal sintético"))
