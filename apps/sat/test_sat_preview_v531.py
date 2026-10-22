from pathlib import Path

from django.test import TestCase


class SatPreviewV531StaticContractTests(TestCase):
    def test_preview_template_keeps_active_attempt_guard_and_v531_assets(self):
        root = Path(__file__).resolve().parents[2]
        template = (root / "templates" / "test" / "test_modules.html").read_text(encoding="utf-8")

        self.assertIn("One active test at a time", template)
        self.assertIn("blocked_active_attempt", template)
        self.assertIn("blocked_active_url", template)
        self.assertIn("sat-preview-v531.css", template)
        self.assertIn("sat-preview-privacy-v531.js", template)
        self.assertIn("data-preview-watermark", template)

    def test_preview_css_uses_minimal_exam_shell(self):
        root = Path(__file__).resolve().parents[2]
        css = (root / "static" / "assets" / "css" / "sat-preview-v531.css").read_text(encoding="utf-8")

        self.assertIn(".sat531-overview", css)
        self.assertIn(".sat531-module-list", css)
        self.assertIn("@media print", css)
        self.assertIn("overflow: hidden", css)

    def test_preview_privacy_script_contains_deterrence_controls(self):
        root = Path(__file__).resolve().parents[2]
        js = (root / "static" / "assets" / "js" / "sat-preview-privacy-v531.js").read_text(encoding="utf-8")

        self.assertIn("visibilitychange", js)
        self.assertIn("contextmenu", js)
        self.assertIn("printscreen", js)
