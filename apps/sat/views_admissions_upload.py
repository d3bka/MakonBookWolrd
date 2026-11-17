"""V86: the media API used by `manage.py upload_admissions_media` on the uploader's PC.

Video and PDF bytes never pass through the server. The PC encrypts each lesson (AES-128
HLS) and renders each PDF into page images, uploads them straight to the private R2
bucket, then sends this API only the small record: which lesson or file, the asset id,
the AES key and the playlist.

Guards:
* Off (404) unless MAKONBOOK_MEDIA_UPLOAD_TOKEN is set to a long random value.
* `Authorization: Bearer <token>`, compared in constant time; HTTPS only in production.
* Wrong tokens are counted per IP; after 10 in an hour the IP gets 429.
* The objects must already be in the private bucket before a record is accepted.
* Every change is logged, never with the key.
"""
import hmac
import json
import logging
import re

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import admissions_media as media
from .models import AdmissionsDocument, AdmissionsLesson, AdmissionsVideo

log = logging.getLogger("makonbook.premium")

MIN_TOKEN_LENGTH = 32
FAIL_LIMIT = 10
FAIL_WINDOW = 60 * 60
KEY_HEX = re.compile(r"^[0-9a-f]{32}$")
MAX_PLAYLIST = 512 * 1024
MAX_DURATION = 6 * 60 * 60


def _json(data, status=200):
    response = JsonResponse(data, status=status)
    response["Cache-Control"] = "private, no-store"
    return response


def _guard(request):
    """None when the request may continue, else the error response."""
    token = getattr(settings, "MAKONBOOK_MEDIA_UPLOAD_TOKEN", "") or ""
    if len(token) < MIN_TOKEN_LENGTH:
        return _json({"error": "not found"}, 404)
    if not settings.DEBUG and not request.is_secure():
        return _json({"error": "https only"}, 403)
    fail_key = f"makon:media-upload:fail:{media.client_ip(request) or 'unknown'}"
    if cache.get(fail_key, 0) >= FAIL_LIMIT:
        return _json({"error": "too many attempts"}, 429)
    header = request.headers.get("Authorization", "")
    given = header[7:].strip() if header.startswith("Bearer ") else ""
    if not hmac.compare_digest(given.encode(), token.encode()):
        cache.add(fail_key, 0, FAIL_WINDOW)
        try:
            cache.incr(fail_key)
        except ValueError:
            cache.set(fail_key, 1, FAIL_WINDOW)
        log.warning("media upload API: wrong token from %s", media.client_ip(request))
        return _json({"error": "forbidden"}, 403)
    if not media.r2_configured():
        return _json({"error": "the private R2 bucket is not configured on the site"}, 503)
    try:
        media.assert_private_bucket()
    except RuntimeError as error:
        return _json({"error": str(error)}, 503)
    return None


