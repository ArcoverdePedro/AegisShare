from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class OpenSourceLicenseContractTests(SimpleTestCase):
    def test_agpl_license_metadata_and_remote_source_offer_stay_aligned(self):
        base_dir = Path(settings.BASE_DIR)
        license_text = (base_dir / "LICENSE").read_text(encoding="utf-8")
        pyproject = (base_dir / "pyproject.toml").read_text(encoding="utf-8")
        shell = (base_dir / "templates" / "navbar" / "navbar.html").read_text(
            encoding="utf-8"
        )

        self.assertTrue(license_text.startswith("GNU AFFERO GENERAL PUBLIC LICENSE"))
        self.assertNotIn("MIT License", license_text)
        self.assertIn('license = "AGPL-3.0-only"', pyproject)
        self.assertIn("AGPL-3.0-only", shell)
        self.assertIn("Código-fonte correspondente", shell)
        self.assertIn("https://github.com/ArcoverdePedro/AegisShare", shell)
