#!/usr/bin/env python3
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

from aegis_share.models import IPFSFile  # noqa: E402

ADMIN_USERNAME = "ci-e2e-admin"
ADMIN_PASSWORD = "ci-e2e-admin-password"
OWNER_USERNAME = "ci-e2e-owner"
OWNER_PASSWORD = "ci-e2e-owner-password"
RECIPIENT_USERNAME = "ci-e2e-recipient"
RECIPIENT_PASSWORD = "ci-e2e-recipient-password"
FILE_NAME = "ci-e2e-document.txt"
FILE_CID = "bafy-ci-e2e-core-journeys"


def configure_user(username, password, *, role, is_staff=False, is_superuser=False):
    User = get_user_model()
    user, _ = User.objects.get_or_create(username=username)
    user.email = f"{username}@example.invalid"
    user.nivel_permissao = role
    user.is_active = True
    user.is_staff = is_staff
    user.is_superuser = is_superuser
    user.set_password(password)
    user.save()
    return user


def main():
    admin = configure_user(
        ADMIN_USERNAME,
        ADMIN_PASSWORD,
        role="ADM",
        is_staff=True,
        is_superuser=True,
    )
    owner = configure_user(OWNER_USERNAME, OWNER_PASSWORD, role="CLI")
    recipient = configure_user(RECIPIENT_USERNAME, RECIPIENT_PASSWORD, role="CLI")

    document, _ = IPFSFile.objects.update_or_create(
        cid=FILE_CID,
        defaults={
            "nome_arquivo": FILE_NAME,
            "mime_type": "text/plain",
            "tamanho_arquivo": 128,
            "sha256": "",
            "is_encrypted": False,
            "description": "Documento deterministico para as jornadas E2E do Core.",
            "dono_arquivo": owner,
        },
    )

    document.access_grants.filter(user=recipient).delete()
    document.shared_links.filter(created_by=admin).delete()

    print(
        "Fixture E2E pronta:",
        ADMIN_USERNAME,
        OWNER_USERNAME,
        RECIPIENT_USERNAME,
        document.id,
    )


if __name__ == "__main__":
    main()
