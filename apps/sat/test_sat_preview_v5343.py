from pathlib import Path

from django.test import TestCase


class SatPreviewV5343ThemeRestoreTests(TestCase):
    def test_preview_uses_global_theme_switcher_without_experimental_overrides(self):
        root = Path(__file__).resolve().parents[2]
        template = (root / "templates" / "test" / "test_modules.html").read_text(encoding="utf-8")

        self.assertIn("makon-theme-switcher.css", template)
        self.assertIn("makon-theme-switcher.js", template)
        self.assertNotIn("sat-preview-v5341-icon.css", template)
        self.assertNotIn("sat-preview-v5342-theme.css", template)

    def test_v533_no_longer_overrides_theme_switcher(self):
        root = Path(__file__).resolve().parents[2]
        css = (root / "static" / "assets" / "css" / "sat-preview-v533.css").read_text(encoding="utf-8")

        self.assertNotIn("Light theme switcher", css)
        self.assertNotIn("body.sat531-page .theme-toggle", css)

    def test_v534_no_longer_overrides_theme_switcher(self):
        root = Path(__file__).resolve().parents[2]
        css = (root / "static" / "assets" / "css" / "sat-preview-v534.css").read_text(encoding="utf-8")

        self.assertNotIn("Theme toggle:", css)
        self.assertNotIn(".theme-toggle-icon::before", css)
