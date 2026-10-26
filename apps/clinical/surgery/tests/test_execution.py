from datetime import timedelta

from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.clinical.pep.tests.test_views import TEST_STORAGES

from ..models import SurgerySchedule
from ..services import SurgeryConflict, cancel_schedule, record_execution
from . import test_schedule


@override_settings(STORAGES=TEST_STORAGES, SECURE_SSL_REDIRECT=False)
class SurgeryExecutionTests(TestCase):
    setUpTestData = classmethod(test_schedule.SurgeryScheduleTests.setUpTestData.__func__)
    order = test_schedule.SurgeryScheduleTests.order
    book = test_schedule.SurgeryScheduleTests.book

    def setUp(self):
        self.user.user_permissions.add(
            Permission.objects.get(content_type__app_label="surgery", codename="record_execution")
        )
        self.schedule = self.book(
            self.order(), test_schedule.tomorrow_at(8), test_schedule.tomorrow_at(9)
        )
        # Simula cirurgia já ocorrida sem burlar a regra de agendamento futuro.
        past = timezone.now() - timedelta(hours=3)
        SurgerySchedule.objects.filter(pk=self.schedule.pk).update(
            starts_at=past, ends_at=past + timedelta(hours=1)
        )

    def execute(self, supersedes=None, **changes):
        now = timezone.now()
        data = {
            "room_in_at": now - timedelta(hours=3),
            "started_at": now - timedelta(hours=2, minutes=50),
            "ended_at": now - timedelta(hours=2),
            "room_out_at": now - timedelta(hours=1, minutes=50),
            "performed_procedure": "Procedimento ampliado",
            "surgeon": self.user,
            "destination": "Recuperação",
            "team": [self.other],
            **changes,
        }
        return record_execution(
            user=self.user, schedule=self.schedule, supersedes=supersedes, **data
        )

    def test_execution_versions_and_blocks_cancel(self):
        with self.assertRaises(SurgeryConflict):
            self.execute(ended_at=timezone.now() - timedelta(hours=4))
        first = self.execute()
        self.assertEqual(list(first.team.all()), [self.other])
        with self.assertRaises(SurgeryConflict):
            self.execute()  # segunda sem correção
        with self.assertRaises(SurgeryConflict):
            self.execute(supersedes=first)  # correção sem motivo
        fixed = self.execute(supersedes=first, reason="Destino errado", destination="UTI")
        self.assertEqual((fixed.supersedes, first.destination), (first, "Recuperação"))
        with self.assertRaises(SurgeryConflict):
            cancel_schedule(user=self.user, schedule=self.schedule, reason="x")

    def test_execution_form_renders_for_scheduled_case(self):
        from django.urls import reverse

        self.client.force_login(self.user)
        url = reverse("surgery:execution_create", args=[self.schedule.case_id, self.schedule.pk])
        self.assertContains(self.client.get(url), "Registrar execução")
