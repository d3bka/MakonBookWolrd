from pathlib import Path

from django.test import TestCase


class SatPreviewV534StaticContractTests(TestCase):
    def test_v534_uses_satmakon_palette(self):
        root = Path(__file__).resolve().parents[2]
        css = (root / "static" / "assets" / "css" / "sat-preview-v534.css").read_text(encoding="utf-8")

        self.assertIn("#6d28d9", css)
        self.assertIn("#4c1d95", css)
        self.assertIn("#8b5cf6", css)
        self.assertIn("#c084fc", css)

    def test_theme_toggle_icon_is_visually_fixed(self):
        root = Path(__file__).resolve().parents[2]
        css = (root / "static" / "assets" / "css" / "sat-preview-v534.css").read_text(encoding="utf-8")

        self.assertIn('--sat534-primary:', css)
        self.assertIn('.sat531-btn.primary', css)
        self.assertNotIn('.theme-toggle-icon::before', css)
        self.assertNotIn('body.sat531-page .theme-toggle', css)

    def test_exam_like_instruction_copy_is_present(self):
        root = Path(__file__).resolve().parents[2]
        template = (root / "templates" / "test" / "test_modules.html").read_text(encoding="utf-8")

        self.assertIn("Test-day reminders", template)
        self.assertIn("When you select Start, the timer begins", template)
        self.assertIn("Use Mark for Review and the question navigator", template)
        self.assertIn("When a module is submitted or its time expires", template)
