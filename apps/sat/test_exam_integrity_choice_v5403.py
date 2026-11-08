from pathlib import Path
from django.test import TestCase


class ExamIntegrityChoiceV5403Tests(TestCase):
    def test_pretest_config_exposes_off_standard_strict_selector(self):
        root = Path(__file__).resolve().parents[2]
        js = (root / "static" / "assets" / "js" / "makon-test-config-v550.js").read_text(encoding="utf-8")

        self.assertIn("this.integrityModes", js)
        self.assertIn("{ id:'off', title:'Off'", js)
        self.assertIn("{ id:'standard', title:'Standard'", js)
        self.assertIn("{ id:'strict', title:'Strict'", js)
        self.assertIn("Exam Integrity", js)

    def test_cover_shows_selected_integrity_and_lock_state(self):
        root = Path(__file__).resolve().parents[2]
        template = (root / "templates" / "test" / "test_modules.html").read_text(encoding="utf-8")

        self.assertIn("sat5417-integrity", template)
        self.assertIn("selected_integrity_mode", template)
        self.assertIn("selected_integrity_locked", template)
        self.assertIn("Managed by teacher", template)
        self.assertIn("Locks on start", template)
        self.assertNotIn("data-integrity-picker", template)

    def test_off_mode_disables_fullscreen_and_is_persisted_for_independent_practice(self):
        root = Path(__file__).resolve().parents[2]
        js = (root / "static" / "assets" / "js" / "makon-test-config-v550.js").read_text(encoding="utf-8")

        self.assertIn("makonbook:practice-integrity-mode", js)
        self.assertIn("this.state.integrity!=='off'", js)
        self.assertIn("url.searchParams.set('integrity_mode',this.state.integrity)", js)
        self.assertIn("url.searchParams.set('integrity_fullscreen_required'", js)
