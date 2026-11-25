"""Lesson-day assessment policy and auditable missed assessments.

The source of lesson days is MANAGER-CONFIRMED schedules, not Hollihop's
possibly delayed attendance stream. Dates use Django's Asia/Tashkent timezone.

V107 rule: a teacher assesses every student at least TWO times in each Monday–Sunday
week, on any lesson days the teacher chooses (fewer when the week has fewer lessons).
An assessment counts only on its own lesson day, before 23:59:59. The week closes on
Sunday 23:59:59; each missing assessment of each student is a 2,000 UZS fine.

Every lesson day snapshots the class's students (``AssessmentObligation``), so a
student who joined later is never counted for earlier lessons. Fines from the earlier
"first three lessons, 5,000 UZS" rule stay as they were.
"""
from collections import defaultdict
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from apps.sat.models import ClassroomMembership, MakonNotification
from .models import (
    AssessmentCalendarException, AssessmentDailyReport, AssessmentObligation,
    AssessmentPenalty, AssessmentSchedule, RatingAssessment, TeacherAssessmentReminder,
)

ASSESSMENTS_PER_WEEK = 2
PENALTY_UZS = 2000
# Weeks before this Monday were settled day by day under the old rule.
WEEKLY_RULE_FROM = date(2026, 11, 23)
SETTLE_WEEKS_BACK = 8


def week_start(day):
    return day - timedelta(days=day.weekday())


def lesson_dates(schedule, from_date, to_date):
    """Verified actual meeting dates for one teacher, respecting cancellations."""
    if not schedule.enabled or to_date < schedule.starts_on:
        return []
    start = max(from_date, schedule.starts_on)
    end = min(to_date, schedule.ends_on) if schedule.ends_on else to_date
    if end < start:
        return []
    cancelled = set()
    added = set()
    for d, action in schedule.exceptions.filter(date__gte=start, date__lte=end).values_list('date', 'action'):
        (cancelled if action == AssessmentCalendarException.CANCELLED else added).add(d)
    weekdays = set(schedule.weekdays)
    days = []
    cur = start
    while cur <= end:
        if (cur.isoweekday() in weekdays and cur not in cancelled) or cur in added:
            days.append(cur)
        cur += timedelta(days=1)
    return days


def lesson_allowed(schedule, day):
    return bool(schedule and day in lesson_dates(schedule, day, day))


def week_lesson_dates(schedule, day):
    """All (not cancelled) lesson days of ``day``'s week."""
    monday = week_start(day)
    return lesson_dates(schedule, monday, monday + timedelta(days=6))


# Kept for callers from before V107: every lesson day of the week now counts.
required_lesson_dates = week_lesson_dates


def required_per_week(lesson_count):
    return min(ASSESSMENTS_PER_WEEK, lesson_count)


def today_assessment_state(classroom, teacher, now=None):
    now = now or timezone.now()
    today = timezone.localdate(now)
    schedule = AssessmentSchedule.objects.filter(classroom=classroom, teacher=teacher, enabled=True).first()
    allowed = lesson_allowed(schedule, today)
    # A lesson day counts towards the weekly minimum (and fines) once a manager turned fines on.
    required = allowed and schedule.fines_active_on(today)
    return schedule, allowed, required


def week_progress(schedule, student_ids, day=None):
    """How many valid assessments each student has this week, and how many are required."""
    day = day or timezone.localdate()
    if schedule is None:
        return {}, 0
    monday = week_start(day)
    days = week_lesson_dates(schedule, day)
    done = defaultdict(int)
    for student_id, lesson_date, assessed_at in RatingAssessment.objects.filter(
        classroom_id=schedule.classroom_id, teacher_id=schedule.teacher_id, student_id__in=list(student_ids),
        lesson_date__gte=monday, lesson_date__lte=monday + timedelta(days=6),
    ).values_list('student_id', 'lesson_date', 'assessed_at'):
        if lesson_date in days and timezone.localtime(assessed_at).date() == lesson_date:
            done[student_id] += 1
    return dict(done), required_per_week(len(days))


