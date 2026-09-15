from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.utils import timezone

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.models import Encounter, Patient, PatientAccessGrant
from apps.clinical.prescription.models import DoseRule, Drug, MedicationSafetyReview
from apps.clinical.prescription.safety import evaluate_medication_safety
from apps.clinical.prescription.services import (
    add_medication_request_item,
    create_medication_request,
    submit_medication_request,
)

from ..models import VitalSignsRecord
from ..selectors import latest_weight_fact


class WeightRxGovernanceGateTests(TestCase):
    def setUp(self):
        self.admin = make_user("nursing-weight-rx-admin", role="ADM")
        self.prescriber = make_user("nursing-weight-rx-prescriber", role="FUNC")
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="NUR-WEIGHT-RX",
            full_name="Paciente Peso Gate RX",
            birth_date=timezone.localdate() - timedelta(days=365 * 30),
            created_by=self.admin,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            responsible_professional=self.prescriber,
            created_by=self.admin,
        )
        PatientAccessGrant.objects.create(
            patient=self.patient,
            user=self.prescriber,
            granted_by=self.admin,
            reason="Cobertura sintética do gate de peso",
        )
        permission = Permission.objects.get(
            codename="prescribe_medication",
            content_type__app_label="prescription",
        )
        self.prescriber.user_permissions.add(permission)
        self.drug = Drug.objects.create(
            code="NUR-WEIGHT-RX-DRUG",
            name="Medicamento Sintético Gate Peso",
            presentation="Comprimido teste",
            dispense_unit="unidade",
        )

    def test_available_nursing_weight_does_not_activate_rx_without_governance_policy(self):
        request = create_medication_request(
            encounter_id=self.encounter.pk,
            actor=self.prescriber,
        )
        add_medication_request_item(
            request_id=request.pk,
            actor=self.prescriber,
            drug_id=self.drug.pk,
            dose=Decimal("10"),
            dose_unit="mg",
            route="oral",
            frequency="1x ao dia",
            sequence=1,
        )
        request = submit_medication_request(request_id=request.pk, actor=self.prescriber)
        DoseRule.objects.create(
            drug=self.drug,
            rule_code="NUR-WEIGHT-GATE",
            basis=DoseRule.Basis.WEIGHT,
            min_weight_kg=Decimal("1"),
            max_weight_kg=Decimal("200"),
            min_dose=Decimal("1"),
            max_dose=Decimal("20"),
            dose_unit="mg",
            reference_source="fixture-sintetica",
            reference_version="test-v1",
            approved_by=self.admin,
            approved_at=timezone.now(),
            active=True,
        )
        VitalSignsRecord.objects.create(
            encounter=self.encounter,
            recorded_by=self.prescriber,
            recorded_at=timezone.now() - timedelta(minutes=10),
            weight_kg=Decimal("74.500"),
        )

        fact = latest_weight_fact(encounter=self.encounter)
        snapshot = evaluate_medication_safety(request)

        self.assertEqual(fact["weight_kg"], Decimal("74.500"))
        self.assertEqual(snapshot["dose_status"], MedicationSafetyReview.DoseStatus.NOT_EVALUABLE)
        self.assertTrue(
            any(
                finding["severity"] == MedicationSafetyReview.DoseStatus.NOT_EVALUABLE
                for finding in snapshot["findings"]
            )
        )
