from django.urls import reverse

from aegis_share.models import Notification


def notify(user, *, title: str, body: str = "", kind: str = "SYSTEM", link: str = ""):
    if not user:
        return None
    return Notification.objects.create(
        user=user,
        title=title,
        body=body,
        kind=kind,
        link=link,
    )


def notify_file_shared(file, recipient, actor):
    return notify(
        recipient,
        kind="SHARE",
        title=f"{actor.username} compartilhou um arquivo com voce",
        body=file.nome_arquivo,
        link=reverse("file_detail", args=[file.id]),
    )


def notify_document_request(document_request):
    return notify(
        document_request.recipient,
        kind="REQUEST",
        title="Nova solicitacao de documentos",
        body=document_request.title,
        link=reverse("document_requests"),
    )
