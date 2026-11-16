"""V80: the Universities catalogue (all students) and the Admissions course.

Admissions: current SATMakon students get every lesson; everyone else gets the first
MAKONBOOK_FREE_ADMISSIONS_LESSONS (3) and sees the rest locked.
"""
from collections import OrderedDict

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Prefetch
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import (
    AdmissionsLesson, AdmissionsLessonProgress, AdmissionsResource, AdmissionsStep, TestReview, University,
)
from .student_access import is_active_satmakon_student
from .student_workspace import should_use_student_workspace, student_workspace_context

# Old Admissions section slugs (V52) -> the new course index.
LEGACY_ADMISSIONS_SLUGS = {"university_guide", "application_help", "scholarships"}

FIT_LABELS = {"reach": "Reach", "match": "Match", "safety": "Safety"}

# ISO country codes, shown as small badges (flag emoji do not render on Windows).
FLAGS = {
    "USA": "US", "United Kingdom": "GB", "Canada": "CA", "Australia": "AU", "New Zealand": "NZ",
    "Switzerland": "CH", "Germany": "DE", "Netherlands": "NL", "Belgium": "BE", "Italy": "IT",
    "Spain": "ES", "Ireland": "IE", "Sweden": "SE", "Denmark": "DK", "Finland": "FI", "France": "FR",
    "Czech Republic": "CZ", "Hungary": "HU", "Singapore": "SG", "Hong Kong": "HK", "China": "CN",
    "Japan": "JP", "South Korea": "KR", "Malaysia": "MY", "Kazakhstan": "KZ",
    "United Arab Emirates": "AE", "Qatar": "QA", "Turkey": "TR", "Uzbekistan": "UZ",
}

def _code(country):
    return FLAGS.get(country) or (country or "?")[:2].upper()


RANK_ORDER = {"top10": 1, "top50": 2, "top100": 3, "top200": 4, "top500": 5, "other": 6}


def free_admissions_lesson_limit():
    return max(0, int(getattr(settings, "MAKONBOOK_FREE_ADMISSIONS_LESSONS", 3) or 0))


def _student_only(request):
    """Staff accounts keep their own dashboards (same rule as Mistakes)."""
    if not should_use_student_workspace(request.user):
        return redirect("student_dashboard_root")
    return None


def best_sat_score(user):
    return (
        TestReview.objects.filter(user=user, score__gte=400, score__lte=1600)
        .aggregate(best=Max("score")).get("best")
    )


def university_fit(score, uni):
    """'reach' / 'match' / 'safety' for a student's SAT score, or '' when we cannot tell.

    Same rules as university-catalogue-v80.js. Very selective schools (under 10%) are
    always a reach; a top score only makes a school under 30% a match, never a safety.
    """
    rate = float(uni.acceptance_rate) if uni.acceptance_rate is not None else None
    if rate is not None and rate < 10:
        return "reach"
    if not score or uni.sat_kind == "none" or not uni.sat_low:
        return "reach" if rate is not None and rate < 20 else ""
    high = uni.sat_high or uni.sat_low
    if score < uni.sat_low:
        return "reach"
    if score < high:
        return "reach" if rate is not None and rate < 20 else "match"
    return "safety" if rate is None or rate >= 30 else "match"


def _university_row(uni):
    return {
        "s": uni.slug, "n": uni.name, "c": uni.country, "ci": uni.city, "r": uni.region, "k": uni.kind,
        "rb": uni.rank_band, "a": float(uni.acceptance_rate) if uni.acceptance_rate is not None else None,
        "lo": uni.sat_low, "hi": uni.sat_high, "sk": uni.sat_kind, "tp": uni.test_policy,
        "ie": float(uni.ielts_min) if uni.ielts_min is not None else None, "to": uni.toefl_min,
        "t": uni.tuition_usd, "ai": uni.aid, "p": uni.platform, "f": _code(uni.country),
    }


