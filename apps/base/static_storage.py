"""V99: static files storage that never crashes a process for a missing manifest.

Production serves hashed static files from the manifest that `collectstatic`
writes. Only the web container runs collectstatic and mounts that folder; the
Celery worker, Celery beat and the Telegram bot do not. With the strict
manifest storage any `static()` call in those processes (the favicon redirect
in satmakon/urls.py, e-mail and notification templates) raised
"Missing staticfiles manifest entry" and the container restart-looped.

Here a missing entry falls back to the plain, unhashed URL and logs a warning,
so background processes keep running. Web still gets hashed URLs.
"""
import logging

from whitenoise.storage import CompressedManifestStaticFilesStorage

logger = logging.getLogger(__name__)


class ForgivingManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    manifest_strict = False
    _warned = set()

    def stored_name(self, name):
        try:
            return super().stored_name(name)
        except ValueError:
            if name not in self._warned:
                self._warned.add(name)
                logger.warning("Static file %s is not in the manifest; serving the unhashed URL.", name)
            return self.clean_name(name)
