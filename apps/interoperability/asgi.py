from django.urls import reverse

from .lab_inbox import MAX_BODY_BYTES


class InboxBodyTooLarge(Exception):
    pass


async def bounded_inbox(app, scope, receive, send):
    """Limita a entrada antes do spool de corpo do Django ASGI."""
    if (
        scope.get("path") != reverse("interoperability:lab_inbox_receive")
        or scope.get("method") != "POST"
    ):
        return await app(scope, receive, send)
    total = 0

    async def limited_receive():
        nonlocal total
        message = await receive()
        total += len(message.get("body", b""))
        if total > MAX_BODY_BYTES:
            raise InboxBodyTooLarge
        return message

    try:
        return await app(scope, limited_receive, send)
    except InboxBodyTooLarge:
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"cache-control", b"private, no-store"),
                    (b"vary", b"Cookie"),
                    (b"x-content-type-options", b"nosniff"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": b"Upload excede o limite."})
