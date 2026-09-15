from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clinical.pep.models import Encounter, Patient

from ..models import VitalSignsRecord


class NursingViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.nurse = user_model.objects.create_user(
            username="nursing-view-user",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.other_employee = user_model.objects.create_user(
            username="nursing-view-other",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.client_user = user_model.objects.create_user(
            username="nursing-view-client",
            password="test-password",
            nivel_permissao="CLI",
        )
        self.started_at = timezone.now() - timedelta(hours=1)
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="NUR-VIEW-1",
            full_name="Paciente Visível",
            birth_date=date(1988, 2, 1),
            created_by=self.nurse,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            started_at=self.started_at,
            responsible_professional=self.nurse,
            created_by=self.nurse,
        )
        self.other_patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="NUR-VIEW-2",
            full_name="Paciente Fora do Escopo",
            birth_date=date(1987, 3, 1),
            created_by=self.other_employee,
        )
        self.other_encounter = Encounter.objects.create(
            patient=self.other_patient,
            started_at=self.started_at,
            responsible_professional=self.other_employee,
            created_by=self.other_employee,
        )
        self.view_permission = Permission.objects.get(
            content_type__app_label="nursing",
            codename="view_nursing",
        )
        self.record_permission = Permission.objects.get(
            content_type__app_label="nursing",
            codename="record_vitals",
        )

    def _recorded_at(self, value):
        return timezone.localtime(value).strftime("%Y-%m-%dT%H:%M:%S")

    def test_worklist_requires_explicit_view_permission(self):
        self.client.force_login(self.nurse)

        response = self.client.get(reverse("nursing:worklist"))

        self.assertEqual(response.status_code, 403)

    def test_worklist_only_lists_pep_scoped_encounters(self):
        self.nurse.user_permissions.add(self.view_permission)
        self.client.force_login(self.nurse)

        response = self.client.get(reverse("nursing:worklist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Paciente Visível")
        self.assertNotContains(response, "Paciente Fora do Escopo")
        self.assertEqual(response["Cache-Control"], "private, no-store, max-age=0")

    def test_encounter_outside_pep_scope_returns_404(self):
        self.nurse.user_permissions.add(self.view_permission)
        self.client.force_login(self.nurse)

        response = self.client.get(
            reverse("nursing:encounter", kwargs={"pk": self.other_encounter.pk})
        )

        self.assertEqual(response.status_code, 404)

    def test_client_role_remains_denied_with_misassigned_permission(self):
        self.client_user.user_permissions.add(self.view_permission)
        self.client.force_login(self.client_user)

        response = self.client.get(reverse("nursing:worklist"))

        self.assertEqual(response.status_code, 403)

    def test_create_vitals_persists_actor_and_canonical_values(self):
        self.nurse.user_permissions.add(self.view_permission, self.record_permission)
        self.client.force_login(self.nurse)
        measured_at = timezone.now() - timedelta(minutes=1)

        response = self.client.post(
            reverse("nursing:vitals_create", kwargs={"encounter_id": self.encounter.pk}),
            data={
                "recorded_at": self._recorded_at(measured_at),
                "temperature_c": "36.50",
                "heart_rate_bpm": "72",
                "weight_kg": "70.125",
            },
        )

        self.assertRedirects(
            response,
            reverse("nursing:encounter", kwargs={"pk": self.encounter.pk}),
        )
        record = VitalSignsRecord.objects.get()
        self.assertEqual(record.encounter, self.encounter)
        self.assertEqual(record.recorded_by, self.nurse)
        self.assertEqual(str(record.temperature_c), "36.50")
        self.assertEqual(str(record.weight_kg), "70.125")

    def test_create_vitals_requires_at_least_one_measure(self):
        self.nurse.user_permissions.add(self.record_permission)
        self.client.force_login(self.nurse)

        response = self.client.post(
            reverse("nursing:vitals_create", kwargs={"encounter_id": self.encounter.pk}),
            data={
                "recorded_at": self._recorded_at(timezone.now() - timedelta(minutes=1)),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Informe ao menos uma medida clínica.")
        self.assertFalse(VitalSignsRecord.objects.exists())

    def test_create_vitals_rejects_closed_encounter(self):
        self.nurse.user_permissions.add(self.record_permission)
        self.client.force_login(self.nurse)
        ended_at = timezone.now() - timedelta(minutes=10)
        closed_encounter = Encounter.objects.create(
            patient=self.patient,
            status=Encounter.Status.CLOSED,
            started_at=ended_at - timedelta(hours=1),
            ended_at=ended_at,
            responsible_professional=self.nurse,
            created_by=self.nurse,
        )

        response = self.client.get(
            reverse("nursing:vitals_create", kwargs={"encounter_id": closed_encounter.pk})
        )

        self.assertEqual(response.status_code, 403)
