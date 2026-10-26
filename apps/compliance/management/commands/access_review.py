import csv
import sys

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import BaseCommand
from django.utils import timezone

from aegis_share.models import FileAccess
from apps.clinical.adt.models import UserLocationAccess
from apps.clinical.pep.models import PatientAccessGrant

HEADER = [
    "usuario",
    "ativo",
    "papel",
    "tipo",
    "objeto",
    "concedido_por",
    "concedido_em",
    "expira_em",
]


def access_rows(*, include_expired=False):
    """Concessoes vigentes por usuario para revisao periodica; so IDs, sem nome de paciente."""
    now = timezone.now()
    grants = PatientAccessGrant.objects.select_related("user", "granted_by")
    if not include_expired:
        grants = grants.exclude(expires_at__lte=now)
    for grant in grants.order_by("user__username", "created_at").iterator():
        yield (
            grant.user,
            "PACIENTE",
            grant.patient_id,
            grant.granted_by,
            grant.created_at,
            grant.expires_at,
        )
    for access in UserLocationAccess.objects.select_related("user", "granted_by", "location"):
        yield (
            access.user,
            "UNIDADE_ADT",
            access.location.code,
            access.granted_by,
            access.created_at,
            None,
        )
    for access in FileAccess.objects.select_related("user", "granted_by").iterator():
        yield (
            access.user,
            "ARQUIVO",
            access.arquivo_id,
            access.granted_by,
            access.data_compartilhado,
            None,
        )
    User = get_user_model()
    direct = Permission.objects.filter(user__isnull=False).values_list(
        "user", "content_type__app_label", "codename"
    )
    by_group = Permission.objects.filter(group__user__isnull=False).values_list(
        "group__user", "content_type__app_label", "codename"
    )
    users = {u.pk: u for u in User.objects.all()}
    for user_id, app, codename in sorted(
        {*direct, *by_group}, key=lambda row: (str(row[0]), row[1], row[2])
    ):
        yield users[user_id], "PERMISSAO", f"{app}.{codename}", None, None, None
    for user in User.objects.filter(is_superuser=True):
        yield user, "SUPERUSUARIO", "*", None, None, None


class Command(BaseCommand):
    help = "Exporta concessoes de acesso (CSV) para revisao periodica; nao altera nada."

    def add_arguments(self, parser):
        parser.add_argument("--include-expired", action="store_true")

    def handle(self, *args, **options):
        writer = csv.writer(sys.stdout)
        writer.writerow(HEADER)
        for user, kind, obj, granted_by, granted_at, expires_at in access_rows(
            include_expired=options["include_expired"]
        ):
            writer.writerow(
                [
                    user.username,
                    "sim" if user.is_active else "nao",
                    user.nivel_permissao,
                    kind,
                    obj,
                    getattr(granted_by, "username", ""),
                    granted_at.isoformat() if granted_at else "",
                    expires_at.isoformat() if expires_at else "",
                ]
            )
