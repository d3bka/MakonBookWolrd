"""V116: the student's calendar — lessons, homework deadlines, mock exams, support lessons
and SAT dates in one place, plus an .ics feed for Google / Apple Calendar.

* Lessons come from the class lesson schedule (Hollihop days, with the Hollihop lesson time
  when it is known; otherwise the lesson is an all-day entry), minus cancelled days and plus
  extra lessons the manager added.
* Homework: active assignments of the student's classes with a deadline (the same ones the
  Homework page shows); a submitted one is marked done.
* Mock exams the student registered for (confirmed), booked support lessons, official SAT
  dates and the student's own exam date from their goal.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone as dt_timezone

from django.conf import settings
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

KINDS = {
    "lesson": ("Lesson", "bi-easel2"),
    "homework": ("Homework deadline", "bi-list-check"),
    "exam": ("Mock exam", "bi-clipboard2-check"),
    "term": ("Mid/Final exam", "bi-journal-check"),
    "support": ("Support lesson", "bi-person-video3"),
    "sat": ("SAT date", "bi-flag"),
}
FEED_PAST_DAYS = 30
FEED_FUTURE_DAYS = 180


@dataclass
class Event:
    kind: str
    title: str
    day: date
    start: datetime | None = None   # None: all-day
    end: datetime | None = None
    subtitle: str = ""
    url: str = ""
    done: bool = False
    uid: str = ""

    @property
    def label(self):
        return KINDS[self.kind][0]

    @property
    def icon(self):
        return KINDS[self.kind][1]

    @property
    def all_day(self):
        return self.start is None

    @property
    def sort_key(self):
        moment = timezone.localtime(self.start).time() if self.start else time(0)
        return (self.day, 0 if self.all_day else 1, moment, self.title)


def _aware(day, hhmm):
    try:
        hour, minute = (int(x) for x in str(hhmm).split(":")[:2])
        return timezone.make_aware(datetime.combine(day, time(hour, minute)), timezone.get_current_timezone())
    except (TypeError, ValueError):
        return None


def _class_ids(user):
    from .models import ClassroomMembership

    return list(ClassroomMembership.objects.filter(
        user=user, role="student", status="approved", classroom__is_active=True,
    ).values_list("classroom_id", flat=True))


def lesson_events(user, start, end, class_ids=None):
    from apps.ratings.models import AssessmentCalendarException, AssessmentSchedule

    class_ids = _class_ids(user) if class_ids is None else class_ids
    schedules = list(AssessmentSchedule.objects.filter(classroom_id__in=class_ids, enabled=True).select_related("classroom"))
    exceptions = {}
    for exc in AssessmentCalendarException.objects.filter(schedule__in=schedules, date__gte=start, date__lte=end):
        exceptions[(exc.schedule_id, exc.date)] = exc.action
    seen = set()
    events = []
    for schedule in schedules:
        weekdays = {int(d) for d in (schedule.weekdays or []) if str(d).isdigit()}
        times = schedule.lesson_times or {}
        day = max(start, schedule.starts_on)
        last = min(end, schedule.ends_on) if schedule.ends_on else end
        while day <= last:
            action = exceptions.get((schedule.pk, day))
            planned = day.isoweekday() in weekdays
            if (planned and action != AssessmentCalendarException.CANCELLED) or action == AssessmentCalendarException.ADDED:
                key = (schedule.classroom_id, day)  # two teachers of one class: one lesson
                if key not in seen:
                    seen.add(key)
                    begin_end = times.get(str(day.isoweekday())) or []
                    begin = _aware(day, begin_end[0]) if begin_end else None
                    finish = _aware(day, begin_end[1]) if begin and len(begin_end) > 1 and begin_end[1] else None
                    events.append(Event(
                        "lesson", schedule.classroom.name, day, begin, finish or (begin + timedelta(minutes=90) if begin else None),
                        subtitle="Extra lesson" if action == AssessmentCalendarException.ADDED else "",
                        url=reverse("student_classrooms_root"), uid=f"lesson-{schedule.classroom_id}-{day:%Y%m%d}",
                    ))
            day += timedelta(days=1)
    # Cancelled days of classes still show, so the student knows there is no lesson.
    for (schedule_id, day), action in exceptions.items():
        schedule = next((s for s in schedules if s.pk == schedule_id), None)
        if (schedule and action == AssessmentCalendarException.CANCELLED and (schedule.classroom_id, day) not in seen
                and day.isoweekday() in {int(d) for d in (schedule.weekdays or []) if str(d).isdigit()}):
            seen.add((schedule.classroom_id, day))
            events.append(Event("lesson", schedule.classroom.name, day, subtitle="No lesson (cancelled)", done=True,
                                uid=f"lesson-{schedule.classroom_id}-{day:%Y%m%d}-cancelled"))
    return events


def homework_events(user, start, end, class_ids=None):
    from .models import ClassroomHomeworkAssignment, ClassroomHomeworkSubmission

    class_ids = _class_ids(user) if class_ids is None else class_ids
    since, until = _range(start, end)
    assignments = (
        ClassroomHomeworkAssignment.objects.filter(classroom_id__in=class_ids, is_active=True, due_at__gte=since, due_at__lt=until)
        .filter(Q(assign_all=True) | Q(assigned_students=user)).select_related("classroom").distinct()
    )
    submitted = set(ClassroomHomeworkSubmission.objects.filter(
        student=user, status=ClassroomHomeworkSubmission.STATUS_SUBMITTED, assignment__in=assignments,
    ).values_list("assignment_id", flat=True))
    events = []
    for assignment in assignments:
        due = timezone.localtime(assignment.due_at)
        events.append(Event(
            "homework", assignment.title, due.date(), due, due + timedelta(minutes=15),
            subtitle=assignment.classroom.name, url=reverse("student_homework_root"),
            done=assignment.pk in submitted, uid=f"homework-{assignment.pk}",
        ))
    return events


def exam_events(user, start, end):
    from .event_registration_models import EventRegistration

    since, until = _range(start, end)
    events = []
    for reg in EventRegistration.objects.filter(
        user=user, status__in=[EventRegistration.STATUS_CONFIRMED, EventRegistration.STATUS_ATTENDED],
        event__start_at__gte=since, event__start_at__lt=until,
    ).select_related("event"):
        event = reg.event
        begin = timezone.localtime(event.start_at)
        events.append(Event("exam", event.title, begin.date(), begin, timezone.localtime(event.end_at),
                            url=reverse("events"), done=reg.status == EventRegistration.STATUS_ATTENDED,
                            uid=f"exam-{event.pk}"))
    return events


def term_exam_events(user, start, end):
    """V117: Mid-term / Final sessions the student has a seat in."""
    from .exam_models import ExamSeat

    since, until = _range(start, end)
    events = []
    for seat in ExamSeat.objects.filter(
        student=user, session__starts_at__gte=since, session__starts_at__lt=until,
    ).exclude(status=ExamSeat.STATUS_MOVED).select_related("session", "session__exam"):
        session = seat.session
        begin = timezone.localtime(session.starts_at)
        title = f"{session.exam.get_kind_display()} · {session.get_subject_display()}" + (" (retake)" if session.is_retake else "")
        events.append(Event("term", title, begin.date(), begin, timezone.localtime(session.ends_at),
                            subtitle=session.room, url=reverse("student_exams_root"), uid=f"term-{session.pk}"))
    return events


def support_events(user, start, end):
    from .models import SupportLessonBooking

    since, until = _range(start, end)
    events = []
    for booking in SupportLessonBooking.objects.filter(
        student=user, status__in=[SupportLessonBooking.STATUS_SCHEDULED, SupportLessonBooking.STATUS_COMPLETED],
        start_at__gte=since, start_at__lt=until,
    ).select_related("teacher__user", "lesson_topic"):
        begin = timezone.localtime(booking.start_at)
        finish = timezone.localtime(booking.end_at) if booking.end_at else begin + timedelta(minutes=60)
        topic = getattr(booking.lesson_topic, "name", "") or "Support lesson"
        teacher = getattr(booking.teacher, "name", "") or ""
        events.append(Event("support", topic, begin.date(), begin, finish, subtitle=teacher,
                            url=reverse("my_support_lessons_root"),
                            done=booking.status == SupportLessonBooking.STATUS_COMPLETED, uid=f"support-{booking.pk}"))
    return events


def sat_events(user, start, end):
    from .models import OfficialSatDate, StudentGoalProfile

    goal = StudentGoalProfile.objects.filter(user=user).only("exam_date").first()
    my_date = goal.exam_date if goal else None
    events = []
    for row in OfficialSatDate.objects.filter(is_active=True, date__gte=start, date__lte=end):
        mine = row.date == my_date
        events.append(Event("sat", "My SAT exam" if mine else "SAT test day", row.date,
                            subtitle=row.note if not mine else "The date in your goal",
                            uid=f"sat-{row.date:%Y%m%d}"))
    if my_date and start <= my_date <= end and not any(e.day == my_date for e in events):
        events.append(Event("sat", "My SAT exam", my_date, subtitle="The date in your goal", uid=f"sat-mine-{my_date:%Y%m%d}"))
    return events


def _range(start, end):
    tz = timezone.get_current_timezone()
    return (timezone.make_aware(datetime.combine(start, time.min), tz),
            timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min), tz))


def events_for(user, start, end):
    class_ids = _class_ids(user)
    events = (
        lesson_events(user, start, end, class_ids) + homework_events(user, start, end, class_ids)
        + exam_events(user, start, end) + term_exam_events(user, start, end) + support_events(user, start, end)
        + sat_events(user, start, end)
    )
    return sorted(events, key=lambda e: e.sort_key)


# ------------------------------------------------------------------ month grid

def month_grid(year, month, events, today):
    first = date(year, month, 1)
    start = first - timedelta(days=first.weekday())
    next_month = date(year + (month == 12), month % 12 + 1, 1)
    end = next_month - timedelta(days=1)
    end = end + timedelta(days=6 - end.weekday())
    by_day = {}
    for event in events:
        by_day.setdefault(event.day, []).append(event)
    weeks, day = [], start
    while day <= end:
        week = []
        for _ in range(7):
            week.append({"date": day, "in_month": day.month == month, "today": day == today, "events": by_day.get(day, [])})
            day += timedelta(days=1)
        weeks.append(week)
    return start, end, weeks


# ------------------------------------------------------------------ .ics feed

def _ics_text(value):
    return (str(value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def _fold(line):
    """RFC 5545: lines longer than 75 octets continue on the next line after a space."""
    data = line.encode("utf-8")
    if len(data) <= 75:
        return line
    parts, current = [], b""
    for char in line:
        encoded = char.encode("utf-8")
        if len(current) + len(encoded) > (75 if not parts else 74):
            parts.append(current.decode("utf-8"))
            current = b""
        current += encoded
    parts.append(current.decode("utf-8"))
    return "\r\n ".join(parts)


def _utc(value):
    return value.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ics_feed(user, today=None):
    today = today or timezone.localdate()
    events = events_for(user, today - timedelta(days=FEED_PAST_DAYS), today + timedelta(days=FEED_FUTURE_DAYS))
    domain = getattr(settings, "SITE_DOMAIN", "makonbook") or "makonbook"
    stamp = _utc(timezone.now())
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//MakonBook//Student calendar//EN", "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH", "X-WR-CALNAME:MakonBook", "X-WR-TIMEZONE:Asia/Tashkent", "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
    ]
    for event in events:
        uid = hashlib.sha1(f"{user.pk}:{event.uid}".encode()).hexdigest()[:20]
        summary = event.title
        if event.kind == "homework":
            summary = f"Homework due: {event.title}" + (" ✓" if event.done else "")
        elif event.kind == "lesson" and event.subtitle.startswith("No lesson"):
            summary = f"No lesson: {event.title}"
        elif event.kind == "exam":
            summary = f"Mock exam: {event.title}"
        elif event.kind == "term":
            summary = f"Exam: {event.title}"
        elif event.kind == "support":
            summary = f"Support lesson: {event.title}"
        lines += ["BEGIN:VEVENT", f"UID:{uid}@{domain}", f"DTSTAMP:{stamp}"]
        if event.all_day:
            lines += [f"DTSTART;VALUE=DATE:{event.day:%Y%m%d}", f"DTEND;VALUE=DATE:{event.day + timedelta(days=1):%Y%m%d}",
                      "TRANSP:TRANSPARENT"]
        else:
            lines += [f"DTSTART:{_utc(event.start)}", f"DTEND:{_utc(event.end or event.start + timedelta(minutes=30))}"]
        lines.append(f"SUMMARY:{_ics_text(summary)}")
        description = " · ".join(x for x in (event.label, event.subtitle) if x)
        if description:
            lines.append(f"DESCRIPTION:{_ics_text(description)}")
        if event.url:
            lines.append(f"URL:{settings.SITE_URL}{event.url}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
