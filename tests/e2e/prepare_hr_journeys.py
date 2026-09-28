#!/usr/bin/env python3
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.models import Permission  # noqa: E402

from apps.admin.hr.models import Employee  # noqa: E402


def configure_user(pk, username, role="FUNC", *, staff=False, superuser=False):
    user, _ = get_user_model().objects.get_or_create(pk=pk, defaults={"username": username})
    user.username = username
    user.first_name = "Pessoa"
    user.last_name = f"Sintética HR {username.rsplit('-', 1)[-1]}"
    user.nivel_permissao = role
    user.is_active = True
    user.is_staff = staff
    user.is_superuser = superuser
    user.set_password(f"{username}-password")
    user.save()
    return user


def main():
    permissions = Permission.objects.filter(
        content_type__app_label="hr",
        codename__in=["view_employee", "add_employee", "change_employee"],
    )
    operator = configure_user("10000000-0000-4000-8000-000000000001", "ci-hr-operator", staff=True)
    operator.user_permissions.set(permissions)
    viewer = configure_user("10000000-0000-4000-8000-000000000002", "ci-hr-viewer")
    viewer.user_permissions.set(permissions.filter(codename="view_employee"))
    delegate = configure_user("10000000-0000-4000-8000-000000000003", "ci-hr-delegate", staff=True)
    delegate.user_permissions.set(permissions)
    client = configure_user("10000000-0000-4000-8000-000000000004", "ci-hr-client", role="CLI")
    client.user_permissions.set(permissions)
    configure_user(
        "10000000-0000-4000-8000-000000000005",
        "ci-hr-admin",
        role="ADM",
        staff=True,
        superuser=True,
    )
    candidate = configure_user("10000000-0000-4000-8000-000000000006", "ci-hr-person")
    candidate.user_permissions.clear()
    Employee.objects.filter(user=candidate).delete()
    Employee.objects.update_or_create(
        id="10000000-0000-4000-8000-000000000010",
        defaults={
            "user": operator,
            "department": "Setor sintético HR",
            "job_title": "Função sintética HR",
            "active": True,
        },
    )
    print("Dados sintéticos HR preparados; usar somente em banco de teste.")


if __name__ == "__main__":
    main()
