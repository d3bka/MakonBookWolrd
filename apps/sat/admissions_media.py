"""V81: protected delivery of premium SATMakon Admissions videos and PDFs.

Rules (protection first):
* Files live only in settings.MAKONBOOK_PREMIUM_ROOT — a private folder outside /media,
  outside git, outside the Docker image and outside R2 (whose r2.dev domain is public).
* Videos are AES-128 encrypted HLS. The playlist, every segment and the key need a
  logged-in student with access, plus a short-lived signed token bound to that user,
  that lesson and that login session. Sharing a link is useless.
* PDFs are never served. Only page images exist, and each one is stamped with the
  viewer's name, login and date when it is sent.
* Every response is `Cache-Control: private, no-store`, same-origin only, and rate limited
  so a script cannot pull a whole course.
* V82: encrypted segments may live in a separate PRIVATE R2 bucket. Django still checks
  every segment request and answers with a redirect to a presigned URL that lives about a
  minute. Premium content plays on at most N devices per student, every key hand-out is
  logged, and keys for too many different videos in an hour are refused.
"""
import hashlib
import io
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import unicodedata
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.http import FileResponse, HttpResponse

TOKEN_SALT = "makonbook.admissions.media.v81"
TOKEN_MAX_AGE = 2 * 60 * 60          # a player page stays valid for one study session
SEGMENT_NAME = re.compile(r"^s\d{4,5}\.ts$")
ASSET_NAME = re.compile(r"^[0-9a-f]{32}$")
VIDEO_DIR = "admissions/videos"
DOC_DIR = "admissions/docs"

# Requests per user. Segments are ~10 s, so watching at 2x with seeking needs ~150 per
# 10 minutes; a downloader pulling whole lessons hits the limits fast. The daily caps allow
# about 7 hours of video and 1,500 PDF pages a day.
RATE_LIMITS = {"segment": 300, "key": 60, "page": 200, "playlist": 60}
DAILY_LIMITS = {"segment": 2500, "key": 300, "page": 1500, "playlist": 300}
RATE_WINDOW = 10 * 60
DAY = 24 * 60 * 60
ACCESS_CACHE_SECONDS = 120

PRIVATE_HEADERS = {
    "Cache-Control": "private, no-store, no-cache, max-age=0, must-revalidate",
    "Pragma": "no-cache",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
    "X-Content-Type-Options": "nosniff",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Referrer-Policy": "same-origin",
}


# ---------------------------------------------------------------- paths


def premium_root():
    return Path(settings.MAKONBOOK_PREMIUM_ROOT)


def new_asset_id():
    return secrets.token_hex(16)


def video_dir(asset):
    if not ASSET_NAME.match(asset or ""):
        raise ValueError("bad asset id")
    return premium_root() / VIDEO_DIR / asset


def doc_dir(asset):
    if not ASSET_NAME.match(asset or ""):
        raise ValueError("bad asset id")
    return premium_root() / DOC_DIR / asset


# ---------------------------------------------------------------- tokens and request guards


def _session_tag(request):
    key = getattr(getattr(request, "session", None), "session_key", None) or ""
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def make_token(request, kind, object_id):
    return signing.dumps([request.user.pk, kind, int(object_id), _session_tag(request)], salt=TOKEN_SALT, compress=False)


def token_ok(request, token, kind, object_id):
    """The token was issued to this user, in this login session, for this object."""
    if not token or not getattr(request.user, "is_authenticated", False):
        return False
    try:
        user_id, token_kind, token_object, session_tag = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
    except (signing.BadSignature, ValueError, TypeError):
        return False
    return (user_id == request.user.pk and token_kind == kind and token_object == int(object_id)
            and secrets.compare_digest(session_tag, _session_tag(request)))


def same_origin(request):
    """Browsers say where a request comes from; refuse other sites embedding or pulling files."""
    site = request.headers.get("Sec-Fetch-Site")
    return site in (None, "same-origin", "none")


def _count(key, window):
    if cache.add(key, 1, window):
        return 1
    try:
        return cache.incr(key)
    except ValueError:  # expired between add and incr
        cache.set(key, 1, window)
        return 1


