from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.shortcuts import redirect
from django.urls import reverse

from .models import TrackedSession


class FirstAccessRedirectMiddleware:
    """Redireciona apenas enquanto a instalacao ainda nao possui administrador."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.User = get_user_model()
        self.setup_url = reverse("primeiro_cadastro")
        self._configured = False

    def __call__(self, request):
        if not self._configured:
            self._configured = self.User.objects.filter(is_superuser=True).exists()

        current_path = request.path
        bypass = (
            current_path.startswith(self.setup_url)
            or current_path.startswith("/static/")
            or current_path.startswith("/health/")
        )
        if not self._configured and not bypass:
            return redirect(self.setup_url)

        return self.get_response(request)


class TrackedSessionMiddleware:
    """Mantem inventario leve das sessoes autenticadas para revogacao pelo usuario."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            self._track(request)
        return self.get_response(request)

    def _track(self, request):
        if not request.session.session_key:
            request.session.save()
        session_key = request.session.session_key
        throttle_key = f"tracked-session:{session_key}"
        if cache.get(throttle_key):
            return

        TrackedSession.objects.update_or_create(
            session_key=session_key,
            defaults={
                "user": request.user,
                "ip_address": request.META.get("REMOTE_ADDR") or None,
                "user_agent": (request.META.get("HTTP_USER_AGENT") or "")[:1000],
                "revoked_at": None,
            },
        )
        cache.set(throttle_key, True, 300)
