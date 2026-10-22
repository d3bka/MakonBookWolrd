from pathlib import Path
from django.test import TestCase


class SatPreviewV5344ThemeLightTests(TestCase):
    def test_v5344_light_theme_css_is_loaded(self):
        root = Path(__file__).resolve().parents[2]
        template = (root / "templates" / "test" / "test_modules.html").read_text(encoding="utf-8")
        self.assertIn("sat-preview-v5344-theme-light.css", template)

    def test_v5344_defines_light_theme_switcher_variables_for_preview_page(self):
        root = Path(__file__).resolve().parents[2]
        css = (root / "static" / "assets" / "css" / "sat-preview-v5344-theme-light.css").read_text(encoding="utf-8")
        self.assertIn('html[data-theme="light"] body.sat531-page .theme-switcher', css)
        self.assertIn('--theme-switch-menu-bg: rgba(255,255,255,.96);', css)
        self.assertIn('--theme-switch-menu-text: #211337;', css)
        self.assertIn('linear-gradient(135deg, rgba(139,92,246,.95), rgba(236,72,153,.86))', css)
