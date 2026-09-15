from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.urls import URLPattern, URLResolver, reverse

from apps.clinical.prescription.urls import urlpatterns as prescription_urlpatterns

from .surface_contract import (
    RX_GET_SURFACE_NAMES,
    RX_NON_GET_SURFACE_NAMES,
    RX_REVIEWED_SURFACE_NAMES,
)

FORBIDDEN_OFFLINE_TOKENS = (
    "AegisOfflineQueue",
    "offline_queue.js",
    "indexedDB",
    "caches.open(",
    "caches.put(",
)


def _collect_routes(patterns, prefix=""):
    routes = set()
    for entry in patterns:
        route = f"{prefix}{entry.pattern}"
        if isinstance(entry, URLResolver):
            routes.update(_collect_routes(entry.url_patterns, route))
        elif isinstance(entry, URLPattern):
            routes.add(route)
    return routes


def _collect_named_routes(patterns):
    names = set()
    for entry in patterns:
        if isinstance(entry, URLResolver):
            names.update(_collect_named_routes(entry.url_patterns))
        elif isinstance(entry, URLPattern) and entry.name:
            names.add(entry.name)
    return names


class PrescriptionArchitectureBoundaryTests(TestCase):
    def test_prescription_urlconf_exposes_no_api_routes(self):
        routes = _collect_routes(prescription_urlpatterns)

        self.assertTrue(routes)
        self.assertFalse(any(route.startswith("api/") for route in routes))

    def test_every_published_rx_route_requires_explicit_security_review(self):
        published_names = _collect_named_routes(prescription_urlpatterns)

        self.assertTrue(published_names)
        self.assertFalse(RX_GET_SURFACE_NAMES & RX_NON_GET_SURFACE_NAMES)
        self.assertEqual(
            published_names,
            RX_REVIEWED_SURFACE_NAMES,
            msg=(
                "Toda nova rota RX deve ser classificada em surface_contract.py antes de "
                "ser publicada, para revisão explícita de cache/PWA/auditoria."
            ),
        )

    def test_prescription_runtime_does_not_opt_into_offline_queue_or_cache(self):
        base_dir = Path(settings.BASE_DIR)
        sources = []

        app_dir = base_dir / "apps" / "clinical" / "prescription"
        for path in app_dir.glob("*.py"):
            if path.name.startswith("test_"):
                continue
            sources.append(path)

        template_dir = base_dir / "templates" / "clinical" / "prescription"
        sources.extend(template_dir.glob("*.html"))

        self.assertTrue(sources)
        for path in sources:
            body = path.read_text(encoding="utf-8")
            for token in FORBIDDEN_OFFLINE_TOKENS:
                with self.subTest(path=str(path), token=token):
                    self.assertNotIn(token, body)

    def test_service_worker_keeps_non_get_requests_outside_cache_pipeline(self):
        response = self.client.get(reverse("pwa:service_worker"))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("if (request.method !== 'GET') return;", body)
        self.assertIn("fetch(request, { cache: 'no-store' })", body)
        self.assertNotIn("/prescricoes/", body)
        self.assertNotIn("/medicamentos/", body)
        self.assertNotIn("/dispensar/", body)
        self.assertNotIn("AegisOfflineQueue", body)

    def test_prescription_pages_are_not_precached_by_service_worker(self):
        response = self.client.get(reverse("pwa:service_worker"))

        body = response.content.decode()
        precache = body.split("const PRECACHE_URLS = [", 1)[1].split("];", 1)[0]
        self.assertNotIn("prescri", precache.lower())
        self.assertNotIn("medic", precache.lower())
        self.assertNotIn("farm", precache.lower())