def over_limit(user, bucket):
    """True when this user went over the 10-minute or the daily limit for this kind of request."""
    short = _count(f"adm-media:{bucket}:{user.pk}", RATE_WINDOW)
    daily = _count(f"adm-media-day:{bucket}:{user.pk}:{date.today().isoformat()}", DAY)
    return short > RATE_LIMITS.get(bucket, 300) or daily > DAILY_LIMITS.get(bucket, 2000)


def access_still_valid(user, kind, object_id, check):
    """Re-check access (check() -> bool) at most every ACCESS_CACHE_SECONDS per user and object,
    so a student who left SATMakon stops receiving segments and pages within two minutes."""
    key = f"adm-access:{kind}:{object_id}:{user.pk}"
    cached = cache.get(key)
    if cached is None:
        cached = bool(check())
        cache.set(key, cached, ACCESS_CACHE_SECONDS)
    return cached


def private_response(response):
    for header, value in PRIVATE_HEADERS.items():
        response[header] = value
    return response


def serve_private_file(relative_path, content_type):
    """Send a file from the premium folder. In production nginx streams it from an
    `internal` location (X-Accel-Redirect) after this view has checked access."""
    relative_path = str(relative_path).replace("\\", "/").lstrip("/")
    prefix = getattr(settings, "MAKONBOOK_PREMIUM_ACCEL_PREFIX", "")
    if prefix:
        response = HttpResponse(content_type=content_type)
        response["X-Accel-Redirect"] = prefix.rstrip("/") + "/" + relative_path
    else:
        path = (premium_root() / relative_path).resolve()
        if premium_root().resolve() not in path.parents or not path.is_file():
            return private_response(HttpResponse(status=404))
        response = FileResponse(open(path, "rb"), content_type=content_type)
    response["Content-Disposition"] = "inline"
    return private_response(response)


# ---------------------------------------------------------------- HLS playlist


def rewrite_playlist(text, key_url, segment_url):
    """Point the key and every segment at the access-checked endpoints.

    key_url: full URL of the key endpoint (with token).
    segment_url: callable(segment_name) -> URL.
    """
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#EXT-X-KEY"):
            line = re.sub(r'URI="[^"]*"', f'URI="{key_url}"', stripped)
        elif stripped and not stripped.startswith("#"):
            name = os.path.basename(stripped)
            if not SEGMENT_NAME.match(name):
                continue  # never point the player at anything we did not create
            line = segment_url(name)
        out.append(line)
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- page watermark


def _ascii(text):
    folded = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", folded).strip()


def masked_phone(user, dot="•"):
    """'+998901234512' -> '+99890•••••12'; '' when the profile has no phone."""
    try:
        raw = user.profile.phone_number or ""
    except Exception:  # noqa: BLE001 - a user without a profile has no phone
        raw = ""
    digits = re.sub(r"[^\d+]", "", raw)
    count = len(re.sub(r"\D", "", digits))
    if count < 10:
        return ""
    keep = 6 if count >= 12 else 4   # +998 90 ... for Uzbek numbers, less for shorter ones
    return digits[:keep] + dot * 5 + digits[-2:]


def watermark_text(user):
    name = _ascii(user.get_full_name()) or _ascii(user.get_username()) or "student"
    login = _ascii(user.get_username())
    parts = ["SATMakon", name]
    if login and login != name:
        parts.append(login)
    parts.append(f"ID {user.pk}")
    phone = masked_phone(user, dot="*")
    if phone:
        parts.append(phone)
    parts.append(date.today().isoformat())
    return " - ".join(parts)


def _font(size):
    from PIL import ImageFont

    for candidate in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


