from pathlib import Path

from django.test import TestCase


class SatPreviewV532StaticContractTests(TestCase):
    def test_module_detail_list_is_removed_but_active_attempt_guard_stays(self):
        root = Path(__file__).resolve().parents[2]
        template = (root / "templates" / "test" / "test_modules.html").read_text(encoding="utf-8")

        self.assertIn("One active test at a time", template)
        self.assertIn("blocked_active_attempt", template)
        self.assertNotIn('class="sat531-structure"', template)
        self.assertNotIn('class="sat531-module-list"', template)

    def test_summary_keeps_only_questions_and_time(self):
        root = Path(__file__).resolve().parents[2]
        template = (root / "templates" / "test" / "test_modules.html").read_text(encoding="utf-8")

        self.assertIn("Questions", template)
        self.assertIn("Approx. time", template)
        self.assertNotIn("<span>Modules</span>", template)

    def test_v532_restores_purple_makonbook_buttons(self):
        root = Path(__file__).resolve().parents[2]
        css = (root / "static" / "assets" / "css" / "sat-preview-v532.css").read_text(encoding="utf-8")

        self.assertIn("linear-gradient(100deg, #7c3aed", css)
        self.assertIn(".sat531-btn.primary", css)
        self.assertIn(".sat-retake-guard-action", css)
