from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.utils import timezone

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.models import Encounter, Patient

from ..models import Drug, MedicationRequest, MedicationRequestItem


class UsedDrugFixtureMixin:
    def setUp(self):
        super().setUp()
        self.actor = make_user("rx-used-drug-integrity", role="ADM")
        self.patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="RX-USED-DRUG-PATIENT",
            full_name="Paciente Sintético Histórico",
            birth_date=timezone.localdate().replace(year=timezone.localdate().year - 30),
            created_by=self.actor,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            responsible_professional=self.actor,
            created_by=self.actor,
        )
        self.request = MedicationRequest.objects.create(
            encounter=self.encounter,
            authored_by=self.actor,
        )
        self.used_drug = Drug.objects.create(
            code="RX-HISTORY-USED",
            name="Medicamento Sintético Histórico",
            presentation="Apresentação histórica",
            strength_text="10 unidades",
            route_hint="via histórica",
            dispense_unit="unidade",
            active=True,
        )
        self.unused_drug = Drug.objects.create(
            code="RX-HISTORY-UNUSED",
            name="Medicamento Sintético Não Utilizado",
            presentation="Apresentação editável",
            strength_text="20 unidades",
            route_hint="via editável",
            dispense_unit="frasco",
            active=True,
        )
        MedicationRequestItem.objects.create(
            medication_request=self.request,
            drug=self.used_drug,
            dose=Decimal("1"),
            dose_unit="unidade",
            route="via sintética",
            frequency="frequência sintética",
            sequence=1,
        )


class UsedDrugApplicationIntegrityTests(UsedDrugFixtureMixin, TestCase):
    def test_used_drug_historical_fields_cannot_be_rewritten_through_save(self):
        self.used_drug.name = "Nome histórico reescrito"

        with self.assertRaises(ValidationError):
            self.used_drug.save()

        self.used_drug.refresh_from_db()
        self.assertEqual(self.used_drug.name, "Medicamento Sintético Histórico")

    def test_used_drug_can_be_deactivated_without_rewriting_history(self):
        self.used_drug.active = False
        self.used_drug.save()
        self.used_drug.refresh_from_db()

        self.assertFalse(self.used_drug.active)
        self.assertEqual(self.used_drug.name, "Medicamento Sintético Histórico")

    def test_unused_drug_historical_fields_remain_editable(self):
        self.unused_drug.name = "Medicamento Sintético Atualizado"
        self.unused_drug.presentation = "Nova apresentação sintética"
        self.unused_drug.save()
        self.unused_drug.refresh_from_db()

        self.assertEqual(self.unused_drug.name, "Medicamento Sintético Atualizado")
        self.assertEqual(self.unused_drug.presentation, "Nova apresentação sintética")


class UsedDrugPostgreSQLIntegrityTests(UsedDrugFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        if connection.vendor != "postgresql":
            self.skipTest("Os guards desta suíte são específicos do PostgreSQL.")

    def _assert_bulk_update_rejected(self, **changes):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Drug.objects.filter(pk=self.used_drug.pk).update(**changes)

    def test_bulk_update_cannot_rewrite_used_drug_history(self):
        self._assert_bulk_update_rejected(name="Bypass por bulk update")

        self.used_drug.refresh_from_db()
        self.assertEqual(self.used_drug.name, "Medicamento Sintético Histórico")

    def test_raw_sql_cannot_rewrite_used_drug_history(self):
        table = connection.ops.quote_name(Drug._meta.db_table)

        with self.assertRaises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {table} SET presentation = %s WHERE id = %s",
                ["Bypass por SQL direto", self.used_drug.pk],
            )

        self.used_drug.refresh_from_db()
        self.assertEqual(self.used_drug.presentation, "Apresentação histórica")

    def test_bulk_update_can_change_only_active_state_for_used_drug(self):
        updated = Drug.objects.filter(pk=self.used_drug.pk).update(active=False)

        self.assertEqual(updated, 1)
        self.used_drug.refresh_from_db()
        self.assertFalse(self.used_drug.active)
        self.assertEqual(self.used_drug.name, "Medicamento Sintético Histórico")

    def test_unused_drug_still_supports_bulk_historical_update(self):
        updated = Drug.objects.filter(pk=self.unused_drug.pk).update(
            name="Medicamento Sintético Bulk Atualizado",
            presentation="Apresentação bulk atualizada",
        )

        self.assertEqual(updated, 1)
        self.unused_drug.refresh_from_db()
        self.assertEqual(self.unused_drug.name, "Medicamento Sintético Bulk Atualizado")
        self.assertEqual(self.unused_drug.presentation, "Apresentação bulk atualizada")
