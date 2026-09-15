import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

SCENARIO_TITLE = "papel CLI permanece negado nas superfícies RX mesmo com permissões mal atribuídas"


def _read_repo_file(relative_path):
    return (Path(settings.BASE_DIR) / relative_path).read_text(encoding="utf-8")


def _gherkin_example_routes(body):
    return set(
        re.findall(
            r"^\s*\|\s*(/[^|]+?)\s*\|\s*$",
            body,
            flags=re.MULTILINE,
        )
    )


def _playwright_denied_routes(body):
    return set(re.findall(r"expectForbidden\(page,\s*'([^']+)'\)", body))


class PrescriptionAcceptanceTraceabilityTests(SimpleTestCase):
    def test_denial_scenario_title_is_shared_by_gherkin_and_playwright(self):
        feature = _read_repo_file(
            "specs/003-prescricao-farmacia/features/authorization.feature"
        )
        playwright = _read_repo_file("tests/e2e/prescription_authorization.spec.js")

        self.assertIn(f"Esquema do Cenário: {SCENARIO_TITLE}", feature)
        self.assertIn(f"test('{SCENARIO_TITLE}'", playwright)

    def test_denial_gherkin_routes_match_playwright_exactly(self):
        feature = _read_repo_file(
            "specs/003-prescricao-farmacia/features/authorization.feature"
        )
        playwright = _read_repo_file("tests/e2e/prescription_authorization.spec.js")

        feature_routes = _gherkin_example_routes(feature)
        playwright_routes = _playwright_denied_routes(playwright)

        self.assertTrue(feature_routes)
        self.assertEqual(feature_routes, playwright_routes)
        self.assertIn("Então a resposta HTTP é 403", feature)
        self.assertIn(".toBe(403)", playwright)
