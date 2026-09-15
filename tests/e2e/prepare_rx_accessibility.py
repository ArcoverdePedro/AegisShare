#!/usr/bin/env python3
import os
from datetime import timedelta
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.models import Permission  # noqa: E402
from django.utils import timezone  # noqa: E402

from apps.clinical.pep.models import Encounter, Patient  # noqa: E402
from apps.clinical.prescription.catalog_services import (  # noqa: E402
    create_interaction_reference,
)
from apps.clinical.prescription.models import (  # noqa: E402
    Drug,
    Interaction,
    Lot,
    MedicationRequest,
    StockItem,
)
from apps.clinical.prescription.services import (  # noqa: E402
    add_medication_request_item,
    create_medication_request,
    submit_medication_request,
    validate_medication_request,
)
from apps.clinical.prescription.stock_services import (  # noqa: E402
    create_lot,
    create_stock_item,
)

USERNAME = "ci-rx-accessibility"
PASSWORD = "ci-rx-accessibility-password"
DENIED_USERNAME = "ci-rx-denied-client"
DENIED_PASSWORD = "ci-rx-denied-client-password"
LOT_NUMBER = "E2E-RX-LOT-A11Y-001"
PATIENT_IDENTIFIER = "E2E-RX-PATIENT-001"


def configure_admin():
    User = get_user_model()
    user, _ = User.objects.get_or_create(username=USERNAME)
    user.email = "ci-rx-accessibility@example.invalid"
    user.nivel_permissao = "ADM"
    user.is_active = True
    user.is_staff = True
    user.is_superuser = True
    user.set_password(PASSWORD)
    user.save()
    return user


def configure_denied_client():
    User = get_user_model()
    user, _ = User.objects.get_or_create(username=DENIED_USERNAME)
    user.email = "ci-rx-denied-client@example.invalid"
    user.nivel_permissao = "CLI"
    user.is_active = True
    user.is_staff = False
    user.is_superuser = False
    user.set_password(DENIED_PASSWORD)
    user.save()

    permissions = Permission.objects.filter(
        content_type__app_label="prescription",
        codename__in={
            "view_medication_request",
            "prescribe_medication",
            "validate_medication_request",
            "cancel_medication_request",
            "view_medication_dispense",
            "dispense_medication",
            "view_drug",
            "manage_drug_catalog",
            "view_pharmacy_stock",
            "manage_pharmacy_stock",
        },
    )
    user.user_permissions.set(permissions)
    return user


def ensure_drug(*, code, name, presentation):
    drug, _ = Drug.objects.update_or_create(
        code=code,
        defaults={
            "name": name,
            "presentation": presentation,
            "strength_text": "Referência sintética",
            "route_hint": "",
            "dispense_unit": "unidade",
            "active": True,
        },
    )
    return drug


def ensure_stock(*, actor, drug):
    stock = StockItem.objects.filter(
        drug=drug,
        storage_location="Farmácia E2E",
    ).first()
    if stock is None:
        stock = create_stock_item(
            actor=actor,
            drug_id=drug.pk,
            storage_location="Farmácia E2E",
            minimum_level=Decimal("5"),
        )

    lot = Lot.objects.filter(stock_item=stock, lot_number=LOT_NUMBER).first()
    if lot is None:
        lot = create_lot(
            actor=actor,
            stock_item_id=stock.pk,
            lot_number=LOT_NUMBER,
            expires_on=timezone.localdate() + timedelta(days=180),
            initial_quantity=Decimal("12"),
        )
    return stock, lot


def ensure_encounter(*, actor):
    patient, _ = Patient.objects.get_or_create(
        identifier_type=Patient.IdentifierType.OTHER,
        identifier=PATIENT_IDENTIFIER,
        defaults={
            "full_name": "Paciente Sintético RX E2E",
            "birth_date": timezone.localdate() - timedelta(days=365 * 35),
            "created_by": actor,
        },
    )
    encounter = Encounter.objects.filter(
        patient=patient,
        status=Encounter.Status.OPEN,
        responsible_professional=actor,
    ).first()
    if encounter is None:
        encounter = Encounter.objects.create(
            patient=patient,
            encounter_type=Encounter.Type.CONSULTATION,
            status=Encounter.Status.OPEN,
            responsible_professional=actor,
            created_by=actor,
            location="Ambulatório E2E",
        )
    return patient, encounter


