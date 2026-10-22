from pathlib import Path

from django.test import TestCase


class SatPreviewV533StaticContractTests(TestCase):
    def test_v533_assets_are_loaded(self):
        root = Path(__file__).resolve().parents[2]
        template = (root / "templates" / "test" / "test_modules.html").read_text(encoding="utf-8")

        self.assertIn("sat-preview-v533.css", template)
        self.assertIn("sat-preview-privacy-v533.js", template)
        self.assertIn("One active test at a time", template)

    def test_copy_and_selection_deterrence_is_present(self):
        root = Path(__file__).resolve().parents[2]
        css = (root / "static" / "assets" / "css" / "sat-preview-v533.css").read_text(encoding="utf-8")
        js = (root / "static" / "assets" / "js" / "sat-preview-privacy-v533.js").read_text(encoding="utf-8")

        self.assertIn("user-select: none", css)
        self.assertIn("selectstart", js)
        self.assertIn("document.addEventListener('copy'", js)
        self.assertIn("key === 'c'", js)

    def test_light_theme_switcher_and_vertical_balance_contract(self):
        root = Path(__file__).resolve().parents[2]
        css = (root / "static" / "assets" / "css" / "sat-preview-v533.css").read_text(encoding="utf-8")

        self.assertNotIn("body.sat531-page .theme-toggle", css)
        self.assertNotIn("body.sat531-page .theme-menu", css)
        self.assertIn("justify-content: center", css)
        self.assertIn("min-height: 330px", css)
