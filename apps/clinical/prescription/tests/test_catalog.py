from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.models import Encounter, Patient

from ..catalog_services import (
    CatalogStateError,
    create_dose_rule_reference,
    create_drug,
    create_interaction_reference,
    set_interaction_reference_active,
    update_drug,
)
from ..models import (
    DoseRule,
    Drug,
    Interaction,
    MedicationRequest,
    MedicationRequestItem,
)


class CatalogServiceTests(TestCase):
    def setUp(self):
        self.admin = make_user("rx-catalog-admin", role="ADM")
        self.manager = make_user("rx-catalog-manager", role="FUNC")
        self.other = make_user("rx-catalog-other", role="FUNC")
        self.client_role_user = make_user("rx-catalog-client", role="CLI")
        self._grant_permission(self.manager, "manage_drug_catalog")
        self._grant_permission(self.client_role_user, "manage_drug_catalog")

    def _grant_permission(self, user, codename):
        permission = Permission.objects.get(
            codename=codename,
            content_type__app_label="prescription",
        )
        user.user_permissions.add(permission)
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            if hasattr(user, cache_name):
                delattr(user, cache_name)

    def _create_drug(self, *, code="SYN-RX-001", name="Medicamento Sintético A"):
        return create_drug(
            actor=self.manager,
            code=code,
            name=name,
            presentation="Apresentação sintética",
            strength_text="10 unidades de teste",
            route_hint="via sintética",
            dispense_unit="unidade",
        )

    def test_catalog_management_requires_explicit_internal_capability(self):
        with self.assertRaises(PermissionDenied):
            create_drug(
                actor=self.other,
                code="SYN-DENIED-1",
                name="Negado",
                presentation="Teste",
                dispense_unit="unidade",
            )

        with self.assertRaises(PermissionDenied):
            create_drug(
                actor=self.client_role_user,
                code="SYN-DENIED-2",
                name="Negado cliente",
                presentation="Teste",
                dispense_unit="unidade",
            )

    def test_create_drug_normalizes_catalog_fields(self):
        drug = create_drug(
            actor=self.manager,
            code="  syn-rx-002  ",
            name=" Medicamento   Sintético B ",
            presentation="  Solução   de teste ",
            strength_text="  20   unidades ",
            route_hint="  via   teste ",
            dispense_unit="  frasco  ",
        )

        self.assertEqual(drug.code, "SYN-RX-002")
        self.assertEqual(drug.name, "Medicamento Sintético B")
        self.assertEqual(drug.presentation, "Solução de teste")
        self.assertEqual(drug.dispense_unit, "frasco")

    def test_used_drug_cannot_have_historical_meaning_rewritten(self):
        drug = self._create_drug()
        patient = Patient.objects.create(
            identifier_type=Patient.IdentifierType.OTHER,
            identifier="RX-CATALOG-PATIENT",
            full_name="Paciente Sintético Catálogo",
            birth_date=timezone.localdate() - timedelta(days=365 * 30),
            created_by=self.admin,
        )
        encounter = Encounter.objects.create(
            patient=patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            responsible_professional=self.manager,
            created_by=self.admin,
        )
        request = MedicationRequest.objects.create(
            encounter=encounter,
            authored_by=self.manager,
        )
        MedicationRequestItem.objects.create(
            medication_request=request,
            drug=drug,
            dose=Decimal("1"),
            dose_unit="unidade",
            route="via sintética",
            frequency="frequência sintética",
            sequence=1,
        )

        with self.assertRaises(CatalogStateError):
            update_drug(
                drug_id=drug.pk,
                actor=self.manager,
                code=drug.code,
                name="Nome histórico reescrito",
                presentation=drug.presentation,
                strength_text=drug.strength_text,
                route_hint=drug.route_hint,
                dispense_unit=drug.dispense_unit,
                active=True,
            )

        updated = update_drug(
            drug_id=drug.pk,
            actor=self.manager,
            code=drug.code,
            name=drug.name,
            presentation=drug.presentation,
            strength_text=drug.strength_text,
            route_hint=drug.route_hint,
            dispense_unit=drug.dispense_unit,
            active=False,
        )
        self.assertFalse(updated.active)

    def test_active_interaction_is_stamped_with_approver_and_version(self):
        drug_a = self._create_drug(code="SYN-INT-A", name="Sintético A")
        drug_b = self._create_drug(code="SYN-INT-B", name="Sintético B")

        interaction = create_interaction_reference(
            actor=self.manager,
            drug_a_id=drug_a.pk,
            drug_b_id=drug_b.pk,
            severity=Interaction.Severity.MODERATE,
            blocking=True,
            summary="Interação exclusivamente sintética para teste automatizado.",
            reference_source="Fonte sintética de teste",
            reference_version="TEST-1",
            active=True,
        )

        self.assertTrue(interaction.active)
        self.assertEqual(interaction.approved_by, self.manager)
        self.assertIsNotNone(interaction.approved_at)
        self.assertEqual(interaction.reference_version, "TEST-1")

    def test_inactive_interaction_requires_explicit_activation(self):
        drug_a = self._create_drug(code="SYN-DRAFT-A", name="Sintético Draft A")
        drug_b = self._create_drug(code="SYN-DRAFT-B", name="Sintético Draft B")
        interaction = create_interaction_reference(
            actor=self.manager,
            drug_a_id=drug_a.pk,
            drug_b_id=drug_b.pk,
            severity=Interaction.Severity.INFO,
            blocking=False,
            summary="Referência sintética ainda não ativa.",
            reference_source="Fonte sintética de teste",
            reference_version="TEST-DRAFT-1",
            active=False,
        )
        self.assertIsNone(interaction.approved_by)
        self.assertIsNone(interaction.approved_at)

        activated = set_interaction_reference_active(
            interaction_id=interaction.pk,
            actor=self.manager,
            active=True,
        )
        self.assertTrue(activated.active)
        self.assertEqual(activated.approved_by, self.manager)
        self.assertIsNotNone(activated.approved_at)

    def test_approved_reference_requires_new_version_after_deactivation(self):
        drug_a = self._create_drug(code="SYN-VERSION-A", name="Sintético Versão A")
        drug_b = self._create_drug(code="SYN-VERSION-B", name="Sintético Versão B")
        interaction = create_interaction_reference(
            actor=self.manager,
            drug_a_id=drug_a.pk,
            drug_b_id=drug_b.pk,
            severity=Interaction.Severity.INFO,
            blocking=False,
            summary="Referência sintética versionada para teste.",
            reference_source="Fonte sintética de teste",
            reference_version="TEST-VERSION-1",
            active=True,
        )

        set_interaction_reference_active(
            interaction_id=interaction.pk,
            actor=self.manager,
            active=False,
        )

        with self.assertRaises(CatalogStateError):
            set_interaction_reference_active(
                interaction_id=interaction.pk,
                actor=self.manager,
                active=True,
            )

    def test_active_dose_rule_is_stamped_without_executable_formula(self):
        drug = self._create_drug(code="SYN-DOSE-1", name="Sintético Dose")
        rule = create_dose_rule_reference(
            actor=self.manager,
            drug_id=drug.pk,
            rule_code="SYNTHETIC-AGE-RULE",
            basis=DoseRule.Basis.AGE,
            min_age_days=1,
            max_age_days=100,
            min_dose=Decimal("1"),
            max_dose=Decimal("2"),
            dose_unit="unidade-teste",
            reference_source="Fonte sintética de teste",
            reference_version="TEST-DOSE-1",
            active=True,
        )

        self.assertTrue(rule.active)
        self.assertEqual(rule.approved_by, self.manager)
        self.assertIsNotNone(rule.approved_at)
        self.assertEqual(rule.rule_code, "SYNTHETIC-AGE-RULE")