@login_required(login_url='/login/')
def universities(request):
    denied = _student_only(request)
    if denied:
        return denied
    rows = list(University.objects.filter(is_active=True))
    countries = sorted({uni.country for uni in rows})
    context = student_workspace_context(request.user, active="universities")
    context.update({
        "uni_rows": [_university_row(uni) for uni in rows],
        "uni_total": len(rows),
        "uni_country_count": len(countries),
        "uni_countries": [{"name": name, "flag": _code(name)} for name in countries],
        "uni_regions": University.REGION_CHOICES,
        "uni_ranks": University.RANK_CHOICES,
        "uni_aid": University.AID_CHOICES,
        "uni_policies": University.TEST_POLICY_CHOICES,
        "uni_platforms": [c for c in University.PLATFORM_CHOICES if c[0] != "other"],
        "uni_best_score": best_sat_score(request.user),
        "uni_data_year": rows[0].data_year if rows else "",
    })
    return render(request, "sat/universities.html", context)


@login_required(login_url='/login/')
def university_detail(request, slug):
    denied = _student_only(request)
    if denied:
        return denied
    uni = get_object_or_404(University, slug=slug, is_active=True)
    score = best_sat_score(request.user)
    similar = list(
        University.objects.filter(is_active=True, region=uni.region, rank_band=uni.rank_band)
        .exclude(pk=uni.pk).order_by("name")[:6]
    )
    if len(similar) < 3:
        similar += list(University.objects.filter(is_active=True, country=uni.country)
                        .exclude(pk__in=[uni.pk] + [u.pk for u in similar]).order_by("name")[:6 - len(similar)])
    fit = university_fit(score, uni)
    context = student_workspace_context(request.user, active="universities")
    context.update({
        "uni": uni,
        "uni_flag": _code(uni.country),
        "uni_score": score,
        "uni_fit": fit,
        "uni_fit_label": FIT_LABELS.get(fit, ""),
        "uni_similar": [{"uni": item, "flag": _code(item.country)} for item in similar],
        "uni_sat_position": _sat_position(score, uni),
    })
    return render(request, "sat/university_detail.html", context)


def _sat_position(score, uni):
    """Where the score and the SAT range sit on a 1000–1600 bar, in percent."""
    if not uni.sat_low or uni.sat_kind == "none":
        return None

    def pct(value):
        return max(0, min(100, round((value - 1000) / 6)))

    high = uni.sat_high or uni.sat_low
    you = pct(score) if score else None
    return {
        "low": pct(uni.sat_low), "width": max(2, pct(high) - pct(uni.sat_low)), "score": you,
        # keep the "You" label inside the bar at the ends
        "edge": "" if you is None or 12 <= you <= 88 else ("start" if you < 12 else "end"),
    }


# ---------------------------------------------------------------- Admissions course


def _lessons():
    return list(
        AdmissionsLesson.objects.filter(is_published=True)
        .prefetch_related(Prefetch("steps", queryset=AdmissionsStep.objects.order_by("order", "id")),
                          Prefetch("resources", queryset=AdmissionsResource.objects.order_by("order", "id")))
        .order_by("order", "id")
    )


def _course_state(user):
    """Lessons with .number, .is_locked and .is_done set, plus summary numbers."""
    lessons = _lessons()
    full = is_active_satmakon_student(user)
    limit = free_admissions_lesson_limit()
    done_ids = set(
        AdmissionsLessonProgress.objects.filter(user=user, lesson__in=lessons).values_list("lesson_id", flat=True)
    )
    for index, lesson in enumerate(lessons):
        lesson.number = index + 1
        lesson.is_locked = not full and index >= limit
        lesson.is_done = lesson.pk in done_ids
        lesson.has_video = bool(lesson.youtube_embed_url)
    return lessons, full, limit, done_ids


