from django.db.models import Q

from aegis_share.models import IPFSFile, Workspace


def files_for_user(user, *, include_deleted=False):
    qs = (
        IPFSFile.objects.select_related("dono_arquivo", "workspace", "folder")
        .prefetch_related("tags", "usuarios_permitidos")
    )

    if not include_deleted:
        qs = qs.filter(deleted_at__isnull=True)

    if user.is_admin():
        return qs.distinct().order_by("-data_adicionado")

    workspace_ids = Workspace.objects.filter(
        Q(cliente=user) | Q(members=user)
    ).values_list("id", flat=True)

    return (
        qs.filter(
            Q(dono_arquivo=user)
            | Q(usuarios_permitidos=user)
            | Q(workspace_id__in=workspace_ids)
        )
        .distinct()
        .order_by("-data_adicionado")
    )


def get_accessible_file(user, file_id, *, include_deleted=False):
    qs = files_for_user(user, include_deleted=include_deleted)
    return qs.filter(id=file_id).first()
