"""Unguessable storage keys for student and exam content.

PublicStorage and PrivateStorage share one R2 bucket and the bucket's r2.dev
domain serves every object, so a file is only as private as its key. Keys built
from the client's filename (``IMG_1234.jpg``) are guessable; these are not:
``<prefix>/<yyyy>/<mm>/<32 hex chars><ext>`` — 128 bits of randomness.
"""
import os
import re
import uuid

from django.utils import timezone
from django.utils.deconstruct import deconstructible

_SAFE_EXT = re.compile(r"^\.[a-z0-9]{1,8}$")
RANDOM_NAME = re.compile(r"/[0-9a-f]{32}(\.[a-z0-9]{1,8})?$")


def safe_extension(filename):
    ext = os.path.splitext(str(filename or ""))[1].lower()
    return ext if _SAFE_EXT.match(ext) else ""


def is_random_name(name):
    return bool(RANDOM_NAME.search(str(name or "")))


@deconstructible
class RandomUploadPath:
    def __init__(self, prefix):
        self.prefix = str(prefix).strip("/")

    def __call__(self, instance, filename):
        now = timezone.now()
        return f"{self.prefix}/{now:%Y}/{now:%m}/{uuid.uuid4().hex}{safe_extension(filename)}"

    def __eq__(self, other):
        return isinstance(other, RandomUploadPath) and other.prefix == self.prefix
