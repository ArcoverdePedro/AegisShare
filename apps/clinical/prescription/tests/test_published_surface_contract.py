from pathlib import Path

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.test import SimpleTestCase
from django.urls import URLPattern

from apps.clinical.prescription.urls import urlpatterns as prescription_urlpatterns
from apps.clinical.prescription.views import NoStoreResponseMixin

PUBLISHED_SURFACES = {
    "drug_catalog": {
        "route": "medicamentos/",
        "browser_denial_path": "/medicamentos/",
        "accessibility_marker": "verifyCatalog(page)",
    },
    "drug_create": {
        "route": "medicamentos/novo/",
        "browser_denial_path": "/medicamentos/novo/",
        "accessibility_marker": "verifyDrugCreateForm(page)",
    },
    "drug_update": {
        "route": "medicamentos/<uuid:pk>/editar/",
        "browser_denial_path": (
            "/medicamentos/00000000-0000-0000-0000-000000000001/editar/"
        ),
        "accessibility_marker": "verifyDrugEditForm(page)",
    },
    "pharmacy_stock": {
        "route": "estoque-farmacia/",
        "browser_denial_path": "/estoque-farmacia/",
        "accessibility_marker": "verifyStock(page)",
    },
}

SERVER_SECURITY_EVIDENCE = (
    "apps/clinical/prescription/tests/test_response_cache_policy.py",
    "apps/clinical/prescription/tests/test_anonymous_boundary.py",
    "apps/clinical/prescription/tests/test_denied_access_audit.py",
)
BROWSER_DENIAL_EVIDENCE = "tests/e2e/prescription_authorization.spec.js"
ACCESSIBILITY_EVIDENCE = "tests/e2e/prescription_accessibility.spec.js"


def _published_patterns():
    return {
        pattern.name: pattern
        for pattern in prescription_urlpatterns
        if isinstance(pattern, URLPattern)
    }


class PublishedRxSurfaceContractTests(SimpleTestCase):
    def test_urlconf_matches_explicit_published_surface_inventory(self):
        patterns = _published_patterns()
        actual = {name: str(pattern.pattern) for name, pattern in patterns.items()}
        expected = {
            name: contract["route"] for name, contract in PUBLISHED_SURFACES.items()
        }

        self.assertEqual(actual, expected)

    def test_every_published_surface_requires_login_and_no_store_response(self):
        patterns = _published_patterns()

        for name in PUBLISHED_SURFACES:
            with self.subTest(surface=name):
                view_class = patterns[name].callback.view_class
                self.assertTrue(issubclass(view_class, LoginRequiredMixin))
                self.assertTrue(issubclass(view_class, NoStoreResponseMixin))

    def test_every_published_surface_is_listed_in_server_security_evidence(self):
        base_dir = Path(settings.BASE_DIR)

        for relative_path in SERVER_SECURITY_EVIDENCE:
            body = (base_dir / relative_path).read_text(encoding="utf-8")
            for name in PUBLISHED_SURFACES:
                with self.subTest(evidence=relative_path, surface=name):
                    self.assertIn(f'prescription:{name}', body)

    def test_every_published_surface_is_listed_in_browser_denial_evidence(self):
        body = (Path(settings.BASE_DIR) / BROWSER_DENIAL_EVIDENCE).read_text(
            encoding="utf-8"
        )

        for name, contract in PUBLISHED_SURFACES.items():
            with self.subTest(surface=name):
                self.assertIn(contract["browser_denial_path"], body)

    def test_every_published_surface_has_accessibility_evidence(self):
        body = (Path(settings.BASE_DIR) / ACCESSIBILITY_EVIDENCE).read_text(
            encoding="utf-8"
        )

        for name, contract in PUBLISHED_SURFACES.items():
            with self.subTest(surface=name):
                self.assertIn(contract["accessibility_marker"], body)
