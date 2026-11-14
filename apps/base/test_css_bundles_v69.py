"""V69: the student shell loads 3 CSS bundles that must match their sources."""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from apps.base.css_bundles import BUNDLES, CSS_DIR, render_bundle


class CssBundleTests(SimpleTestCase):
    def test_bundles_are_up_to_date(self):
        for name in BUNDLES:
            with self.subTest(bundle=name):
                built = (CSS_DIR / name).read_text(encoding="utf-8")
                self.assertEqual(
                    built, render_bundle(name),
                    f"{name} is stale — run `python manage.py build_css_bundles` after editing its sources.",
                )

    def test_student_shell_links_bundles_not_individual_sources(self):
        shell = (Path(settings.BASE_DIR) / "templates/sat/student_workspace.html").read_text(encoding="utf-8")
        for name, sources in BUNDLES.items():
            with self.subTest(bundle=name):
                self.assertIn(name, shell)
                for source in sources:
                    self.assertNotIn(f"assets/css/{source}'", shell)

    def test_both_shells_cancel_the_legacy_section_padding(self):
        # main.css sets `section{padding:60px 0}`; inside the workspaces that
        # leaked 60-120px gaps into ~15 pages. The reset must stay zero-class
        # specificity so component rules that set their own padding still win.
        reset = (CSS_DIR / "workspace-section-reset-v69.css").read_text(encoding="utf-8")
        self.assertIn(":where(.mb50-main) section", reset)
        self.assertIn("workspace-section-reset-v69.css", BUNDLES["student-shell-layers.bundle.css"])
        staff = (Path(settings.BASE_DIR) / "templates/sat/staff_workspace.html").read_text(encoding="utf-8")
        self.assertIn("assets/css/workspace-section-reset-v69.css", staff)

    def test_bundles_keep_the_original_cascade_order(self):
        base = (CSS_DIR / "student-shell-base.bundle.css").read_text(encoding="utf-8")
        positions = [base.index(f"/* ==== {source} ==== */") for source in BUNDLES["student-shell-base.bundle.css"]]
        self.assertEqual(positions, sorted(positions))
