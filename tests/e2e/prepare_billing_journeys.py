#!/usr/bin/env python3
import os
from datetime import date

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.models import Permission  # noqa: E402

from apps.clinical.pep.models import Encounter, Patient, PatientAccessGrant  # noqa: E402


def main():
    permissions = Permission.objects.filter(
        content_type__app_label="billing",
        codename__in=[
            "view_accounts",
            "open_account",
            "add_item",
        ],
    )
    for role in ("operator", "outsider", "delegate"):
        user, _ = get_user_model().objects.get_or_create(username=f"ci-billing-{role}")
        user.nivel_permissao = "FUNC"
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.set_password(f"ci-billing-{role}-password")
        user.save()
        user.user_permissions.add(*permissions)
        if role == "operator":
            patient, _ = Patient.objects.get_or_create(
                id="08000000-0000-4000-8000-000000000001",
                defaults={
                    "identifier_type": "OTHER",
                    "identifier": "BILL-E2E-SYNTH",
                    "full_name": "Pessoa Sintética BILL",
                    "birth_date": date(1990, 1, 1),
                    "created_by": user,
                },
            )
            Encounter.objects.get_or_create(
                id="08000000-0000-4000-8000-000000000002",
                defaults={"patient": patient, "created_by": user, "responsible_professional": user},
            )
    operator = get_user_model().objects.get(username="ci-billing-operator")
    Encounter.objects.get_or_create(
        id="08000000-0000-4000-8000-000000000005",
        defaults={"patient": patient, "created_by": operator, "responsible_professional": operator},
    )
    admin_user, _ = get_user_model().objects.get_or_create(username="ci-billing-admin")
    admin_user.nivel_permissao = "ADM"
    admin_user.is_active = admin_user.is_staff = admin_user.is_superuser = True
    admin_user.set_password("ci-billing-admin-password")
    admin_user.save()
    PatientAccessGrant.objects.update_or_create(
        id="08000000-0000-4000-8000-000000000004",
        defaults={
            "patient": patient,
            "user": get_user_model().objects.get(username="ci-billing-delegate"),
            "granted_by": admin_user,
            "reason": "Concessão sintética E2E",
        },
    )
    print("Dados sintéticos BILL preparados; usar somente em banco de teste.")


if __name__ == "__main__":
    main()
