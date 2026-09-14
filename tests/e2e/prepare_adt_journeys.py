#!/usr/bin/env python3
import os
from datetime import timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.models import Permission  # noqa: E402
from django.utils import timezone  # noqa: E402

from apps.clinical.adt.models import (  # noqa: E402
    Admission,
    Bed,
    BedOccupancy,
    Location,
    UserLocationAccess,
)
from apps.clinical.pep.models import Encounter, Patient  # noqa: E402

OPERATOR_USERNAME = "ci-adt-operator"
OPERATOR_PASSWORD = "ci-adt-operator-password"
OUTSIDER_USERNAME = "ci-adt-outsider"
OUTSIDER_PASSWORD = "ci-adt-outsider-password"
MASKED_USERNAME = "ci-adt-masked-viewer"
MASKED_PASSWORD = "ci-adt-masked-viewer-password"
SETUP_ADMIN_USERNAME = "ci-adt-setup-admin"


def configure_user(username, password, *, superuser=False):
    User = get_user_model()
    user, _ = User.objects.get_or_create(username=username)
    user.email = f"{username}@example.invalid"
    user.nivel_permissao = "ADM" if superuser else "FUNC"
    user.is_active = True
    user.is_staff = superuser
    user.is_superuser = superuser
    user.set_password(password)
    user.save()
    return user


def add_adt_permissions(user, *codenames):
    permissions = Permission.objects.filter(
        content_type__app_label="adt",
        codename__in=codenames,
    )
    found = set(permissions.values_list("codename", flat=True))
    missing = set(codenames) - found
    if missing:
        raise RuntimeError(f"Permissões ADT ausentes: {sorted(missing)}")
    user.user_permissions.add(*permissions)


def create_patient_and_encounter(*, owner, identifier, name):
    patient, _ = Patient.objects.get_or_create(
        identifier_type=Patient.IdentifierType.OTHER,
        identifier=identifier,
        defaults={
            "full_name": name,
            "birth_date": timezone.localdate() - timedelta(days=365 * 38),
            "sex": "F",
            "created_by": owner,
        },
    )
    encounter, _ = Encounter.objects.get_or_create(
        patient=patient,
        defaults={
            "encounter_type": Encounter.Type.INPATIENT,
            "status": Encounter.Status.OPEN,
            "started_at": timezone.now() - timedelta(hours=8),
            "location": "Unidade ADT E2E",
            "reason": "Internação sintética para jornada E2E.",
            "responsible_professional": owner,
            "created_by": owner,
        },
    )
    return patient, encounter


def main():
    setup_admin = configure_user(
        SETUP_ADMIN_USERNAME,
        "ci-adt-setup-admin-password",
        superuser=True,
    )
    operator = configure_user(OPERATOR_USERNAME, OPERATOR_PASSWORD)
    outsider = configure_user(OUTSIDER_USERNAME, OUTSIDER_PASSWORD)
    masked = configure_user(MASKED_USERNAME, MASKED_PASSWORD)

    operator.user_permissions.clear()
    outsider.user_permissions.clear()
    masked.user_permissions.clear()
    add_adt_permissions(
        operator,
        "view_admission",
        "view_bed_map",
        "admit_patient",
        "transfer_patient",
        "discharge_patient",
        "view_movement_history",
    )
    add_adt_permissions(masked, "view_bed_map")

    location, _ = Location.objects.get_or_create(
        code="E2E-ADT",
        defaults={"name": "Unidade ADT E2E", "kind": Location.Kind.WARD},
    )
    UserLocationAccess.objects.get_or_create(
        user=operator,
        location=location,
        defaults={"granted_by": setup_admin},
    )
    UserLocationAccess.objects.get_or_create(
        user=masked,
        location=location,
        defaults={"granted_by": setup_admin},
    )

    # Dois conjuntos tornam retry do Playwright independente do estado alterado
    # pela primeira tentativa da jornada completa.
    for retry in range(2):
        patient, _encounter = create_patient_and_encounter(
            owner=operator,
            identifier=f"E2E-ADT-JOURNEY-R{retry}",
            name=f"Paciente ADT Jornada R{retry}",
        )
        for suffix in ("A", "B"):
            Bed.objects.get_or_create(
                location=location,
                code=f"E2E-J{retry}-{suffix}",
                defaults={"label": f"E2E Jornada R{retry} {suffix}"},
            )
        if hasattr(patient, "full_name"):
            # A variável é usada apenas para deixar explícito que o paciente existe
            # antes da seleção server-side do Encounter.
            pass

    masked_patient, masked_encounter = create_patient_and_encounter(
        owner=setup_admin,
        identifier="E2E-ADT-MASKED-PATIENT",
        name="Paciente ADT Sigiloso E2E",
    )
    masked_bed, _ = Bed.objects.get_or_create(
        location=location,
        code="E2E-MASK-01",
        defaults={"label": "E2E Leito Sigiloso"},
    )
    masked_admission, _ = Admission.objects.get_or_create(
        encounter=masked_encounter,
        defaults={
            "admitted_at": timezone.now() - timedelta(hours=2),
            "admitted_by": setup_admin,
        },
    )
    BedOccupancy.objects.get_or_create(
        admission=masked_admission,
        bed=masked_bed,
        ended_at=None,
        defaults={
            "started_at": masked_admission.admitted_at,
            "started_by": setup_admin,
        },
    )

    print(
        "Dados E2E ADT prontos:",
        operator.username,
        outsider.username,
        masked.username,
        location.code,
        masked_patient.identifier,
    )


if __name__ == "__main__":
    main()
