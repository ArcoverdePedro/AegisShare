#!/usr/bin/env python3
import os
import uuid
from datetime import date, timedelta
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.models import Permission  # noqa: E402
from django.utils import timezone  # noqa: E402

from apps.clinical.pep.models import Encounter, Patient  # noqa: E402
from apps.clinical.prescription.models import (  # noqa: E402
    Drug,
    Lot,
    MedicationDispense,
    MedicationDispenseItem,
    MedicationRequest,
    MedicationRequestItem,
    StockItem,
)

NURSE_USERNAME = "ci-nursing-offline"
NURSE_PASSWORD = "ci-nursing-offline-password"
PATIENT_ID = uuid.UUID("10000000-0000-4000-8000-000000000004")
OPEN_ENCOUNTER_ID = uuid.UUID("20000000-0000-4000-8000-000000000004")
CLOSED_ENCOUNTER_ID = uuid.UUID("20000000-0000-4000-8000-000000000005")
DRUG_ID = uuid.UUID("30000000-0000-4000-8000-000000000004")
REQUEST_ID = uuid.UUID("40000000-0000-4000-8000-000000000004")
REQUEST_ITEM_ID = uuid.UUID("41000000-0000-4000-8000-000000000004")
STOCK_ID = uuid.UUID("50000000-0000-4000-8000-000000000004")
LOT_ID = uuid.UUID("60000000-0000-4000-8000-000000000004")
DISPENSE_ID = uuid.UUID("70000000-0000-4000-8000-000000000004")
DISPENSE_ITEM_ID = uuid.UUID("80000000-0000-4000-8000-000000000004")


def main():
    user_model = get_user_model()
    nurse, _ = user_model.objects.get_or_create(username=NURSE_USERNAME)
    nurse.email = "ci-nursing-offline@example.invalid"
    nurse.nivel_permissao = "FUNC"
    nurse.is_active = True
    nurse.is_staff = False
    nurse.is_superuser = False
    nurse.set_password(NURSE_PASSWORD)
    nurse.save()
    nurse.user_permissions.add(
        Permission.objects.get(content_type__app_label="nursing", codename="view_nursing"),
        Permission.objects.get(content_type__app_label="nursing", codename="record_vitals"),
        Permission.objects.get(
            content_type__app_label="nursing",
            codename="administer_medication",
        ),
    )

    patient, _ = Patient.objects.update_or_create(
        pk=PATIENT_ID,
        defaults={
            "identifier_type": Patient.IdentifierType.OTHER,
            "identifier": "CI-NUR-OFFLINE-001",
            "full_name": "Paciente Sintético Enfermagem Offline",
            "birth_date": date(1990, 1, 1),
            "created_by": nurse,
            "active": True,
        },
    )

    started_at = timezone.now() - timedelta(hours=1)
    open_encounter, _ = Encounter.objects.update_or_create(
        pk=OPEN_ENCOUNTER_ID,
        defaults={
            "patient": patient,
            "status": Encounter.Status.OPEN,
            "started_at": started_at,
            "ended_at": None,
            "responsible_professional": nurse,
            "created_by": nurse,
        },
    )
    ended_at = timezone.now() - timedelta(minutes=10)
    Encounter.objects.update_or_create(
        pk=CLOSED_ENCOUNTER_ID,
        defaults={
            "patient": patient,
            "status": Encounter.Status.CLOSED,
            "started_at": started_at,
            "ended_at": ended_at,
            "responsible_professional": nurse,
            "created_by": nurse,
        },
    )

    drug, _ = Drug.objects.update_or_create(
        pk=DRUG_ID,
        defaults={
            "code": "CI-NUR-ADMIN-DRUG",
            "name": "Medicamento Sintético Administração E2E",
            "presentation": "Apresentação sintética",
            "dispense_unit": "unidade",
            "active": True,
        },
    )
    request, _ = MedicationRequest.objects.get_or_create(
        pk=REQUEST_ID,
        defaults={
            "encounter": open_encounter,
            "authored_by": nurse,
        },
    )
    MedicationRequest.objects.filter(pk=request.pk).update(
        encounter=open_encounter,
        authored_by=nurse,
        status=MedicationRequest.Status.DRAFT,
        replaces=None,
        submitted_at=None,
        validated_by=None,
        validated_at=None,
        cancelled_by=None,
        cancelled_at=None,
        cancellation_reason="",
    )
    request.refresh_from_db()
    request_item, _ = MedicationRequestItem.objects.update_or_create(
        pk=REQUEST_ITEM_ID,
        defaults={
            "medication_request": request,
            "drug": drug,
            "dose": Decimal("10"),
            "dose_unit": "mg",
            "route": "oral",
            "frequency": "1x ao dia",
            "sequence": 1,
        },
    )
    request.status = MedicationRequest.Status.VALIDATED
    request.submitted_at = timezone.now() - timedelta(minutes=30)
    request.validated_by = nurse
    request.validated_at = timezone.now() - timedelta(minutes=20)
    request.save()

    stock, _ = StockItem.objects.update_or_create(
        pk=STOCK_ID,
        defaults={
            "drug": drug,
            "storage_location": "Farmácia Enfermagem E2E",
            "minimum_level": Decimal("0"),
            "active": True,
        },
    )
    lot, _ = Lot.objects.update_or_create(
        pk=LOT_ID,
        defaults={
            "stock_item": stock,
            "lot_number": "NUR-E2E-LOT-001",
            "expires_on": timezone.localdate() + timedelta(days=90),
            "quantity_available": Decimal("10"),
            "active": True,
        },
    )
    dispense, _ = MedicationDispense.objects.get_or_create(
        pk=DISPENSE_ID,
        defaults={
            "medication_request": request,
            "dispensed_by": nurse,
            "dispensed_at": timezone.now() - timedelta(minutes=10),
        },
    )
    MedicationDispenseItem.objects.get_or_create(
        pk=DISPENSE_ITEM_ID,
        defaults={
            "dispense": dispense,
            "request_item": request_item,
            "lot": lot,
            "quantity": Decimal("2"),
        },
    )
    print("Jornadas E2E de Enfermagem prontas.")


if __name__ == "__main__":
    main()