def prepare_today_obligations(day=None, schedule=None):
    """Snapshot today's students on every lesson day, never backdate.

    With a ``schedule`` argument only that classroom is prepared on a teacher
    request, avoiding N+1 work for the whole school. Celery prepares all.
    """
    today = timezone.localdate()
    day = day or today
    if day != today:
        raise ValueError('Obligations may only be prepared for the current day.')
    # V90: obligations (and therefore fines, reminders and reports) exist only
    # for schedules whose fines a manager has turned on.
    schedules = AssessmentSchedule.objects.filter(
        enabled=True, fines_enabled=True, classroom__is_active=True,
    ).select_related('classroom', 'teacher')
    if schedule is not None:
        schedules = schedules.filter(pk=schedule.pk)
    created = 0
    for entry in schedules:
        if not entry.teacher.is_active or not entry.fines_active_on(day) or not lesson_allowed(entry, day):
            continue
        # Ignore stale teacher mappings (e.g. Hollihop changed owners).
        if entry.classroom.teacher_id != entry.teacher_id and not ClassroomMembership.objects.filter(
            classroom=entry.classroom, user=entry.teacher, role='teacher', status='approved',
        ).exists():
            continue
        eligible = []
        for student_id, approved_at, requested_at in ClassroomMembership.objects.filter(
            classroom=entry.classroom, role='student', status='approved',
        ).values_list('user_id', 'approved_at', 'requested_at'):
            joined_at = approved_at or requested_at
            if joined_at and timezone.localtime(joined_at).date() >= day:
                continue
            eligible.append(student_id)
        if not eligible:
            continue
        existing = set(AssessmentObligation.objects.filter(
            schedule=entry, lesson_date=day, student_id__in=eligible,
        ).values_list('student_id', flat=True))
        missing = [student_id for student_id in eligible if student_id not in existing]
        if missing:
            AssessmentObligation.objects.bulk_create([
                AssessmentObligation(schedule=entry, student_id=student_id, lesson_date=day)
                for student_id in missing
            ], ignore_conflicts=True)
            created += len(missing)
    return created


def _closed_week_groups(cutoff, monday=None):
    """Snapshots of closed weeks grouped per (schedule, student, week).

    Yields ``(schedule, student_id, week_monday, obligations, assessed_days, required)``
    where ``obligations`` exclude cancelled lessons.
    """
    open_monday = week_start(cutoff)
    first = max(WEEKLY_RULE_FROM, open_monday - timedelta(weeks=SETTLE_WEEKS_BACK))
    qs = AssessmentObligation.objects.filter(lesson_date__gte=first, lesson_date__lt=open_monday)
    if monday is not None:
        qs = qs.filter(lesson_date__gte=monday, lesson_date__lte=monday + timedelta(days=6))
    obligations = list(qs.select_related('schedule').order_by('lesson_date'))
    if not obligations:
        return
    cancelled = set(AssessmentCalendarException.objects.filter(
        action=AssessmentCalendarException.CANCELLED,
        schedule_id__in={ob.schedule_id for ob in obligations},
        date__gte=first, date__lt=open_monday,
    ).values_list('schedule_id', 'date'))
    groups = defaultdict(list)
    for ob in obligations:
        if (ob.schedule_id, ob.lesson_date) in cancelled:
            continue
        groups[(ob.schedule_id, ob.student_id, week_start(ob.lesson_date))].append(ob)
    if not groups:
        return
    assessed = defaultdict(set)
    for classroom_id, teacher_id, student_id, lesson_date, assessed_at in RatingAssessment.objects.filter(
        student_id__in={key[1] for key in groups},
        lesson_date__gte=first, lesson_date__lt=open_monday,
    ).values_list('classroom_id', 'teacher_id', 'student_id', 'lesson_date', 'assessed_at'):
        if timezone.localtime(assessed_at).date() == lesson_date:
            assessed[(classroom_id, teacher_id, student_id)].add(lesson_date)
    for (schedule_id, student_id, monday_key), obs in groups.items():
        schedule = obs[0].schedule
        days = {ob.lesson_date for ob in obs}
        done_days = assessed[(schedule.classroom_id, schedule.teacher_id, student_id)] & days
        yield schedule, student_id, monday_key, obs, done_days, required_per_week(len(days))


def settle_missed_assessments(cutoff=None):
    """Fine missing weekly assessments of closed weeks only. Reentrant.

    A week is closed once ``cutoff`` (today) is past its Sunday. Each missing
    assessment of each student becomes one penalty on one of the student's
    unassessed lesson days of that week (the latest ones first). Penalties that
    already exist for that student and week count, so re-runs add nothing.
    """
    cutoff = cutoff or timezone.localdate()
    new = []
    with transaction.atomic():
        for _schedule, _student_id, _monday, obs, done_days, required in _closed_week_groups(cutoff):
            missing = required - len(done_days)
            if missing <= 0:
                continue
            ob_ids = [ob.pk for ob in obs]
            fined = set(AssessmentPenalty.objects.filter(obligation_id__in=ob_ids).values_list('obligation_id', flat=True))
            to_create = missing - len(fined)
            if to_create <= 0:
                continue
            candidates = [ob for ob in sorted(obs, key=lambda o: o.lesson_date, reverse=True)
                          if ob.lesson_date not in done_days and ob.pk not in fined]
            for ob in candidates[:to_create]:
                penalty, added = AssessmentPenalty.objects.get_or_create(
                    obligation=ob, defaults={'amount_uzs': PENALTY_UZS},
                )
                if added:
                    new.append(penalty)
    return new


# Late import avoids loading Django models in module scope before app registry is ready.
from django.db import models  # noqa: E402


