from io import BytesIO

from django.contrib.auth.views import LogoutView
from django.contrib.staticfiles import finders
from django.http import Http404, HttpResponse, JsonResponse
from django.urls import reverse
from django.views.generic import TemplateView, View
from PIL import Image, ImageOps

PWA_ICON_SIZES = {192, 512}


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


class PwaLogoutView(LogoutView):
    """Limpa dados locais do PWA ao encerrar a sessão em navegadores compatíveis."""

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        response["Clear-Site-Data"] = '"cache", "storage"'
        response["Cache-Control"] = "no-store"
        return response
