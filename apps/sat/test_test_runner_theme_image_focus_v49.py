from pathlib import Path

from unittest import TestCase


ROOT = Path(__file__).resolve().parents[2]
ENG_TEMPLATE = ROOT / "templates/test/shared/attempt_eng.html"
MATH_TEMPLATE = ROOT / "templates/test/shared/attempt_math.html"
FOCUS_CSS = ROOT / "static/assets/css/sat-image-focus-v49.css"
FOCUS_JS = ROOT / "static/assets/js/sat-image-focus-v49.js"


class TestRunnerThemeImageFocusV49Tests(TestCase):
    def _template(self, path):
        return path.read_text(encoding="utf-8")

    def test_test_runner_bootstraps_saved_theme_before_styles(self):
        # The runner is styled by sat-runner-mb-v60.css (the MakonBook web app's
        # test screen); the saved theme must be applied before it loads.
        for path in (ENG_TEMPLATE, MATH_TEMPLATE):
            source = self._template(path)
            theme_init = source.index("{% include 'base/theme_init.html' %}")
            first_test_stylesheet = source.index("assets/css/sat-runner-mb-v60.css")
            self.assertLess(theme_init, first_test_stylesheet, path.name)
            self.assertIn("assets/js/makon-theme-switcher.js", source)

    def test_both_test_sections_load_image_focus_assets(self):
        for path in (ENG_TEMPLATE, MATH_TEMPLATE):
            source = self._template(path)
            self.assertIn("assets/css/sat-image-focus-v49.css", source)
            self.assertIn("assets/js/sat-image-focus-v49.js", source)

    def test_test_runner_styles_follow_light_and_dark_theme(self):
        css = (ROOT / "static/assets/css/sat-runner-mb-v60.css").read_text(encoding="utf-8")
        self.assertIn("body.mb-runner {", css)
        self.assertIn('html[data-theme="dark"] body.mb-runner {', css)
        for path in (ENG_TEMPLATE, MATH_TEMPLATE):
            self.assertIn("assets/css/sat-runner-mb-v60.css' %}?v=60", self._template(path))

    def test_image_focus_covers_question_graphs_and_visual_answers(self):
        js = FOCUS_JS.read_text(encoding="utf-8")
        self.assertIn("#passage img", js)
        self.assertIn("#question-text img", js)
        self.assertIn("#graph-container img", js)
        self.assertIn("#answers img", js)
        self.assertIn("MutationObserver", js)
        self.assertIn("pointerdown", js)
        self.assertIn("wheel", js)

    def test_visual_answer_image_can_receive_click_without_selecting_choice(self):
        css = FOCUS_CSS.read_text(encoding="utf-8")
        js = FOCUS_JS.read_text(encoding="utf-8")
        self.assertIn(".choice-container .sat-focusable-image", css)
        self.assertIn("pointer-events: auto !important", css)
        self.assertIn("event.stopPropagation()", js)
        self.assertIn("event.preventDefault()", js)
