"""V81: access-checked delivery of premium Admissions videos (encrypted HLS) and PDF pages.

Every endpoint: logged-in student account, the lesson/file must be open to this student
(full course for current SATMakon students, first lessons for others), same-origin
requests only, a signed token bound to user + object + login session, rate limits,
and private no-store responses. See apps/sat/admissions_media.py.
"""
import logging

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from . import admissions_media as media
from .models import AdmissionsDocument, AdmissionsVideo
from .student_workspace import should_use_student_workspace, student_workspace_context
from .views_admissions import _course_state, _student_only, course_documents, viewer_label

log = logging.getLogger("makonbook.premium")


def _denied(status=403):
    return media.private_response(HttpResponse(status=status))


def _open_lesson(request, slug):
    """The lesson if this student may watch it, else None."""
    if not should_use_student_workspace(request.user):
        return None
    lessons, full, limit, done_ids = _course_state(request.user)
    lesson = next((item for item in lessons if item.slug == slug), None)
    if lesson is None or lesson.is_locked or lesson.video is None:
        return None
    return lesson


def _other_device():
    """This browser session was replaced by a newer device of the same student."""
    response = _denied(409)
    response["X-Makon-Reason"] = "device"
    return response


def _guard(request, bucket):
    if not media.same_origin(request):
        log.warning("premium %s refused: cross-site request by user %s", bucket, request.user.pk)
        return _denied()
    if media.over_limit(request.user, bucket):
        log.warning("premium %s rate limit hit by user %s", bucket, request.user.pk)
        return _denied(429)
    return None


# ---------------------------------------------------------------- video


@never_cache
@require_GET
@login_required(login_url='/login/')
def video_playlist(request, slug):
    blocked = _guard(request, "playlist")
    if blocked:
        return blocked
    lesson = _open_lesson(request, slug)
    if lesson is None:
        return _denied(404)
    video = lesson.video
    text = video.playlist_text
    if not text:
        try:
            text = (media.video_dir(video.asset) / "index.m3u8").read_text(encoding="utf-8")
        except (OSError, ValueError):
            log.error("premium playlist missing for lesson %s", lesson.pk)
            return _denied(404)
    media.register_device(request)  # this device becomes the newest; the oldest beyond the limit stops
    token = media.make_token(request, "video", video.pk)
    key_url = reverse("admissions_video_key_root", args=[slug]) + f"?t={token}"
    segment_base = reverse("admissions_video_segment_root", args=[slug, "NAME"])
    body = media.rewrite_playlist(text, key_url, lambda name: segment_base.replace("NAME", name) + f"?t={token}")
    log.info("premium video %s opened by user %s", lesson.pk, request.user.pk)
    return media.private_response(HttpResponse(body, content_type="application/vnd.apple.mpegurl"))


@never_cache
@require_GET
@login_required(login_url='/login/')
def video_key(request, slug):
    blocked = _guard(request, "key")
    if blocked:
        return blocked
    lesson = _open_lesson(request, slug)  # access is re-checked: a student who left loses the key
    if lesson is None or not media.token_ok(request, request.GET.get("t"), "video", lesson.video.pk):
        return _denied()
    if not media.device_active(request):
        return _other_device()
    if not media.key_allowed(request, lesson.video):  # logged; too many different videos in an hour -> 429
        return _denied(429)
    return media.private_response(HttpResponse(bytes.fromhex(lesson.video.key_hex), content_type="application/octet-stream"))


@never_cache
@require_GET
@login_required(login_url='/login/')
def video_segment(request, slug, name):
    if not media.SEGMENT_NAME.match(name):
        raise Http404
    blocked = _guard(request, "segment")
    if blocked:
        return blocked
    from .models import AdmissionsVideo

    video = (AdmissionsVideo.objects.filter(lesson__slug=slug, lesson__is_published=True)
             .only("pk", "asset", "storage").first())
    if video is None or not media.token_ok(request, request.GET.get("t"), "video", video.pk):
        return _denied()
    # The token proves access when it was issued; access is re-checked every couple of minutes.
    if not media.access_still_valid(request.user, "video", video.pk, lambda: _open_lesson(request, slug) is not None):
        return _denied()
    if not media.device_active(request):
        return _other_device()
    try:
        media.video_dir(video.asset)  # validates the stored folder name
    except ValueError:
        return _denied(404)
    if video.storage == AdmissionsVideo.STORAGE_R2:
        # Bytes come from the private bucket through a presigned URL that lives about a minute.
        try:
            url = media.presigned_segment_url(video.asset, name)
        except ValueError:
            return _denied(404)
        except Exception:  # noqa: BLE001 - misconfigured bucket must not leak details
            log.exception("premium R2 presign failed for video %s", video.pk)
            return _denied(503)
        return media.private_response(HttpResponseRedirect(url))
    return media.serve_private_file(f"{media.VIDEO_DIR}/{video.asset}/{name}", "video/mp2t")


# ---------------------------------------------------------------- documents


def _open_document(request, slug):
    if not should_use_student_workspace(request.user):
        return None, None
    lessons, full, limit, done_ids = _course_state(request.user)
    document = next((item for item in course_documents(lessons, full) if item.slug == slug), None)
    return document, lessons


@login_required(login_url='/login/')
def document_view(request, slug):
    denied = _student_only(request)
    if denied:
        return denied
    document, lessons = _open_document(request, slug)
    if document is None:
        raise Http404("File not found")
    context = student_workspace_context(request.user, active="admissions")
    context.update({"document": document, "viewer_label": viewer_label(request.user)})
    if document.is_open:
        media.register_device(request)
        token = media.make_token(request, "doc", document.pk)
        context["document_pages"] = [
            reverse("admissions_document_page_root", args=[slug, number]) + f"?t={token}"
            for number in range(1, document.page_count + 1)
        ]
        log.info("premium file %s opened by user %s", document.pk, request.user.pk)
    by_number = {lesson.number: lesson for lesson in lessons}
    context["document_lessons"] = [by_number[n] for n in document.lesson_numbers if n in by_number]
    response = render(request, "sat/admissions_document.html", context)
    return media.private_response(response)


@never_cache
@require_GET
@login_required(login_url='/login/')
def document_page(request, slug, number):
    blocked = _guard(request, "page")
    if blocked:
        return blocked
    document = (AdmissionsDocument.objects.filter(slug=slug, is_published=True)
                .only("pk", "asset", "page_count", "storage").first())
    if document is None or not document.asset or not 1 <= number <= document.page_count:
        return _denied(404)
    if not media.token_ok(request, request.GET.get("t"), "doc", document.pk):
        return _denied()
    if not media.access_still_valid(request.user, "doc", document.pk,
                                    lambda: getattr(_open_document(request, slug)[0], "is_open", False)):
        return _denied()
    if not media.device_active(request):
        return _other_device()
    if document.storage == AdmissionsVideo.STORAGE_R2:
        # V86: the clean page comes from the private bucket and is stamped here, so an
        # unstamped page never leaves the server.
        try:
            source = media.read_page_from_r2(document.asset, number)
        except ValueError:
            return _denied(404)
        except Exception:  # noqa: BLE001 - a missing object or bucket trouble must not leak details
            log.exception("premium R2 page %s/%s failed", document.pk, number)
            return _denied(503)
    else:
        try:
            source = media.doc_dir(document.asset) / f"p{number:03d}.jpg"
        except ValueError:
            return _denied(404)
        if not source.is_file():
            return _denied(404)
    image = media.stamp_page(source, media.watermark_text(request.user))
    response = HttpResponse(image, content_type="image/jpeg")
    response["Content-Disposition"] = "inline"
    return media.private_response(response)
