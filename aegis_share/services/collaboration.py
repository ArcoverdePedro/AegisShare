from aegis_share.models import CustomUser


def file_chat_users(file, current_user):
    """Retorna usuarios relevantes e autorizados para conversar sobre um arquivo."""
    candidates = CustomUser.objects.filter(is_active=True).exclude(id=current_user.id)

    ids = {file.dono_arquivo_id}
    ids.update(file.access_grants.values_list("user_id", flat=True))

    if file.workspace_id:
        ids.add(file.workspace.cliente_id)
        ids.update(file.workspace.members.values_list("id", flat=True))

    if current_user.is_admin():
        ids.update(
            CustomUser.objects.filter(nivel_permissao="ADM", is_active=True)
            .exclude(id=current_user.id)
            .values_list("id", flat=True)
        )

    return candidates.filter(id__in=ids).distinct().order_by("username")