@login_required(login_url='/login/')
def admissions_home(request):
    denied = _student_only(request)
    if denied:
        return denied
    lessons, full, limit, done_ids = _course_state(request.user)
    labels = dict(AdmissionsLesson.MODULE_CHOICES)
    modules = OrderedDict()
    for lesson in lessons:
        module = modules.setdefault(lesson.module, {"key": lesson.module, "label": labels.get(lesson.module, ""),
                                                     "lessons": []})
        module["lessons"].append(lesson)
    open_lessons = [lesson for lesson in lessons if not lesson.is_locked]
    next_lesson = next((lesson for lesson in open_lessons if not lesson.is_done), None)
    done = sum(1 for lesson in lessons if lesson.is_done)
    context = student_workspace_context(request.user, active="admissions")
    context.update({
        "adm_modules": list(modules.values()),
        "adm_total": len(lessons),
        "adm_done": done,
        "adm_percent": round(done * 100 / len(lessons)) if lessons else 0,
        "adm_full_access": full,
        "adm_free_limit": limit,
        "adm_locked_count": sum(1 for lesson in lessons if lesson.is_locked),
        "adm_next": next_lesson,
        "adm_minutes": sum(lesson.minutes for lesson in lessons),
        "adm_video_count": sum(1 for lesson in lessons if lesson.has_video),
    })
    return render(request, "sat/admissions_home.html", context)


@login_required(login_url='/login/')
def admissions_lesson(request, slug):
    denied = _student_only(request)
    if denied:
        return denied
    if slug in LEGACY_ADMISSIONS_SLUGS:
        return redirect("admissions_root")
    lessons, full, limit, done_ids = _course_state(request.user)
    lesson = next((item for item in lessons if item.slug == slug), None)
    if lesson is None:
        raise Http404("Lesson not found")
    index = lessons.index(lesson)
    previous_lesson = lessons[index - 1] if index > 0 else None
    next_lesson = lessons[index + 1] if index + 1 < len(lessons) else None
    context = student_workspace_context(request.user, active="admissions")
    context.update({
        "lesson": lesson,
        "lesson_module": dict(AdmissionsLesson.MODULE_CHOICES).get(lesson.module, ""),
        "lesson_steps": [] if lesson.is_locked else [
            {"title": step.title, "blocks": _step_blocks(step.body)} for step in lesson.steps.all()
        ],
        "lesson_resources": [] if lesson.is_locked else list(lesson.resources.all()),
        "lesson_prev": previous_lesson,
        "lesson_next": next_lesson,
        "adm_total": len(lessons),
        "adm_full_access": full,
        "adm_free_limit": limit,
        "lesson_links_universities": lesson.module == "choose",
    })
    return render(request, "sat/admissions_lesson.html", context)


def _step_blocks(body):
    """Split a step body into paragraphs and bullet lists ('- ' lines)."""
    blocks, bullets = [], []
    for raw in (body or "").splitlines():
        line = raw.strip()
        if line.startswith("- "):
            bullets.append(line[2:].strip())
            continue
        if bullets:
            blocks.append({"kind": "list", "items": bullets})
            bullets = []
        if line:
            blocks.append({"kind": "text", "text": line})
    if bullets:
        blocks.append({"kind": "list", "items": bullets})
    return blocks


@login_required(login_url='/login/')
@require_POST
def admissions_lesson_complete(request, slug):
    if not should_use_student_workspace(request.user):
        return JsonResponse({"ok": False, "error": "Students only."}, status=403)
    lessons, full, limit, done_ids = _course_state(request.user)
    lesson = next((item for item in lessons if item.slug == slug), None)
    if lesson is None:
        raise Http404("Lesson not found")
    if lesson.is_locked:
        return JsonResponse({"ok": False, "error": "Available only to current SATMakon students."}, status=403)
    if request.POST.get("done", "1") == "0":
        AdmissionsLessonProgress.objects.filter(user=request.user, lesson=lesson).delete()
        done = False
    else:
        AdmissionsLessonProgress.objects.get_or_create(user=request.user, lesson=lesson)
        done = True
    if request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("accept", ""):
        total_done = AdmissionsLessonProgress.objects.filter(user=request.user, lesson__in=lessons).count()
        return JsonResponse({"ok": True, "done": done, "completed": total_done, "total": len(lessons)})
    return redirect("admissions_section_root", slug=lesson.slug)
