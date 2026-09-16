#!/usr/bin/env python3
import os
from datetime import date

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.models import Permission  # noqa: E402

from apps.clinical.pep.models import Patient  # noqa: E402
from apps.compliance.models import DataSubjectRequest, DataSubjectRequestEvent  # noqa: E402


def main():
    permissions = Permission.objects.filter(
        content_type__app_label="compliance",
        codename__in=["view_requests", "register_request", "process_request"],
    )
    for name in ("operator", "outsider"):
        user, _ = get_user_model().objects.get_or_create(username=f"ci-compliance-{name}")
        user.email = f"ci-compliance-{name}@example.invalid"
        user.nivel_permissao = "FUNC"
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.set_password(f"ci-compliance-{name}-password")
        user.save()
        user.user_permissions.add(*permissions)
        if name == "operator":
            patient, _ = Patient.objects.update_or_create(
                pk="13000000-0000-4000-8000-000000000001",
                defaults={
                    "identifier_type": "OTHER",
                    "identifier": "E2E-LGP-PRIVATE-ID",
                    "full_name": "Pessoa Sintética Compliance E2E",
                    "birth_date": date(1990, 1, 15),
                    "created_by": user,
                    "active": True,
                },
            )
            item, created = DataSubjectRequest.objects.get_or_create(
                pk="13000000-0000-4000-8000-000000000002",
                defaults={
                    "patient": patient,
                    "category": "ACCESS",
                    "summary": "Resumo sintético de referência",
                    "created_by": user,
                },
            )
            if created:
                DataSubjectRequestEvent.objects.create(
                    request=item, to_status="RECEIVED", actor=user
                )


if __name__ == "__main__":
    main()
