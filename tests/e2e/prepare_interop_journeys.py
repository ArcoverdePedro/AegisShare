#!/usr/bin/env python3
import os
from datetime import date

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

import django

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.models import Permission  # noqa: E402

from apps.clinical.pep.models import Patient  # noqa: E402


def main():
    permission = Permission.objects.get(
        content_type__app_label="interoperability", codename="export_patient"
    )
    for name in ("exporter", "outsider"):
        user, _ = get_user_model().objects.get_or_create(username=f"ci-interop-{name}")
        user.email = f"ci-interop-{name}@example.invalid"
        user.nivel_permissao = "FUNC"
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.set_password(f"ci-interop-{name}-password")
        user.save()
        user.user_permissions.add(permission)
        if name == "exporter":
            Patient.objects.update_or_create(
                pk="12000000-0000-4000-8000-000000000001",
                defaults={
                    "identifier_type": "OTHER",
                    "identifier": "E2E-INTEROP-PRIVATE-ID",
                    "full_name": "Pessoa Sintética Interop E2E",
                    "birth_date": date(1990, 1, 15),
                    "sex": "I",
                    "created_by": user,
                    "active": True,
                },
            )


if __name__ == "__main__":
    main()
