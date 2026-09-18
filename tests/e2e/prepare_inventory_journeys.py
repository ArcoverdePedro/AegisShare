#!/usr/bin/env python3
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.models import Permission  # noqa: E402

from apps.admin.inventory.models import InventoryItem  # noqa: E402


def main():
    permissions = Permission.objects.filter(
        content_type__app_label="inventory", codename__in=["view_requisitions", "request_material"]
    )
    for role in ("operator", "reader", "delegate", "client", "admin"):
        lookup = (
            {"pk": "09000000-0000-4000-8000-000000000003"}
            if role == "delegate"
            else {"username": f"ci-inventory-{role}"}
        )
        user, _ = get_user_model().objects.get_or_create(
            **lookup, defaults={"username": f"ci-inventory-{role}"}
        )
        user.nivel_permissao = "CLI" if role == "client" else "ADM" if role == "admin" else "FUNC"
        user.is_active = True
        user.is_staff = user.is_superuser = role == "admin"
        user.set_password(f"ci-inventory-{role}-password")
        user.save()
        user.user_permissions.set(
            permissions.filter(codename="view_requisitions") if role == "reader" else permissions
        )
    for index in (1, 2):
        InventoryItem.objects.update_or_create(
            id=f"09000000-0000-4000-8000-{index:012}",
            defaults={
                "code": f"INV-E2E-{index}",
                "name": f"Material sintético INV {index}",
                "unit": "caixa",
                "active": True,
            },
        )
    print("Dados sintéticos INV preparados; usar somente em banco de teste.")


if __name__ == "__main__":
    main()
