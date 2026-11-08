from pathlib import Path
from django.test import TestCase


class ExamIntegrityOverviewV5402Tests(TestCase):
    def test_cover_shows_read_only_integrity_summary(self):
        root = Path(__file__).resolve().parents[2]
        template = (root / "templates" / "test" / "test_modules.html").read_text(encoding="utf-8")
        self.assertIn("sat5417-integrity", template)
        self.assertIn("selected_integrity_mode", template)
        self.assertIn("selected_integrity_locked", template)
        self.assertIn("Exam Integrity", template)
        self.assertIn("Locks on start", template)

    def test_integrity_picker_lives_in_pretest_config_not_cover(self):
        root = Path(__file__).resolve().parents[2]
        template = (root / "templates" / "test" / "test_modules.html").read_text(encoding="utf-8")
        js = (root / "static" / "assets" / "js" / "makon-test-config-v550.js").read_text(encoding="utf-8")
        self.assertNotIn("data-integrity-picker", template)
        self.assertIn("ptc-integrity-card", js)
        self.assertIn("data-integrity", js)
        self.assertIn("Managed by teacher", js)