def ensure_blocking_interaction(*, actor, drug_a, drug_b):
    interaction = Interaction.objects.filter(
        drug_a_id__in=[drug_a.pk, drug_b.pk],
        drug_b_id__in=[drug_a.pk, drug_b.pk],
        reference_version="e2e-block-v1",
    ).first()
    if interaction is None:
        interaction = create_interaction_reference(
            actor=actor,
            drug_a_id=drug_a.pk,
            drug_b_id=drug_b.pk,
            severity=Interaction.Severity.MAJOR,
            blocking=True,
            summary="Interação sintética bloqueante E2E",
            reference_source="fixture-sintetica-e2e",
            reference_version="e2e-block-v1",
            active=True,
        )
    return interaction


def ensure_submitted_blocked_request(*, actor, encounter, drug_a, drug_b):
    request = MedicationRequest.objects.filter(
        encounter=encounter,
        authored_by=actor,
        status=MedicationRequest.Status.SUBMITTED,
        items__drug=drug_a,
    ).filter(items__drug=drug_b).first()
    if request is not None:
        return request

    request = create_medication_request(encounter_id=encounter.pk, actor=actor)
    for sequence, (drug, dose) in enumerate(
        ((drug_a, Decimal("10")), (drug_b, Decimal("5"))),
        start=1,
    ):
        add_medication_request_item(
            request_id=request.pk,
            actor=actor,
            drug_id=drug.pk,
            dose=dose,
            dose_unit="mg",
            route="oral",
            frequency="1x ao dia",
            sequence=sequence,
        )
    return submit_medication_request(request_id=request.pk, actor=actor)


def ensure_validated_request(*, actor, encounter, drug):
    request = MedicationRequest.objects.filter(
        encounter=encounter,
        authored_by=actor,
        status=MedicationRequest.Status.VALIDATED,
        items__drug=drug,
    ).first()
    if request is not None:
        return request

    request = create_medication_request(encounter_id=encounter.pk, actor=actor)
    add_medication_request_item(
        request_id=request.pk,
        actor=actor,
        drug_id=drug.pk,
        dose=Decimal("10"),
        dose_unit="mg",
        route="oral",
        frequency="1x ao dia",
        sequence=1,
    )
    submit_medication_request(request_id=request.pk, actor=actor)
    request, _review = validate_medication_request(
        request_id=request.pk,
        actor=actor,
        manual_allergy_review_confirmed=True,
    )
    return request


def main():
    admin = configure_admin()
    denied_client = configure_denied_client()
    primary = ensure_drug(
        code="E2E-RX-A11Y-001",
        name="Medicamento Sintético Acessibilidade",
        presentation="Apresentação E2E",
    )
    secondary = ensure_drug(
        code="E2E-RX-A11Y-002",
        name="Medicamento Sintético Secundário",
        presentation="Apresentação E2E alternativa",
    )
    stock, lot = ensure_stock(actor=admin, drug=primary)
    patient, encounter = ensure_encounter(actor=admin)
    interaction = ensure_blocking_interaction(
        actor=admin,
        drug_a=primary,
        drug_b=secondary,
    )
    blocked_request = ensure_submitted_blocked_request(
        actor=admin,
        encounter=encounter,
        drug_a=primary,
        drug_b=secondary,
    )
    validated_request = ensure_validated_request(
        actor=admin,
        encounter=encounter,
        drug=primary,
    )

    print(
        "Dados E2E RX prontos:",
        admin.username,
        denied_client.username,
        patient.identifier,
        primary.code,
        stock.storage_location,
        lot.lot_number,
        interaction.pk,
        blocked_request.pk,
        validated_request.pk,
    )


if __name__ == "__main__":
    main()
