import logging
from concurrent.futures import ThreadPoolExecutor

from django.db import connection, transaction
from django.urls import reverse

from aegis_share.models import Notification

logger = logging.getLogger(__name__)

# shortcut: pool em memoria do processo; pushes pendentes se perdem se o processo
# reiniciar. Trocar por uma fila de jobs se a entrega precisar ser garantida.
_push_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="webpush")


def _send_webpush(user_id) -> None:
    # Import tardio evita acoplamento do Core ao app PWA durante o carregamento dos apps.
    from apps.pwa.push import send_generic_push

    try:
        send_generic_push(user_id)
    except Exception:
        logger.exception("webpush_background_failed", extra={"user_id": str(user_id)})
    finally:
        connection.close()  # cada thread abre a propria conexao com o banco


def _send_webpush_after_commit(user_id) -> None:
    # Fora da requisicao: um servico de push lento nao trava quem comentou ou compartilhou.
    _push_pool.submit(_send_webpush, user_id)


def notify(user, *, title: str, body: str = "", kind: str = "SYSTEM", link: str = ""):
    if not user:
        return None
    notification = Notification.objects.create(
        user=user,
        title=title,
        body=body,
        kind=kind,
        link=link,
    )
    user_id = user.pk
    transaction.on_commit(lambda: _send_webpush_after_commit(user_id))
    return notification


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
