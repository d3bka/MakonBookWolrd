"""Copy images from makonbook-api's private bucket into this app's public one.

makonbook-api keeps published images in its own R2 bucket (``p/img/`` for
practice tests, ``v/img/`` for vocabulary) and hands phones signed links.
This site serves question and word images from its own public bucket, so each
file is copied there once, under ``media/makonbook-api/<same key>``. The files
are named by their bytes, so a key never changes content and one copy is
enough; SyncedImage remembers what was copied.

Reading needs a read-only R2 token for makonbook-api's bucket
(MAKONBOOK_API_R2_* settings). Nothing is ever written to that bucket.
"""

from __future__ import annotations

from django.conf import settings
from django.core.files.base import ContentFile

from .models import SyncedImage

TARGET_PREFIX = "makonbook-api/"


class ImageMirrorUnavailable(RuntimeError):
    pass


def _default_fetch():
    bucket = getattr(settings, "MAKONBOOK_API_R2_BUCKET", "")
    key_id = getattr(settings, "MAKONBOOK_API_R2_ACCESS_KEY_ID", "")
    secret = getattr(settings, "MAKONBOOK_API_R2_SECRET_ACCESS_KEY", "")
    endpoint = getattr(settings, "MAKONBOOK_API_R2_ENDPOINT_URL", "")
    if not (bucket and key_id and secret and endpoint):
        return None

    import boto3
    from botocore.config import Config

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
        region_name=getattr(settings, "MAKONBOOK_API_R2_REGION", "auto"),
        config=Config(signature_version="s3v4", retries={"max_attempts": 4, "mode": "standard"}),
    )

    def fetch(key: str) -> bytes:
        return client.get_object(Bucket=bucket, Key=key)["Body"].read()

    return fetch


def _default_storage():
    from apps.sat.storages import PublicStorage

    return PublicStorage()


class ImageMirror:
    def __init__(self, fetch=None, storage=None):
        self._fetch = fetch
        self._storage = storage
        self._resolved = False
        self.copied = 0

    def _ready(self):
        if not self._resolved:
            if self._fetch is None:
                self._fetch = _default_fetch()
            if self._storage is None:
                self._storage = _default_storage()
            self._resolved = True
        if self._fetch is None:
            raise ImageMirrorUnavailable(
                "makonbook-api's images can't be read: set MAKONBOOK_API_R2_BUCKET, "
                "MAKONBOOK_API_R2_ACCESS_KEY_ID and MAKONBOOK_API_R2_SECRET_ACCESS_KEY "
                "(a read-only R2 token for that bucket)."
            )

    def known(self, source_key: str) -> str | None:
        row = SyncedImage.objects.filter(source_key=source_key).only("url").first()
        return row.url if row else None

    def url(self, source_key: str) -> str:
        """The public URL of ``source_key``, copying the file first if needed."""
        existing = self.known(source_key)
        if existing:
            return existing
        self._ready()
        body = self._fetch(source_key)
        name = TARGET_PREFIX + source_key
        if not self._storage.exists(name):
            name = self._storage.save(name, ContentFile(body))
        url = self._storage.url(name)
        SyncedImage.objects.update_or_create(source_key=source_key, defaults={"url": url, "bytes": len(body)})
        self.copied += 1
        return url