def stamp_page(image_path, text):
    """JPEG bytes of a page image with a tiled diagonal watermark and a footer line."""
    from PIL import Image, ImageDraw

    with Image.open(image_path) as source:
        page = source.convert("RGB")
    width, height = page.size
    size = max(16, width // 42)
    font = _font(size)

    tile = Image.new("RGBA", (width * 2, height * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tile)
    step_y = size * 7
    step_x = int(draw.textlength(text, font=font)) + size * 4
    for row, y in enumerate(range(0, height * 2, step_y)):
        offset = (row % 2) * step_x // 2
        for x in range(-step_x, width * 2, step_x):
            draw.text((x + offset, y), text, font=font, fill=(110, 40, 200, 58))
    tile = tile.rotate(28, resample=Image.BICUBIC)
    left, top = (tile.width - width) // 2, (tile.height - height) // 2
    tile = tile.crop((left, top, left + width, top + height))

    stamped = Image.alpha_composite(page.convert("RGBA"), tile)
    footer = ImageDraw.Draw(stamped)
    small = _font(max(12, width // 80))
    footer.text((size, height - size * 2), text, font=small, fill=(90, 30, 170, 190))
    buffer = io.BytesIO()
    stamped.convert("RGB").save(buffer, "JPEG", quality=80, optimize=True)
    return buffer.getvalue()


# ---------------------------------------------------------------- import pipeline (management command)


def ffmpeg_binary():
    return shutil.which("ffmpeg") or os.environ.get("FFMPEG_BINARY") or "ffmpeg"


DURATION = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def encrypt_video_to_hls(source, *, reencode=False, segment_seconds=6):
    """Cut `source` into AES-128 encrypted HLS in a new private asset folder.

    Returns dict(asset, key_hex, duration_seconds, segment_count). The key file only
    exists in a temporary folder while ffmpeg runs, then it is deleted.
    """
    asset = new_asset_id()
    final_dir = video_dir(asset)
    work_dir = final_dir.with_name(asset + ".partial")
    work_dir.mkdir(parents=True, exist_ok=False)
    key = secrets.token_bytes(16)
    iv = secrets.token_hex(16)
    with tempfile.TemporaryDirectory(prefix="adm-key-") as key_tmp:
        key_path = Path(key_tmp) / "k.bin"
        key_path.write_bytes(key)
        info_path = Path(key_tmp) / "k.info"
        info_path.write_text(f"key\n{key_path}\n{iv}\n", encoding="utf-8")
        codec = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "128k"] if reencode \
            else ["-c", "copy"]
        command = [
            ffmpeg_binary(), "-hide_banner", "-nostdin", "-y", "-i", str(source), *codec,
            "-map", "0:v:0", "-map", "0:a:0?", "-f", "hls", "-hls_time", str(segment_seconds),
            "-hls_playlist_type", "vod", "-hls_key_info_file", str(info_path),
            "-hls_segment_filename", str(work_dir / "s%04d.ts"), str(work_dir / "index.m3u8"),
        ]
        result = subprocess.run(command, capture_output=True, text=True, errors="replace")
    if result.returncode != 0 or not (work_dir / "index.m3u8").is_file():
        shutil.rmtree(work_dir, ignore_errors=True)
        raise RuntimeError(f"ffmpeg failed for {Path(source).name}: {result.stderr[-800:]}")
    match = DURATION.search(result.stderr or "")
    duration = int(int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))) if match else 0
    segments = len(list(work_dir.glob("s*.ts")))
    work_dir.rename(final_dir)
    return {"asset": asset, "key_hex": key.hex(), "duration_seconds": duration, "segment_count": segments}


def render_pdf_pages(source, *, width=1400):
    """Render each PDF page to a JPEG in a new private asset folder. Returns (asset, pages)."""
    import fitz  # PyMuPDF
    from PIL import Image

    asset = new_asset_id()
    final_dir = doc_dir(asset)
    work_dir = final_dir.with_name(asset + ".partial")
    work_dir.mkdir(parents=True, exist_ok=False)
    try:
        with fitz.open(str(source)) as pdf:
            for number, page in enumerate(pdf, start=1):
                zoom = width / max(1.0, page.rect.width)
                pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                image.save(work_dir / f"p{number:03d}.jpg", "JPEG", quality=82, optimize=True)
            pages = pdf.page_count
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise
    work_dir.rename(final_dir)
    return asset, pages


def remove_asset(folder):
    if folder and folder.exists() and premium_root().resolve() in folder.resolve().parents:
        shutil.rmtree(folder, ignore_errors=True)


# ---------------------------------------------------------------- V82: private R2 bucket for segments


def r2_configured():
    return all(getattr(settings, name, "") for name in (
        "MAKONBOOK_PREMIUM_R2_BUCKET", "MAKONBOOK_PREMIUM_R2_ENDPOINT_URL",
        "MAKONBOOK_PREMIUM_R2_ACCESS_KEY_ID", "MAKONBOOK_PREMIUM_R2_SECRET_ACCESS_KEY",
    ))


def public_bucket_names():
    names = {getattr(settings, "AWS_STORAGE_BUCKET_NAME", None), getattr(settings, "R2_BUCKET_NAME", None),
             getattr(settings, "MAKONBOOK_API_R2_BUCKET", None)}
    return {name for name in names if name}


def assert_private_bucket():
    """The premium bucket must be its own bucket: the media bucket has a public r2.dev domain."""
    bucket = settings.MAKONBOOK_PREMIUM_R2_BUCKET
    if not bucket or bucket in public_bucket_names():
        raise RuntimeError(
            f"MAKONBOOK_PREMIUM_R2_BUCKET ({bucket or 'empty'}) is not a separate private bucket."
        )
    return bucket


_R2_CLIENT = None


def r2_client():
    global _R2_CLIENT
    if _R2_CLIENT is None:
        import boto3
        from botocore.config import Config

        _R2_CLIENT = boto3.client(
            "s3",
            endpoint_url=settings.MAKONBOOK_PREMIUM_R2_ENDPOINT_URL,
            aws_access_key_id=settings.MAKONBOOK_PREMIUM_R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.MAKONBOOK_PREMIUM_R2_SECRET_ACCESS_KEY,
            region_name="auto",
            config=Config(signature_version="s3v4", retries={"max_attempts": 8, "mode": "adaptive"},
                          max_pool_connections=32),
        )
    return _R2_CLIENT


def r2_segment_key(asset, name):
    if not ASSET_NAME.match(asset or "") or not SEGMENT_NAME.match(name or ""):
        raise ValueError("bad segment")
    return f"{VIDEO_DIR}/{asset}/{name}"


def presigned_segment_url(asset, name):
    return r2_client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": assert_private_bucket(), "Key": r2_segment_key(asset, name),
            "ResponseCacheControl": "private, no-store, max-age=0",
            "ResponseContentType": "video/mp2t",
            "ResponseContentDisposition": "inline",
        },
        ExpiresIn=max(15, int(getattr(settings, "MAKONBOOK_PREMIUM_R2_URL_TTL", 60))),
    )