def send_weekly_manager_report(monday):
    """Deliver exactly one summary for a closed week (Monday–Sunday)."""
    from django.contrib.auth.models import User
    from django.urls import reverse

    monday = week_start(monday)
    if monday + timedelta(days=6) >= timezone.localdate():
        return False
    expected = completed = missing = 0
    for _schedule, _student_id, _monday, _obs, done_days, required in _closed_week_groups(timezone.localdate(), monday=monday):
        expected += required
        completed += min(required, len(done_days))
        missing += max(0, required - len(done_days))
    if not expected:
        return False
    fines = AssessmentPenalty.objects.filter(
        obligation__lesson_date__gte=monday, obligation__lesson_date__lte=monday + timedelta(days=6),
    ).aggregate(total=models.Sum('amount_uzs'))['total'] or 0
    sunday = monday + timedelta(days=6)
    with transaction.atomic():
        dispatch, created = AssessmentDailyReport.objects.get_or_create(
            date=monday, defaults={'expected': expected, 'completed': completed, 'missed': missing},
        )
        if not created:
            return False
        managers = list(User.objects.filter(is_active=True).filter(
            models.Q(groups__name__iexact='Manager') | models.Q(is_superuser=True)
        ).distinct())
        MakonNotification.objects.bulk_create([
            MakonNotification(
                user=manager,
                type=MakonNotification.TYPE_ASSESSMENT,
                title=f'Assessment report for {monday:%d %b} – {sunday:%d %b %Y}',
                message=f'{expected} required student assessments · {completed} done · {missing} missing ({fines:,} UZS pending review).',
                url=reverse('manager_assessment_report') + f'?month={monday:%Y-%m}',
            ) for manager in managers
        ])
    return True


def send_daily_manager_report(report_date=None):
    """Kept for old callers: reports the closed week that contains ``report_date``."""
    day = report_date or (timezone.localdate() - timedelta(days=7))
    return send_weekly_manager_report(week_start(day))


def send_pending_daily_manager_reports():
    """Catch up after outages without duplicating already-sent weekly reports."""
    today = timezone.localdate()
    open_monday = week_start(today)
    sent = 0
    monday = max(week_start(WEEKLY_RULE_FROM), open_monday - timedelta(weeks=SETTLE_WEEKS_BACK))
    while monday < open_monday:
        if not AssessmentDailyReport.objects.filter(date=monday).exists():
            sent += int(send_weekly_manager_report(monday))
        monday += timedelta(weeks=1)
    return sent


def students_due_today(schedule, day):
    """Students who will be fined unless assessed today: the remaining lessons are not enough."""
    days = week_lesson_dates(schedule, day)
    if day not in days:
        return []
    remaining = len([d for d in days if d >= day])
    student_ids = list(AssessmentObligation.objects.filter(
        schedule=schedule, lesson_date=day,
    ).values_list('student_id', flat=True))
    done, required = week_progress(schedule, student_ids, day)
    assessed_today = set(RatingAssessment.objects.filter(
        classroom_id=schedule.classroom_id, teacher_id=schedule.teacher_id, lesson_date=day,
        student_id__in=student_ids,
    ).values_list('student_id', flat=True))
    return [
        student_id for student_id in student_ids
        if student_id not in assessed_today and required - done.get(student_id, 0) >= remaining
    ]


def send_teacher_evening_reminders(now=None):
    """Send at most one on-platform reminder per teacher and day.

    V107: only when a student would be fined unless assessed today, because the
    week's remaining lessons are no longer enough for two assessments. Runs via
    Celery Beat at 21:00 Asia/Tashkent; late retries before midnight are safe.
    """
    now = now or timezone.now()
    local_now = timezone.localtime(now)
    if local_now.hour < 21 or local_now.date() != timezone.localdate(now):
        return 0
    day = local_now.date()
    prepare_today_obligations(day=day)
    schedule_ids = set(AssessmentObligation.objects.filter(
        lesson_date=day, schedule__teacher__is_active=True,
    ).values_list('schedule_id', flat=True))
    pending_by_teacher = defaultdict(int)
    for schedule in AssessmentSchedule.objects.filter(pk__in=schedule_ids):
        due = students_due_today(schedule, day)
        if due:
            pending_by_teacher[schedule.teacher_id] += len(due)

    sent = 0
    for teacher_id, count in pending_by_teacher.items():
        with transaction.atomic():
            # Unique marker is committed with the notification; concurrent tasks
            # cannot deliver two reminder notifications on the same date.
            marker, created = TeacherAssessmentReminder.objects.get_or_create(
                teacher_id=teacher_id, date=day, defaults={'pending_count': count},
            )
            if not created:
                continue
            MakonNotification.objects.create(
                user_id=teacher_id, type=MakonNotification.TYPE_ASSESSMENT,
                title=f'21:00 · Assessment reminder · {day:%d.%m.%Y}',
                message=(f'{count} student(s) still need an assessment today to reach two this week. '
                         f'Complete them before 23:59:59 Tashkent time, otherwise {PENALTY_UZS:,} UZS per missing assessment.'),
                url='/teacher/assessments/',
            )
            sent += 1
    return sent
