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
