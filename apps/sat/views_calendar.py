"""V116: the student's calendar page and the .ics feed for Google / Apple Calendar."""
from datetime import date, timedelta
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from .calendar_models import StudentCalendarFeed
from .student_calendar import KINDS, events_for, ics_feed, month_grid
from .student_workspace import should_use_student_workspace, student_workspace_context

UPCOMING_DAYS = 14


def _month(value, today):
    try:
        year, month = (int(x) for x in str(value or "").split("-")[:2])
        if 2000 <= year <= 2100 and 1 <= month <= 12:
            return year, month
    except ValueError:
        pass
    return today.year, today.month


def _shift(year, month, delta):
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


@login_required(login_url="/login/")
def student_calendar(request):
    if not should_use_student_workspace(request.user):
        return redirect("student_dashboard_root")
    feed, _ = StudentCalendarFeed.objects.get_or_create(user=request.user)
    if request.method == "POST" and request.POST.get("action") == "reset_link":
        feed.reset()
        messages.success(request, "New calendar link made. The old link stops working: add the new one to your calendar app.")
        return redirect("student_calendar_root")

    today = timezone.localdate()
    year, month = _month(request.GET.get("month"), today)
    first = date(year, month, 1)
    grid_start = first - timedelta(days=first.weekday())
    grid_end = grid_start + timedelta(days=41)
    upcoming_end = today + timedelta(days=UPCOMING_DAYS - 1)
    events = events_for(request.user, min(grid_start, today), max(grid_end, upcoming_end))
    _, _, weeks = month_grid(year, month, [e for e in events if grid_start <= e.day <= grid_end], today)

    upcoming = []
    for event in events:
        if today <= event.day <= upcoming_end:
            if not upcoming or upcoming[-1]["date"] != event.day:
                upcoming.append({"date": event.day, "events": []})
            upcoming[-1]["events"].append(event)

    feed_url = f"{settings.SITE_URL}{reverse('student_calendar_feed', args=[feed.token])}"
    webcal_url = "webcal://" + feed_url.split("://", 1)[-1]
    prev_year, prev_month = _shift(year, month, -1)
    next_year, next_month = _shift(year, month, 1)
    context = student_workspace_context(request.user, active="calendar")
    context.update({
        "calendar_weeks": weeks,
        "calendar_month": first,
        "calendar_prev": f"{prev_year}-{prev_month:02d}",
        "calendar_next": f"{next_year}-{next_month:02d}",
        "calendar_this_month": today.year == year and today.month == month,
        "calendar_upcoming": upcoming,
        "today_date": today,
        "calendar_upcoming_days": UPCOMING_DAYS,
        "calendar_kinds": [(key, label, icon) for key, (label, icon) in KINDS.items()],
        "calendar_weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "feed_url": feed_url,
        "feed_webcal_url": webcal_url,
        "feed_google_url": "https://calendar.google.com/calendar/render?cid=" + quote(webcal_url, safe=""),
    })
    return render(request, "sat/student_calendar.html", context)


def student_calendar_feed(request, token):
    """Public by its secret link: calendar apps fetch it without signing in."""
    feed = StudentCalendarFeed.objects.filter(token=token, user__is_active=True).select_related("user").first()
    if feed is None:
        raise Http404("Unknown calendar link.")
    now = timezone.now()
    if not feed.last_fetched_at or now - feed.last_fetched_at > timedelta(minutes=30):
        StudentCalendarFeed.objects.filter(pk=feed.pk).update(last_fetched_at=now)
    response = HttpResponse(ics_feed(feed.user), content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = 'inline; filename="makonbook.ics"'
    response["Cache-Control"] = "private, max-age=900"
    response["X-Robots-Tag"] = "noindex"
    return response
