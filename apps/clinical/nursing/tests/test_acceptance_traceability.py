from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

VITALS_SCENARIOS = (
    "registrar sinais vitais em encontro aberto",
    "enfileirar sinais vitais durante perda de conexão",
    "retry offline não duplica sinais vitais",
    "encontro encerrado antes do sync gera conflito",
)
ADMINISTRATION_SCENARIOS = (
    "administrar medicamento online preserva lote e prescrição",
    "administração não funciona offline",
)


def _read_repo_file(relative_path):
    return (Path(settings.BASE_DIR) / relative_path).read_text(encoding="utf-8")


class NursingAcceptanceTraceabilityTests(SimpleTestCase):
    def test_vitals_scenario_titles_are_shared_by_gherkin_and_playwright(self):
        feature = _read_repo_file("specs/004-enfermagem/features/acceptance.feature")
        playwright = _read_repo_file("tests/e2e/nursing_offline.spec.js")

        for title in VITALS_SCENARIOS:
            with self.subTest(title=title):
                self.assertIn(f"Cenário: {title}", feature)
                self.assertIn(f"test('{title}'", playwright)

    def test_administration_scenario_titles_are_shared_by_gherkin_and_playwright(self):
        feature = _read_repo_file("specs/004-enfermagem/features/acceptance.feature")
        playwright = _read_repo_file(
            "tests/e2e/nursing_medication_administration.spec.js"
        )

        for title in ADMINISTRATION_SCENARIOS:
            with self.subTest(title=title):
                self.assertIn(f"Cenário: {title}", feature)
                self.assertIn(f"test('{title}'", playwright)

    def test_administration_offline_scenario_proves_network_failure_and_no_queue(self):
        playwright = _read_repo_file(
            "tests/e2e/nursing_medication_administration.spec.js"
        )

        self.assertIn("context.setOffline(true)", playwright)
        self.assertIn("page.waitForEvent('requestfailed'", playwright)
        self.assertIn("typeof window.AegisOfflineQueue", playwright)
        self.assertIn("offlineStorageSnapshot(page)", playwright)
        self.assertIn("not.toContain('nursing.medication')", playwright)
