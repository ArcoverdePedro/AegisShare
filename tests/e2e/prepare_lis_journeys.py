#!/usr/bin/env python3
import os
from datetime import date

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.models import Permission  # noqa: E402

from apps.clinical.lis.models import LabTest  # noqa: E402
from apps.clinical.pep.models import Encounter, Patient  # noqa: E402


def main():
    permissions = Permission.objects.filter(
        content_type__app_label="lis",
        codename__in=[
            "view_orders",
            "order_test",
            "collect_specimen",
        ],
    )
    for role in ("operator", "outsider"):
        user, _ = get_user_model().objects.get_or_create(username=f"ci-lis-{role}")
        user.nivel_permissao = "FUNC"
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.set_password(f"ci-lis-{role}-password")
        user.save()
        user.user_permissions.add(*permissions)
        if role == "operator":
            patient, _ = Patient.objects.get_or_create(
                id="05000000-0000-4000-8000-000000000001",
                defaults={
                    "identifier_type": "OTHER",
                    "identifier": "LIS-E2E-SYNTH",
                    "full_name": "Pessoa Sintética LIS",
                    "birth_date": date(1990, 1, 1),
                    "created_by": user,
                },
            )
            Encounter.objects.get_or_create(
                id="05000000-0000-4000-8000-000000000002",
                defaults={"patient": patient, "created_by": user, "responsible_professional": user},
            )
    LabTest.objects.update_or_create(
        id="05000000-0000-4000-8000-000000000003",
        defaults={
            "code": "LIS-E2E",
            "name": "Exame Sintético LIS",
            "specimen_type": "Material Sintético LIS",
            "active": True,
        },
    )
    print("Dados sintéticos LIS preparados; usar somente em banco de teste.")


if __name__ == "__main__":
    main()