def _payload(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _int(value, low, high):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high else None


def _clean_name(value):
    return re.sub(r"[\r\n\t]", " ", str(value or ""))[:200]


@csrf_exempt
@never_cache
@require_GET
def status(request):
    """What the site has, so the PC knows which files are new."""
    blocked = _guard(request)
    if blocked:
        return blocked
    videos = {video.lesson_id: video for video in AdmissionsVideo.objects.all()}
    lessons = [{
        "order": lesson.order, "slug": lesson.slug, "title": lesson.title,
        "video": ({"source_name": videos[lesson.pk].source_name, "storage": videos[lesson.pk].storage,
                   "segment_count": videos[lesson.pk].segment_count} if lesson.pk in videos else None),
    } for lesson in AdmissionsLesson.objects.order_by("order", "id")]
    documents = [{
        "slug": document.slug, "title": document.title, "source_name": document.source_name,
        "ready": document.is_ready, "storage": document.storage, "page_count": document.page_count,
    } for document in AdmissionsDocument.objects.order_by("order", "id")]
    return _json({"bucket": settings.MAKONBOOK_PREMIUM_R2_BUCKET, "lessons": lessons, "documents": documents})


def _check_playlist(text, segment_count):
    if not isinstance(text, str) or not text.startswith("#EXTM3U") or len(text) > MAX_PLAYLIST:
        return "the playlist is not an HLS playlist"
    keys = [line for line in text.splitlines() if line.strip().startswith("#EXT-X-KEY")]
    if len(keys) != 1 or "METHOD=AES-128" not in keys[0]:
        return "the playlist must have exactly one AES-128 key line"
    segments = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    if not segments or any(not media.SEGMENT_NAME.match(name) for name in segments):
        return "the playlist may only name encrypted segments (s0000.ts ...)"
    if len(segments) != segment_count:
        return f"the playlist names {len(segments)} segments, not {segment_count}"
    return None


def _forget_old(asset, storage, kind):
    """Remove a replaced asset after the new record is saved."""
    try:
        if kind == "video":
            if storage == AdmissionsVideo.STORAGE_R2:
                media.delete_video_from_r2(asset)
            media.remove_asset(media.video_dir(asset))
        else:
            if storage == AdmissionsVideo.STORAGE_R2:
                media.delete_doc_from_r2(asset)
            media.remove_asset(media.doc_dir(asset))
    except Exception:  # noqa: BLE001 - the new content is live; a leftover is only storage
        log.exception("could not remove the replaced %s %s", kind, asset)


@csrf_exempt
@never_cache
@require_POST
def register_video(request):
    blocked = _guard(request)
    if blocked:
        return blocked
    data = _payload(request)
    if data is None:
        return _json({"error": "send a JSON object"}, 400)
    lesson = AdmissionsLesson.objects.filter(order=_int(data.get("lesson_order"), 1, 999) or 0).order_by("id").first()
    if lesson is None:
        return _json({"error": "no lesson with this number"}, 404)
    asset = str(data.get("asset") or "")
    key_hex = str(data.get("key_hex") or "").lower()
    segment_count = _int(data.get("segment_count"), 1, 20000)
    duration = _int(data.get("duration_seconds"), 0, MAX_DURATION)
    if not media.ASSET_NAME.match(asset) or not KEY_HEX.match(key_hex) or segment_count is None or duration is None:
        return _json({"error": "asset, key_hex, segment_count or duration_seconds is not valid"}, 400)
    problem = _check_playlist(data.get("playlist_text"), segment_count)
    if problem:
        return _json({"error": problem}, 400)
    existing = AdmissionsVideo.objects.filter(lesson=lesson).first()
    if AdmissionsVideo.objects.filter(asset=asset).exclude(lesson=lesson).exists() or (existing and existing.asset == asset):
        return _json({"error": "this asset is already registered"}, 409)
    stored = media.r2_count(f"{media.VIDEO_DIR}/{asset}/")
    if stored < segment_count:
        return _json({"error": f"only {stored} of {segment_count} segments are in the private bucket"}, 409)
    old = (existing.asset, existing.storage) if existing else None
    with transaction.atomic():
        AdmissionsVideo.objects.update_or_create(lesson=lesson, defaults={
            "asset": asset, "key_hex": key_hex, "duration_seconds": duration, "segment_count": segment_count,
            "source_name": _clean_name(data.get("source_name")), "storage": AdmissionsVideo.STORAGE_R2,
            "playlist_text": data["playlist_text"],
        })
        if duration:
            lesson.minutes = max(1, round(duration / 60))
            lesson.save(update_fields=["minutes"])
    if old:
        _forget_old(old[0], old[1], "video")
    log.info("media upload API: lesson %s video %s (%s segments) from %s",
             lesson.order, asset, segment_count, media.client_ip(request))
    return _json({"ok": True, "lesson": lesson.order, "title": lesson.title, "replaced": bool(old)})


@csrf_exempt
@never_cache
@require_POST
def register_document(request):
    blocked = _guard(request)
    if blocked:
        return blocked
    data = _payload(request)
    if data is None:
        return _json({"error": "send a JSON object"}, 400)
    document = AdmissionsDocument.objects.filter(slug=str(data.get("slug") or "")).first()
    if document is None:
        return _json({"error": "no file with this slug"}, 404)
    asset = str(data.get("asset") or "")
    pages = _int(data.get("page_count"), 1, 999)
    if not media.ASSET_NAME.match(asset) or pages is None:
        return _json({"error": "asset or page_count is not valid"}, 400)
    if asset == document.asset or AdmissionsDocument.objects.filter(asset=asset).exclude(pk=document.pk).exists():
        return _json({"error": "this asset is already registered"}, 409)
    stored = media.r2_count(f"{media.DOC_DIR}/{asset}/")
    if stored < pages:
        return _json({"error": f"only {stored} of {pages} pages are in the private bucket"}, 409)
    old = (document.asset, document.storage) if document.asset else None
    document.asset, document.page_count, document.storage = asset, pages, AdmissionsVideo.STORAGE_R2
    fields = ["asset", "page_count", "storage"]
    if data.get("source_name"):
        document.source_name = _clean_name(data["source_name"])
        fields.append("source_name")
    document.save(update_fields=fields)
    if old:
        _forget_old(old[0], old[1], "document")
    log.info("media upload API: file %s %s (%s pages) from %s", document.slug, asset, pages, media.client_ip(request))
    return _json({"ok": True, "slug": document.slug, "title": document.title, "replaced": bool(old)})
