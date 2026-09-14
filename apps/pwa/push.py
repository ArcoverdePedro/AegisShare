import logging

from django.conf import settings
from django.db.models import F
from django.utils import timezone
from pywebpush import WebPushException, webpush

from .models import PushSubscription

logger = logging.getLogger(__name__)

GENERIC_PUSH_TTL_SECONDS = 300
EXPIRED_SUBSCRIPTION_STATUS_CODES = {404, 410}


def webpush_is_configured() -> bool:
    return bool(getattr(settings, "WEBPUSH_ENABLED", False))


def _status_code_from_exception(exc: WebPushException) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if status_code is not None:
        return status_code
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None)


def send_generic_push(user_id) -> dict[str, int | bool]:
    """Envia somente um sinal genérico; título/corpo clínico nunca saem do servidor."""

    if not webpush_is_configured():
        return {"configured": False, "sent": 0, "failed": 0, "disabled": 0}

    sent = 0
    failed = 0
    disabled = 0
    subscriptions = PushSubscription.objects.filter(user_id=user_id, active=True).only(
        "id",
        "endpoint",
        "p256dh",
        "auth",
    )

    for subscription in subscriptions:
        try:
            webpush(
                subscription_info=subscription.subscription_info(),
                data=None,
                vapid_private_key=settings.WEBPUSH_VAPID_PRIVATE_KEY,
                vapid_claims={"sub": settings.WEBPUSH_VAPID_SUBJECT},
                ttl=GENERIC_PUSH_TTL_SECONDS,
                timeout=settings.WEBPUSH_SEND_TIMEOUT_SECONDS,
            )
        except WebPushException as exc:
            failed += 1
            status_code = _status_code_from_exception(exc)
            if status_code in EXPIRED_SUBSCRIPTION_STATUS_CODES:
                PushSubscription.objects.filter(pk=subscription.pk).update(
                    active=False,
                    disabled_at=timezone.now(),
                    updated_at=timezone.now(),
                )
                disabled += 1
            else:
                PushSubscription.objects.filter(pk=subscription.pk).update(
                    failure_count=F("failure_count") + 1,
                    updated_at=timezone.now(),
                )
            logger.warning(
                "webpush_delivery_failed",
                extra={
                    "subscription_id": subscription.pk,
                    "status_code": status_code,
                },
            )
        except Exception:
            failed += 1
            PushSubscription.objects.filter(pk=subscription.pk).update(
                failure_count=F("failure_count") + 1,
                updated_at=timezone.now(),
            )
            logger.exception(
                "webpush_delivery_error",
                extra={"subscription_id": subscription.pk},
            )
        else:
            PushSubscription.objects.filter(pk=subscription.pk).update(
                failure_count=0,
                last_success_at=timezone.now(),
                updated_at=timezone.now(),
            )
            sent += 1

    return {
        "configured": True,
        "sent": sent,
        "failed": failed,
        "disabled": disabled,
    }