class DrugCatalogViewTests(TestCase):
    def setUp(self):
        self.admin = make_user("rx-catalog-view-admin", role="ADM")
        self.viewer = make_user("rx-catalog-viewer", role="FUNC")
        self.manager = make_user("rx-catalog-view-manager", role="FUNC")
        self.denied = make_user("rx-catalog-view-denied", role="FUNC")
        self._grant_permission(self.viewer, "view_drug")
        self._grant_permission(self.manager, "view_drug")
        self._grant_permission(self.manager, "manage_drug_catalog")
        Drug.objects.create(
            code="SYN-VIEW-1",
            name="Medicamento Sintético Visível",
            presentation="Apresentação de teste",
            dispense_unit="unidade",
        )

    def _grant_permission(self, user, codename):
        permission = Permission.objects.get(
            codename=codename,
            content_type__app_label="prescription",
        )
        user.user_permissions.add(permission)
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            if hasattr(user, cache_name):
                delattr(user, cache_name)

    def test_catalog_requires_view_capability_and_is_no_store(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("prescription:drug_catalog"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Medicamento Sintético Visível")
        self.assertIn("no-store", response["Cache-Control"])

        self.client.force_login(self.denied)
        denied_response = self.client.get(reverse("prescription:drug_catalog"))
        self.assertEqual(denied_response.status_code, 403)

    def test_manager_can_create_drug_through_server_rendered_form(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("prescription:drug_create"),
            {
                "code": " syn-view-2 ",
                "name": "Novo medicamento sintético",
                "presentation": "Apresentação sintética",
                "strength_text": "",
                "route_hint": "",
                "dispense_unit": "unidade",
                "active": "on",
            },
        )

        self.assertRedirects(response, reverse("prescription:drug_catalog"))
        self.assertTrue(Drug.objects.filter(code="SYN-VIEW-2", active=True).exists())

    def test_catalog_mutation_requires_manage_capability(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("prescription:drug_create"))
        self.assertEqual(response.status_code, 403)
