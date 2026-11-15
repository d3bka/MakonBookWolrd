"""V73: store user images under a server-chosen name that matches their real format.

ImageField does not validate the extension when a model is created directly, so
an upload called ``x.html`` that is also a valid PNG used to be stored as
``x.html`` and served with an HTML content type from the media domain.
"""
import uuid

IMAGE_EXTENSIONS = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp", "GIF": "gif"}


def verified_image_extension(uploaded, allowed=("PNG", "JPEG", "WEBP", "GIF")):
    """Return the real image extension (``"png"``...) or ``None`` if it is not an allowed image."""
    try:
        from PIL import Image

        uploaded.seek(0)
        with Image.open(uploaded) as probe:
            image_format = (probe.format or "").upper()
            probe.verify()
    except Exception:  # noqa: BLE001 - anything Pillow cannot read is not an image
        return None
    finally:
        try:
            uploaded.seek(0)
        except Exception:  # noqa: BLE001
            pass
    if image_format not in allowed:
        return None
    return IMAGE_EXTENSIONS.get(image_format)


def rename_verified_image(uploaded, allowed=("PNG", "JPEG", "WEBP", "GIF")):
    """Give a verified image a random name with its real extension. Returns False if it is not an image."""
    extension = verified_image_extension(uploaded, allowed=allowed)
    if not extension:
        return False
    uploaded.name = f"{uuid.uuid4().hex}.{extension}"
    return True
