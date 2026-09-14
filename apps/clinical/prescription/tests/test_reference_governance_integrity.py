from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.utils import timezone

from aegis_share.tests.helpers import make_user

from ..models import DoseRule, Drug, Interaction


class ApprovedReferenceFixtureMixin:
    def setUp(self):
        super().setUp()
        self.actor = make_user("rx-reference-integrity-actor", role="ADM")
        self.drug_a = Drug.objects.create(
            code="RX-REF-INTEGRITY-A",
            name="Medicamento Sintético Referência A",
            presentation="Apresentação sintética A",
            dispense_unit="unidade",
        )
        self.drug_b = Drug.objects.create(
            code="RX-REF-INTEGRITY-B",
            name="Medicamento Sintético Referência B",
            presentation="Apresentação sintética B",
            dispense_unit="unidade",
        )

    def approved_interaction(self):
        return Interaction.objects.create(
            drug_a=self.drug_a,
            drug_b=self.drug_b,
            severity=Interaction.Severity.MODERATE,
            blocking=True,
            summary="Interação exclusivamente sintética para integridade.",
            reference_source="Fonte sintética de teste",
            reference_version="INTEGRITY-INT-1",
            approved_by=self.actor,
            approved_at=timezone.now(),
            active=True,
        )

    def approved_dose_rule(self):
        return DoseRule.objects.create(
            drug=self.drug_a,
            rule_code="INTEGRITY-AGE-RULE",
            basis=DoseRule.Basis.AGE,
            min_age_days=1,
            max_age_days=100,
            min_dose=Decimal("1"),
            max_dose=Decimal("2"),
            dose_unit="unidade-teste",
            reference_source="Fonte sintética de teste",
            reference_version="INTEGRITY-DOSE-1",
            approved_by=self.actor,
            approved_at=timezone.now(),
            active=True,
        )


class ApprovedReferenceApplicationIntegrityTests(ApprovedReferenceFixtureMixin, TestCase):
    def test_approved_interaction_cannot_be_rewritten_through_save(self):
        interaction = self.approved_interaction()
        interaction.summary = "Conteúdo reescrito"

        with self.assertRaises(ValidationError):
            interaction.save()

        interaction.refresh_from_db()
        self.assertEqual(
            interaction.summary,
            "Interação exclusivamente sintética para integridade.",
        )

    def test_approved_dose_rule_cannot_be_rewritten_through_save(self):
        rule = self.approved_dose_rule()
        rule.max_dose = Decimal("3")

        with self.assertRaises(ValidationError):
            rule.save()

        rule.refresh_from_db()
        self.assertEqual(rule.max_dose, Decimal("2"))

    def test_approved_reference_can_be_deactivated_but_not_reactivated(self):
        interaction = self.approved_interaction()
        interaction.active = False
        interaction.save()
        interaction.refresh_from_db()
        self.assertFalse(interaction.active)

        interaction.active = True
        with self.assertRaises(ValidationError):
            interaction.save()

        interaction.refresh_from_db()
        self.assertFalse(interaction.active)

    def test_approved_reference_cannot_be_deleted_through_orm(self):
        rule = self.approved_dose_rule()

        with self.assertRaises(ValidationError), transaction.atomic():
            rule.delete()

        self.assertTrue(DoseRule.objects.filter(pk=rule.pk).exists())

    def test_unapproved_reference_remains_editable_and_deletable(self):
        interaction = Interaction.objects.create(
            drug_a=self.drug_a,
            drug_b=self.drug_b,
            severity=Interaction.Severity.INFO,
            blocking=False,
            summary="Rascunho sintético editável.",
            reference_source="Fonte sintética de teste",
            reference_version="INTEGRITY-DRAFT-1",
            active=False,
        )
        interaction.summary = "Rascunho sintético atualizado."
        interaction.save()
        interaction.delete()

        self.assertFalse(Interaction.objects.filter(pk=interaction.pk).exists())


class ApprovedReferencePostgreSQLIntegrityTests(ApprovedReferenceFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        if connection.vendor != "postgresql":
            self.skipTest("Os guards desta suíte são específicos do PostgreSQL.")

    def _assert_bulk_update_rejected(self, queryset, **changes):
        with self.assertRaises(IntegrityError), transaction.atomic():
            queryset.update(**changes)

    def test_bulk_update_cannot_rewrite_approved_interaction(self):
        interaction = self.approved_interaction()

        self._assert_bulk_update_rejected(
            Interaction.objects.filter(pk=interaction.pk),
            summary="Bypass por bulk update",
        )

        interaction.refresh_from_db()
        self.assertEqual(
            interaction.summary,
            "Interação exclusivamente sintética para integridade.",
        )

    def test_bulk_update_cannot_rewrite_approved_dose_rule(self):
        rule = self.approved_dose_rule()

        self._assert_bulk_update_rejected(
            DoseRule.objects.filter(pk=rule.pk),
            max_dose=Decimal("3"),
        )

        rule.refresh_from_db()
        self.assertEqual(rule.max_dose, Decimal("2"))

    def test_bulk_deactivation_is_allowed_but_bulk_reactivation_is_rejected(self):
        interaction = self.approved_interaction()

        updated = Interaction.objects.filter(pk=interaction.pk).update(active=False)
        self.assertEqual(updated, 1)

        self._assert_bulk_update_rejected(
            Interaction.objects.filter(pk=interaction.pk),
            active=True,
        )

        interaction.refresh_from_db()
        self.assertFalse(interaction.active)

    def test_raw_delete_cannot_remove_approved_reference(self):
        interaction = self.approved_interaction()
        table = connection.ops.quote_name(Interaction._meta.db_table)

        with self.assertRaises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {table} WHERE id = %s", [interaction.pk])

        self.assertTrue(Interaction.objects.filter(pk=interaction.pk).exists())

    def test_unapproved_reference_still_supports_bulk_update_and_delete(self):
        rule = DoseRule.objects.create(
            drug=self.drug_a,
            rule_code="INTEGRITY-DRAFT-RULE",
            basis=DoseRule.Basis.AGE,
            min_age_days=1,
            max_age_days=100,
            min_dose=Decimal("1"),
            max_dose=Decimal("2"),
            dose_unit="unidade-teste",
            reference_source="Fonte sintética de teste",
            reference_version="INTEGRITY-DRAFT-DOSE-1",
            active=False,
        )

        updated = DoseRule.objects.filter(pk=rule.pk).update(max_dose=Decimal("3"))
        self.assertEqual(updated, 1)
        deleted, _ = DoseRule.objects.filter(pk=rule.pk).delete()

        self.assertEqual(deleted, 1)
        self.assertFalse(DoseRule.objects.filter(pk=rule.pk).exists())
