#!/usr/bin/env python3
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

import django

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

PROFESSIONAL_USERNAME = "ci-pep-professional"
PROFESSIONAL_PASSWORD = "ci-pep-professional-password"
OUTSIDER_USERNAME = "ci-pep-outsider"
OUTSIDER_PASSWORD = "ci-pep-outsider-password"


def configure_user(username, password):
    User = get_user_model()
    user, _ = User.objects.get_or_create(username=username)
    user.email = f"{username}@example.invalid"
    user.nivel_permissao = "FUNC"
    user.is_active = True
    user.is_staff = False
    user.is_superuser = False
    user.set_password(password)
    user.save()
    return user


def main():
    professional = configure_user(PROFESSIONAL_USERNAME, PROFESSIONAL_PASSWORD)
    outsider = configure_user(OUTSIDER_USERNAME, OUTSIDER_PASSWORD)
    print("Usuários E2E PEP prontos:", professional.username, outsider.username)


if __name__ == "__main__":
    main()
