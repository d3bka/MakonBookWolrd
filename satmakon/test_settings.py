from .settings import *  # noqa: F401,F403

# Tests must be deterministic and must never depend on a developer's local
# PostgreSQL service, Docker Desktop, DATABASE_URL, or production database.
# An isolated in-memory SQLite database is fast enough for this suite and is
# recreated from migrations for every test run.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Keep request/response tests independent from production static serving and
# the custom 500-page renderer. WhiteNoise is unnecessary in Django's test
# client and would otherwise inspect STATIC_ROOT/manifest state.
_TEST_DISABLED_MIDDLEWARE = {
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "apps.base.middleware.MakonErrorPageMiddleware",
}
MIDDLEWARE = [item for item in MIDDLEWARE if item not in _TEST_DISABLED_MIDDLEWARE]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# V82: tests never talk to the real private premium bucket, even when the local .env has its keys.
MAKONBOOK_PREMIUM_R2_BUCKET = ""
MAKONBOOK_PREMIUM_R2_ENDPOINT_URL = ""
MAKONBOOK_PREMIUM_R2_ACCESS_KEY_ID = ""
MAKONBOOK_PREMIUM_R2_SECRET_ACCESS_KEY = ""
MAKONBOOK_MEDIA_UPLOAD_TOKEN = ""
MAKONBOOK_MEDIA_UPLOAD_SITE = "https://makonbook.example"

# V92: models' Public/PrivateStorage write to a local temp folder in tests, never to R2.
import tempfile as _tempfile  # noqa: E402
MAKONBOOK_LOCAL_FILE_STORAGE = True
MAKONBOOK_TEST_MEDIA_ROOT = str(Path(_tempfile.gettempdir()) / "makonbook-test-media")

# V97: import tests opt in to the AI answer check explicitly (override_settings).
TEST_IMPORT_REQUIRE_AI_AUDIT = False

# V102: the health watcher never runs threads or sends alerts from the test suite.
SYSTEM_HEALTH_WATCH_ENABLED = False