def upload_video_to_r2(asset, *, workers=8):
    """Upload every encrypted segment of a local asset to the private bucket and verify it.
    Returns the number of segments. The playlist and the key never go to R2."""
    from concurrent.futures import ThreadPoolExecutor

    bucket = assert_private_bucket()
    folder = video_dir(asset)
    segments = sorted(p for p in folder.iterdir() if SEGMENT_NAME.match(p.name))
    client = r2_client()

    def put(path):
        client.upload_file(str(path), bucket, r2_segment_key(asset, path.name), ExtraArgs={
            "ContentType": "video/mp2t", "CacheControl": "private, no-store, max-age=0",
        })

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(put, segments))
    stored = 0
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=f"{VIDEO_DIR}/{asset}/"):
        stored += len(page.get("Contents", []))
    if stored < len(segments):
        raise RuntimeError(f"R2 upload incomplete for {asset}: {stored}/{len(segments)} segments")
    return len(segments)


def delete_video_from_r2(asset):
    client, bucket = r2_client(), assert_private_bucket()
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=f"{VIDEO_DIR}/{asset}/"):
        keys = [{"Key": item["Key"]} for item in page.get("Contents", [])]
        if keys:
            client.delete_objects(Bucket=bucket, Delete={"Objects": keys, "Quiet": True})


def apply_bucket_cors():
    """hls.js follows the redirect from our segment endpoint to R2 with XHR, so the bucket
    must allow GET from the site's own origins (and nothing else)."""
    origins = [o for o in getattr(settings, "MAKONBOOK_PREMIUM_R2_ALLOWED_ORIGINS", []) if o]
    if not origins or any("*" in origin or not origin.startswith("https://") for origin in origins):
        raise RuntimeError("MAKONBOOK_PREMIUM_R2_ALLOWED_ORIGINS must list exact https:// origins, no wildcards.")
    r2_client().put_bucket_cors(Bucket=assert_private_bucket(), CORSConfiguration={"CORSRules": [{
        "AllowedOrigins": origins, "AllowedMethods": ["GET", "HEAD"], "AllowedHeaders": ["Range"],
        "MaxAgeSeconds": 3600,
    }]})
    return origins


