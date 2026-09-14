from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.clinical.pep.models import Encounter, Patient

from ..models import Admission, Bed, BedOccupancy, Location

User = get_user_model()


class AdtModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="adt-user",
            password="test-password",
            nivel_permissao="FUNC",
        )
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.CPF,
            identifier="529.982.247-25",
            full_name="Paciente ADT",
            birth_date=timezone.localdate() - timedelta(days=365 * 30),
            created_by=self.user,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.INPATIENT,
            status=Encounter.Status.OPEN,
            started_at=timezone.now() - timedelta(hours=1),
            responsible_professional=self.user,
            created_by=self.user,
        )
        self.location = Location.objects.create(
            code=" uti-a ",
            name="  Unidade   Intensiva A ",
            kind=Location.Kind.UNIT,
        )
        self.bed = Bed.objects.create(
            location=self.location,
            code=" 01 ",
            label=" Leito 01 ",
        )
        self.admission = Admission.objects.create(
            encounter=self.encounter,
            admitted_at=timezone.now(),
            admitted_by=self.user,
        )

    def test_location_and_bed_identifiers_are_normalized(self):
        self.assertEqual(self.location.code, "UTI-A")
        self.assertEqual(self.location.name, "Unidade Intensiva A")
        self.assertEqual(self.bed.code, "01")
        self.assertEqual(self.bed.label, "Leito 01")

    def test_admission_requires_open_inpatient_encounter(self):
        consultation = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            responsible_professional=self.user,
            created_by=self.user,
        )
        with self.assertRaises(ValidationError):
            Admission.objects.create(
                encounter=consultation,
                admitted_at=timezone.now(),
                admitted_by=self.user,
            )

    def test_active_occupancy_makes_bed_occupied(self):
        BedOccupancy.objects.create(
            admission=self.admission,
            bed=self.bed,
            started_at=self.admission.admitted_at,
            started_by=self.user,
        )
        self.assertEqual(self.bed.current_status, "OCCUPIED")

    def test_database_rejects_two_active_occupancies_for_same_bed(self):
        BedOccupancy.objects.create(
            admission=self.admission,
            bed=self.bed,
            started_at=self.admission.admitted_at,
            started_by=self.user,
        )
        second_encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.INPATIENT,
            status=Encounter.Status.OPEN,
            started_at=timezone.now(),
            responsible_professional=self.user,
            created_by=self.user,
        )
        second_admission = Admission.objects.create(
            encounter=second_encounter,
            admitted_at=timezone.now(),
            admitted_by=self.user,
        )
        conflicting = BedOccupancy(
            admission=second_admission,
            bed=self.bed,
            started_at=timezone.now(),
            started_by=self.user,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            BedOccupancy.objects.bulk_create([conflicting])

    def test_database_rejects_two_active_beds_for_same_admission(self):
        BedOccupancy.objects.create(
            admission=self.admission,
            bed=self.bed,
            started_at=self.admission.admitted_at,
            started_by=self.user,
        )
        second_bed = Bed.objects.create(
            location=self.location,
            code="02",
            label="Leito 02",
        )
        conflicting = BedOccupancy(
            admission=self.admission,
            bed=second_bed,
            started_at=timezone.now(),
            started_by=self.user,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            BedOccupancy.objects.bulk_create([conflicting])

    def test_closed_occupancy_allows_bed_reuse(self):
        occupancy = BedOccupancy.objects.create(
            admission=self.admission,
            bed=self.bed,
            started_at=self.admission.admitted_at,
            started_by=self.user,
        )
        occupancy.ended_at = timezone.now()
        occupancy.ended_by = self.user
        occupancy.end_reason = BedOccupancy.EndReason.TRANSFER
        occupancy.save()

        second_encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.INPATIENT,
            status=Encounter.Status.OPEN,
            started_at=timezone.now(),
            responsible_professional=self.user,
            created_by=self.user,
        )
        second_admission = Admission.objects.create(
            encounter=second_encounter,
            admitted_at=timezone.now(),
            admitted_by=self.user,
        )
        second = BedOccupancy.objects.create(
            admission=second_admission,
            bed=self.bed,
            started_at=timezone.now(),
            started_by=self.user,
        )
        self.assertIsNone(second.ended_at)
