import hashlib

from django.conf import settings
from django.db import models
from django.utils import timezone

from .session import hash_session_key


class PushSubscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    endpoint = models.TextField()
    endpoint_hash = models.CharField(max_length=64, unique=True, editable=False)
    session_fingerprint = models.CharField(max_length=64, db_index=True, editable=False)
    p256dh = models.TextField()
    auth = models.TextField()
    active = models.BooleanField(default=True, db_index=True)
    failure_count = models.PositiveIntegerField(default=0)
    last_success_at = models.DateTimeField(null=True, blank=True)
    disabled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "active"], name="pwa_push_user_active_idx"),
        ]

    @staticmethod
    def hash_endpoint(endpoint: str) -> str:
        return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()

    @staticmethod
    def hash_session_key(session_key: str) -> str:
        return hash_session_key(session_key)

    def save(self, *args, **kwargs):
        self.endpoint_hash = self.hash_endpoint(self.endpoint)
        super().save(*args, **kwargs)

    def disable(self) -> None:
        if not self.active and self.disabled_at:
            return
        self.active = False
        self.disabled_at = timezone.now()
        self.save(update_fields=["active", "disabled_at", "updated_at"])

    def subscription_info(self) -> dict[str, object]:
        return {
            "endpoint": self.endpoint,
            "keys": {
                "p256dh": self.p256dh,
                "auth": self.auth,
            },
        }

    def __str__(self):
        return f"PushSubscription<{self.pk}:{self.user_id}>"
