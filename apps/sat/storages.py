from pathlib import Path

from django.conf import settings

if getattr(settings, "MAKONBOOK_LOCAL_FILE_STORAGE", False):
    # V92: tests (and CI without R2 keys) keep every upload in a local temporary folder.
    # Models create these storages when they are imported, so the test settings cannot
    # swap them through STORAGES; before this, local test runs uploaded files to the real
    # public R2 bucket. The class paths stay the same, so migrations do not change.
    from django.core.files.storage import FileSystemStorage

    def _test_root(kind):
        return str(Path(getattr(settings, "MAKONBOOK_TEST_MEDIA_ROOT", "/tmp/makonbook-test-media")) / kind)

    class PublicStorage(FileSystemStorage):
        """Local stand-in for the public R2 storage (tests only)."""

        def __init__(self, **kwargs):
            kwargs.setdefault("location", _test_root("public"))
            kwargs.setdefault("base_url", "/media/test-public/")
            super().__init__(**kwargs)

    class PrivateStorage(FileSystemStorage):
        """Local stand-in for the private R2 storage (tests only)."""

        def __init__(self, **kwargs):
            kwargs.setdefault("location", _test_root("private"))
            kwargs.setdefault("base_url", "/media/test-private/")
            super().__init__(**kwargs)

else:
    from storages.backends.s3boto3 import S3Boto3Storage

    class PublicStorage(S3Boto3Storage):
        """Public storage for images and public files with Cloudflare R2"""
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        custom_domain = settings.AWS_S3_CUSTOM_DOMAIN
        file_overwrite = False
        default_acl = None
        querystring_auth = False
        location = "media"

        def url(self, name, parameters=None, expire=None, http_method=None):
            clean_name = str(name).lstrip("/")
            return f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/media/{clean_name}"

    class PrivateStorage(S3Boto3Storage):
        """Private storage for sensitive files with signed URLs"""
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        custom_domain = None
        file_overwrite = False
        default_acl = None
        querystring_auth = True
        location = "private"
