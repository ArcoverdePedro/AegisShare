import uuid
from datetime import date, timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from aegis_share.tests.helpers import make_user
from apps.clinical.adt.models import Bed, Location
from apps.clinical.pep.models import Encounter, Patient
from apps.clinical.pep.tests.test_views import TEST_STORAGES
from apps.clinical.scheduling.models import AgendaSlot, Appointment

from ..views import indicators


@override_settings(STORAGES=TEST_STORAGES, SECURE_SSL_REDIRECT=False)
class IndicatorTests(TestCase):
    def test_values_follow_declared_numerator_and_denominator(self):
        admin = make_user("ind-admin", role="ADM")
        location = Location.objects.create(code="W", name="Ala", kind="WARD")
        Bed.objects.create(location=location, code="1", label="1", operational_status="CLEANING")
        Bed.objects.create(location=location, code="2", label="2")
        Bed.objects.create(
            location=location, code="3", label="3", operational_status="OUT_OF_SERVICE"
        )
        patient = Patient.objects.create(
            identifier_type="OTHER",
            identifier="IND",
            full_name="Paciente Indicador",
            birth_date=date(1990, 1, 1),
            created_by=admin,
        )
        start = timezone.now() - timedelta(days=1)
        slot = AgendaSlot.objects.create(
            professional=admin,
            starts_at=start,
            ends_at=start + timedelta(minutes=20),
            capacity=2,
            location="C1",
            created_by=admin,
        )
        for status in ("NO_SHOW", "CALLED"):
            Appointment.objects.create(
                slot=slot,
                patient=Patient.objects.create(
                    identifier_type="OTHER",
                    identifier=status,
                    full_name=status,
                    birth_date=date(1990, 1, 1),
                    created_by=admin,
                ),
                status=status,
                booked_by=admin,
                operation_key=uuid.uuid4(),
                checked_in_at=start if status == "CALLED" else None,
                called_at=start + timedelta(minutes=12) if status == "CALLED" else None,
            )
        Encounter.objects.create(patient=patient, responsible_professional=admin, created_by=admin)

        values = {i["name"]: i["value"] for i in indicators(days=30)}

        self.assertEqual(values["Ocupação de leitos (agora)"], 0.0)
        self.assertEqual(values["Leitos aguardando higienização (agora)"], 1)
        self.assertEqual(values["Faltas na agenda"], 50.0)
        self.assertEqual(values["Espera chegada → chamada"], 12.0)
        self.assertIsNone(values["Rejeição de amostras"])

    def test_admin_only_and_no_patient_names(self):
        admin = make_user("ind-admin2", role="ADM")
        admin.is_superuser = True
        admin.save(update_fields=["is_superuser"])
        self.client.force_login(make_user("ind-func", role="FUNC"))
        self.assertEqual(self.client.get(reverse("indicators:panel")).status_code, 403)
        self.client.force_login(admin)
        response = self.client.get(reverse("indicators:panel") + "?dias=abc")
        self.assertContains(response, "últimos 30 dias")
        self.assertEqual(response["Cache-Control"], "private, no-store")
