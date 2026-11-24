"""V99: background processes (no collectstatic, no manifest) must still start."""
import importlib
import json
import tempfile
from pathlib import Path

from django.templatetags.static import static
from django.test import SimpleTestCase, override_settings

PROD_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "apps.base.static_storage.ForgivingManifestStaticFilesStorage"},
}


class MissingManifestTests(SimpleTestCase):
    def test_worker_without_manifest_imports_urls_and_resolves_static(self):
        with tempfile.TemporaryDirectory() as empty_root, override_settings(STATIC_ROOT=empty_root, STORAGES=PROD_STORAGES):
            import satmakon.urls

            importlib.reload(satmakon.urls)  # the Celery worker / Telegram bot crashed right here
            self.assertEqual(static("assets/img/icons/original-icon-nobg.png"), "/static/assets/img/icons/original-icon-nobg.png")
            response = self.client.get("/favicon.ico")
            self.assertEqual(response.status_code, 301)
            self.assertEqual(response["Location"], "/static/assets/img/icons/original-icon-nobg.png")

    def test_web_with_a_manifest_still_gets_hashed_urls(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "staticfiles.json").write_text(json.dumps({
                "version": "1.1",
                "paths": {"assets/app.css": "assets/app.abc123.css"},
                "hash": "x",
            }))
            with override_settings(STATIC_ROOT=root, STORAGES=PROD_STORAGES):
                self.assertEqual(static("assets/app.css"), "/static/assets/app.abc123.css")
                self.assertEqual(static("assets/missing.css"), "/static/assets/missing.css")

    def test_production_settings_use_the_forgiving_storage(self):
        source = Path(__file__).resolve().parents[2] / "satmakon" / "settings.py"
        self.assertIn("apps.base.static_storage.ForgivingManifestStaticFilesStorage", source.read_text(encoding="utf-8"))
