import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.models import Permission  # noqa: E402

from apps.interoperability.models import LaboratorySource  # noqa: E402


def main():
    source, _ = LaboratorySource.objects.get_or_create(
        id="12000000-0000-4000-8000-000000000001",
        defaults={"code": "INBOX-SYNTH", "label": "Origem sintética"},
    )
    source.active = True
    source.save()
    for role in ("operator", "outsider"):
        user, _ = get_user_model().objects.get_or_create(username=f"ci-inbox-{role}")
        user.nivel_permissao = "FUNC"
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.set_password(f"ci-inbox-{role}-password")
        user.save()
        user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="interoperability",
                codename__in=["view_lab_inbox", "receive_lab_file"],
            )
        )
        if role == "operator":
            source.operators.add(user)
        else:
            source.operators.remove(user)
    print("Origem e operadores sintéticos preparados; somente em banco de teste.")


if __name__ == "__main__":
    main()
