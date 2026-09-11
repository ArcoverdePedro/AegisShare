from django.http import JsonResponse
from django.templatetags.static import static
from django.views.generic import TemplateView, View


class ManifestView(View):
    def get(self, request, *args, **kwargs):
        response = JsonResponse(
            {
                "name": "AegisShare HIS",
                "short_name": "AegisShare",
                "description": "AegisShare — sistema interno de informação em saúde.",
                "start_url": "/",
                "scope": "/",
                "display": "standalone",
                "background_color": "#f5f7fb",
                "theme_color": "#363636",
                "icons": [
                    {
                        "src": static("images/pwa-icon-192.png"),
                        "sizes": "192x192",
                        "type": "image/png",
                        "purpose": "any maskable",
                    },
                    {
                        "src": static("images/pwa-icon-512.png"),
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
