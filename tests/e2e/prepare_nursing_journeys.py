#!/usr/bin/env python3
import os
import uuid
from datetime import date, timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.models import Permission  # noqa: E402
from django.utils import timezone  # noqa: E402

from apps.clinical.pep.models import Encounter, Patient  # noqa: E402

NURSE_USERNAME = "ci-nursing-offline"
NURSE_PASSWORD = "ci-nursing-offline-password"
PATIENT_ID = uuid.UUID("10000000-0000-4000-8000-000000000004")
OPEN_ENCOUNTER_ID = uuid.UUID("20000000-0000-4000-8000-000000000004")
CLOSED_ENCOUNTER_ID = uuid.UUID("20000000-0000-4000-8000-000000000005")


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
    Encounter.objects.update_or_create(
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
    print("Jornada E2E de Enfermagem offline pronta.")


if __name__ == "__main__":
    main()
