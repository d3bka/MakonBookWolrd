from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class PublicPlacementHeaderSyncV56123Tests(SimpleTestCase):
    def _template(self, name):
        return (Path(settings.BASE_DIR) / "templates" / "sat" / "public_placement" / name).read_text(encoding="utf-8")

    def test_public_placement_pages_use_landing_header_shell(self):
        for name in ("list.html", "start.html", "result.html"):
            with self.subTest(template=name):
                template = self._template(name)
                self.assertIn('class="mb56-page pp-page', template)
                self.assertIn('class="mb56-noise"', template)
                self.assertIn("{% include 'landing/_public_header.html' with local_nav=False %}", template)
                self.assertIn("public-placement-header-sync-v5612-3.css", template)

    def test_header_is_not_reimplemented_inside_public_placement_pages(self):
        for name in ("list.html", "start.html", "result.html"):
            with self.subTest(template=name):
                template = self._template(name)
                self.assertNotIn('<header class="mb56-nav-wrap"', template)
