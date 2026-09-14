import json
from io import BytesIO
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LogoutView
from django.contrib.staticfiles import finders
from django.http import Http404, HttpResponse, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView, View
from PIL import Image, ImageOps

from .models import PushSubscription

PWA_ICON_SIZES = {192, 512}
MAX_PUSH_ENDPOINT_LENGTH = 4096
MAX_PUSH_KEY_LENGTH = 1024


def _no_store(response):
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _read_json_object(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _valid_subscription_payload(payload):
    if payload is None:
        return None

    endpoint = payload.get("endpoint")
    keys = payload.get("keys")
    if not isinstance(endpoint, str) or not isinstance(keys, dict):
        return None

    endpoint = endpoint.strip()
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")
    if not isinstance(p256dh, str) or not isinstance(auth, str):
        return None
    p256dh = p256dh.strip()
    auth = auth.strip()

    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    if not endpoint or len(endpoint) > MAX_PUSH_ENDPOINT_LENGTH:
        return None
    if not p256dh or len(p256dh) > MAX_PUSH_KEY_LENGTH:
        return None
    if not auth or len(auth) > MAX_PUSH_KEY_LENGTH:
        return None
    return endpoint, p256dh, auth


def _session_fingerprint(request):
    session_key = request.session.session_key
    if not session_key:
        request.session.save()
        session_key = request.session.session_key
    if not session_key:
        return None
    return PushSubscription.hash_session_key(session_key)


class ManifestView(View):
    def get(self, request, *args, **kwargs):
        response = JsonResponse(
            {
                "name": "AegisShare HIS",
                "short_name": "AegisShare",
                "description": "Sistema Hospitalar Interno",
                "start_url": "/",
                "scope": "/",
                "display": "standalone",
                "orientation": "portrait",
                "background_color": "#f5f7fb",
                "theme_color": "#363636",
                "icons": [
                    {
                        "src": reverse("pwa:icon", kwargs={"size": 192}),
                        "sizes": "192x192",
                        "type": "image/png",
                        "purpose": "any maskable",
                    },
                    {
                        "src": reverse("pwa:icon", kwargs={"size": 512}),
                        "sizes": "512x512",
                        "type": "image/png",
                        "purpose": "any maskable",
                    },
                ],
            },
            content_type="application/manifest+json",
        )
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response


class PwaIconView(View):
    """Serve os tamanhos exigidos pelo manifest a partir do favicon versionado."""

    def get(self, request, size, *args, **kwargs):
        if size not in PWA_ICON_SIZES:
            raise Http404

        source = finders.find("images/favicon.ico")
        if not source:
            raise Http404

        with Image.open(source) as original:
            icon = ImageOps.fit(
                original.convert("RGBA"),
                (size, size),
                method=Image.Resampling.LANCZOS,
            )
            payload = BytesIO()
            icon.save(payload, format="PNG", optimize=True)

        response = HttpResponse(payload.getvalue(), content_type="image/png")
        response["Cache-Control"] = "public, max-age=31536000, immutable"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class ServiceWorkerView(TemplateView):
    template_name = "pwa/service-worker.js"
    content_type = "application/javascript"

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        response["Service-Worker-Allowed"] = "/"
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response


class OfflineView(TemplateView):
    template_name = "pwa/offline.html"

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        response["Cache-Control"] = "no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class PushConfigView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        response = JsonResponse(
            {
                "enabled": settings.WEBPUSH_ENABLED,
                "public_key": (
                    settings.WEBPUSH_VAPID_PUBLIC_KEY if settings.WEBPUSH_ENABLED else ""
                ),
            }
        )
        return _no_store(response)


class PushSubscribeView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        if not settings.WEBPUSH_ENABLED:
            return _no_store(
                JsonResponse({"error": "webpush_not_configured"}, status=503)
            )

        parsed = _valid_subscription_payload(_read_json_object(request))
        if parsed is None:
            return _no_store(
                JsonResponse({"error": "invalid_subscription"}, status=400)
            )

        session_fingerprint = _session_fingerprint(request)
        if not session_fingerprint:
            return _no_store(JsonResponse({"error": "invalid_session"}, status=409))

        endpoint, p256dh, auth = parsed
        endpoint_hash = PushSubscription.hash_endpoint(endpoint)
        subscription, created = PushSubscription.objects.update_or_create(
            endpoint_hash=endpoint_hash,
            defaults={
                "user": request.user,
                "endpoint": endpoint,
                "session_fingerprint": session_fingerprint,
                "p256dh": p256dh,
                "auth": auth,
                "active": True,
                "failure_count": 0,
                "disabled_at": None,
            },
        )
        return _no_store(
            JsonResponse(
                {"subscribed": True, "subscription_id": subscription.pk},
                status=201 if created else 200,
            )
        )


class PushUnsubscribeView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        payload = _read_json_object(request)
        endpoint = payload.get("endpoint") if payload else None
        if not isinstance(endpoint, str) or not endpoint.strip():
            return _no_store(JsonResponse({"error": "invalid_endpoint"}, status=400))

        endpoint_hash = PushSubscription.hash_endpoint(endpoint.strip())
        now = timezone.now()
        PushSubscription.objects.filter(
            user=request.user,
            endpoint_hash=endpoint_hash,
            active=True,
        ).update(active=False, disabled_at=now, updated_at=now)
        return _no_store(JsonResponse({"subscribed": False}))


class PwaLogoutView(LogoutView):
    """Revoga Push da sessão atual e limpa dados locais ao encerrar a sessão."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.session.session_key:
            now = timezone.now()
            fingerprint = PushSubscription.hash_session_key(request.session.session_key)
            PushSubscription.objects.filter(
                user=request.user,
                session_fingerprint=fingerprint,
                active=True,
            ).update(active=False, disabled_at=now, updated_at=now)

        response = super().dispatch(request, *args, **kwargs)
        response["Clear-Site-Data"] = '"cache", "storage"'
        response["Cache-Control"] = "no-store"
        return response