# ---------------------------------------------------------------- V82: devices and key log


def log_premium():
    import logging

    return logging.getLogger("makonbook.premium")


def client_ip(request):
    """The address our nginx saw (it overwrites X-Real-IP with $remote_addr); never a
    client-supplied X-Forwarded-For entry. Invalid values fall back to REMOTE_ADDR."""
    import ipaddress

    for candidate in (request.META.get("HTTP_X_REAL_IP"), request.META.get("REMOTE_ADDR")):
        try:
            return str(ipaddress.ip_address((candidate or "").strip()))
        except ValueError:
            continue
    return None


def register_device(request):
    """Mark this browser session as the newest device of the student and switch off the
    oldest ones beyond MAKONBOOK_PREMIUM_MAX_DEVICES. Called when a lesson or file opens."""
    from django.db import transaction
    from django.utils import timezone

    from .models import AdmissionsMediaSession

    tag = _session_tag(request)
    limit = max(1, int(getattr(settings, "MAKONBOOK_PREMIUM_MAX_DEVICES", 2)))
    with transaction.atomic():
        # Lock this student's rows so two devices opening at once cannot both stay over the limit.
        list(AdmissionsMediaSession.objects.select_for_update().filter(user=request.user).values_list("pk", flat=True))
        row, _ = AdmissionsMediaSession.objects.update_or_create(
            user=request.user, session_tag=tag,
            defaults={"ip": client_ip(request), "user_agent": (request.META.get("HTTP_USER_AGENT") or "")[:300],
                      "revoked_at": None},
        )
        active = list(AdmissionsMediaSession.objects.filter(user=request.user, revoked_at__isnull=True)
                      .order_by("-last_seen", "-id"))
        stale = [item for item in active[limit:] if item.pk != row.pk]
        if stale:
            AdmissionsMediaSession.objects.filter(pk__in=[item.pk for item in stale]).update(revoked_at=timezone.now())
    if stale:
        for item in stale:
            cache.delete(f"adm-device:{request.user.pk}:{item.session_tag}")
        log_premium().warning("premium device limit: user %s, %s older session(s) switched off",
                              request.user.pk, len(stale))
    cache.set(f"adm-device:{request.user.pk}:{tag}", True, 60)
    return row


def device_active(request):
    """False when a newer device took this session's place (re-checked at most every minute)."""
    from .models import AdmissionsMediaSession

    tag = _session_tag(request)
    key = f"adm-device:{request.user.pk}:{tag}"
    cached = cache.get(key)
    if cached is None:
        cached = AdmissionsMediaSession.objects.filter(
            user=request.user, session_tag=tag, revoked_at__isnull=True).exists()
        cache.set(key, cached, 60)
    return cached


def key_allowed(request, video):
    """Log the key request. Refuse when the student asked for keys to too many different
    videos in the last hour. Warn when keys went to 3+ different IPs in a day."""
    from datetime import timedelta

    from django.utils import timezone

    from .models import AdmissionsKeyLog

    now = timezone.now()
    recent = AdmissionsKeyLog.objects.filter(user=request.user, allowed=True, created_at__gte=now - timedelta(hours=1))
    videos = set(recent.values_list("video_id", flat=True))
    limit = max(1, int(getattr(settings, "MAKONBOOK_PREMIUM_MAX_VIDEOS_PER_HOUR", 25)))
    allowed = video.pk in videos or len(videos) < limit
    AdmissionsKeyLog.objects.create(
        user=request.user, video=video, ip=client_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:300], session_tag=_session_tag(request),
        allowed=allowed, note="" if allowed else f"over {limit} videos per hour",
    )
    if not allowed:
        log_premium().warning("premium alert: user %s asked for keys to %s+ videos in an hour", request.user.pk, limit)
        return False
    ips = set(AdmissionsKeyLog.objects.filter(user=request.user, created_at__gte=now - timedelta(days=1))
              .exclude(ip=None).values_list("ip", flat=True))
    if len(ips) >= 3:
        log_premium().warning("premium alert: user %s got keys from %s different IPs in a day", request.user.pk, len(ips))
    return True
