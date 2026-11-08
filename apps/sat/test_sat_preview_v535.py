from pathlib import Path
from django.test import TestCase


class SatPreviewV535TypographyTests(TestCase):
    def test_v535_typography_css_is_loaded(self):
        root = Path(__file__).resolve().parents[2]
        template = (root / "templates" / "test" / "test_modules.html").read_text(encoding="utf-8")
        self.assertIn("sat-preview-v535-typography.css", template)

    def test_v535_increases_exam_copy_density(self):
        root = Path(__file__).resolve().parents[2]
        css = (root / "static" / "assets" / "css" / "sat-preview-v535-typography.css").read_text(encoding="utf-8")
        self.assertIn("font-size: 13px", css)
        self.assertIn(".sat531-exam-note li", css)
        self.assertIn("font-size: 12px", css)
        self.assertIn(".sat-retake-guard-copy strong", css)
        self.assertIn("font-size: 16px", css)
