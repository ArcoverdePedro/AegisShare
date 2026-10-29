import uuid

from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.models import PatientAccessGrant
from apps.clinical.pep.tests.test_views import TEST_STORAGES

from ..models import LabResult
from ..services import LisConflict, advance_result, enter_result, reject_specimen
from . import test_specimen_lifecycle, test_workflow


@override_settings(STORAGES=TEST_STORAGES, SECURE_SSL_REDIRECT=False)
class LabResultTests(TestCase):
    setUpTestData = classmethod(test_workflow.LisTests.setUpTestData.__func__)
    setUp = test_workflow.LisTests.setUp
    order = test_workflow.LisTests.order
    collect = test_specimen_lifecycle.SpecimenLifecycleTests.collect
    receive = test_specimen_lifecycle.SpecimenLifecycleTests.receive

    def result(self, specimen, key=None, **extra):
        data = {"analyte": "Glicose", "value": "92", "unit": "mg/dL", "reference_range": "70-99"}
        return enter_result(
            user=self.user,
            specimen_id=specimen.pk,
            operation_key=key or uuid.uuid4(),
            **{**data, **extra},
        )

    def test_flow_retry_and_rectification_preserve_original(self):
        specimen = self.collect(self.order(), "RES-1")
        with self.assertRaises(LisConflict):
            self.result(specimen)  # não recebida
        self.receive("RES-1")
        key = uuid.uuid4()
        first = self.result(specimen, key)
        self.assertEqual(self.result(specimen, key), first)
        with self.assertRaises(LisConflict):
            self.result(specimen, supersedes=first, reason="erro")  # ainda não liberado
        advance_result(user=self.user, result_id=first.pk)
        released = advance_result(user=self.user, result_id=first.pk)
        self.assertEqual(released.status, "RELEASED")
        with self.assertRaises(LisConflict):
            advance_result(user=self.user, result_id=first.pk)

        fixed = self.result(specimen, value="29", supersedes=first, reason="Digitação")
        first.refresh_from_db()
        self.assertEqual((first.value, first.status, fixed.supersedes), ("92", "RELEASED", first))
        with self.assertRaises(LisConflict):
            self.result(specimen, supersedes=first, reason="de novo")

    def test_rejected_specimen_and_unreleased_visibility(self):
        order = self.order()
        specimen = self.collect(order, "RES-2")
        self.receive("RES-2")
        self.result(specimen)
        clinician = make_user("lis-clinician", role="FUNC")
        clinician.user_permissions.add(
            Permission.objects.get(codename="view_orders", content_type__app_label="lis")
        )
        PatientAccessGrant.objects.create(
            patient=self.patient, user=clinician, reason="x", granted_by=self.user
        )
        self.client.force_login(clinician)
        url = reverse("lis:order_detail", args=[order.pk])
        self.assertNotContains(self.client.get(url), "Glicose")
        self.client.force_login(self.user)
        self.assertContains(self.client.get(url), "Glicose")

        reject_specimen(
            user=self.user, specimen_id=specimen.pk, reason="Hemólise", operation_key=uuid.uuid4()
        )
        with self.assertRaises(LisConflict):
            self.result(specimen)
        self.assertEqual(LabResult.objects.count(), 1)
