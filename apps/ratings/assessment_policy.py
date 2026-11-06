"""V61: strict lesson-day assessment policy and auditable missed assessments.

The source of lesson days is MANAGER-CONFIRMED schedules, not Hollihop's
possibly delayed attendance stream. Dates use Django's Asia/Tashkent timezone.
Only the first THREE real lessons in each Monday--Sunday week are mandatory.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.sat.models import ClassroomMembership, MakonNotification
from .models import (
    AssessmentCalendarException, AssessmentDailyReport, AssessmentObligation,
    AssessmentPenalty, AssessmentSchedule, RatingAssessment, TeacherAssessmentReminder,
)

ASSESSMENTS_PER_WEEK = 3
PENALTY_UZS = 5000


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


def required_lesson_dates(schedule, day):
    monday = week_start(day)
    return lesson_dates(schedule, monday, monday + timedelta(days=6))[:ASSESSMENTS_PER_WEEK]


def today_assessment_state(classroom, teacher, now=None):
    now = now or timezone.now()
    today = timezone.localdate(now)
    schedule = AssessmentSchedule.objects.filter(classroom=classroom, teacher=teacher, enabled=True).first()
    allowed = lesson_allowed(schedule, today)
    required = allowed and today in required_lesson_dates(schedule, today)
    return schedule, allowed, required


def prepare_today_obligations(day=None, schedule=None):
    """Snapshot today's students for first-three lessons, never backdate.

    With a ``schedule`` argument only that classroom is prepared on a teacher
    request, avoiding N+1 work for the whole school. Celery prepares all.
    """
    today = timezone.localdate()
    day = day or today
    if day != today:
        raise ValueError('Obligations may only be prepared for the current day.')
    schedules = AssessmentSchedule.objects.filter(enabled=True, classroom__is_active=True).select_related('classroom', 'teacher')
    if schedule is not None:
        schedules = schedules.filter(pk=schedule.pk)
    created = 0
    for entry in schedules:
        if not entry.teacher.is_active or day not in required_lesson_dates(entry, day):
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


def settle_missed_assessments(cutoff=None):
    """Close ONLY snapshotted prior days, never bill uncaptured sessions.

    Returns newly created fine count, sum and per-teacher totals. Reentrant.
    """
    cutoff = cutoff or timezone.localdate()
    obligations = AssessmentObligation.objects.filter(lesson_date__lt=cutoff).select_related('schedule')
    new = []
    with transaction.atomic():
        for ob in obligations.iterator(chunk_size=500):
            if AssessmentPenalty.objects.filter(obligation_id=ob.pk).exists():
                continue
            # Manager cancelled a meeting before settlement: not billable.
            # The recurring schedule may have CHANGED since the dated snapshot;
            # never reinterpret historical obligations from today's weekdays.
            if ob.schedule.exceptions.filter(date=ob.lesson_date, action='cancelled').exists():
                continue
            assessed = RatingAssessment.objects.filter(
                classroom_id=ob.schedule.classroom_id,
                teacher_id=ob.schedule.teacher_id,
                student_id=ob.student_id,
                lesson_date=ob.lesson_date,
                assessed_at__date=ob.lesson_date,
            ).exists()
            if assessed:
                continue
            penalty, added = AssessmentPenalty.objects.get_or_create(
                obligation=ob, defaults={'amount_uzs': PENALTY_UZS},
            )
            if added:
                new.append(penalty)
    return new




# Late import avoids loading Django models in module scope before app registry is ready.
from django.db import models  # noqa: E402


def send_daily_manager_report(report_date=None):
    """Deliver exactly one daily management summary for a closed date.

    Marker and notifications commit atomically; retries cannot duplicate mail.
    """
    from django.contrib.auth.models import User
    from django.urls import reverse
    day = report_date or (timezone.localdate() - timedelta(days=1))
    if day >= timezone.localdate():
        return False
    obligations = list(AssessmentObligation.objects.filter(lesson_date=day).select_related('schedule'))
    # Cancelled lesson obligations may exist as a dated snapshot but are
    # neither billable nor part of the completion denominator.
    cancelled_ids = set(AssessmentCalendarException.objects.filter(
        date=day, action=AssessmentCalendarException.CANCELLED,
    ).values_list('schedule_id', flat=True))
    obligations = [ob for ob in obligations if ob.schedule_id not in cancelled_ids]
    expected = len(obligations)
    if not expected:
        return False
    submitted = set(RatingAssessment.objects.filter(lesson_date=day).values_list(
        'classroom_id', 'teacher_id', 'student_id',
    ))
    completed = sum(
        (ob.schedule.classroom_id, ob.schedule.teacher_id, ob.student_id) in submitted
        for ob in obligations
    )
    missed = AssessmentPenalty.objects.filter(obligation__lesson_date=day).count()
    # Do not publish misleading numbers if settlement failed or is in progress.
    if completed + missed != expected:
        return False
    with transaction.atomic():
        dispatch, created = AssessmentDailyReport.objects.get_or_create(
            date=day, defaults={'expected': expected, 'completed': completed, 'missed': missed},
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
                title=f'Assessment report for {day:%d %b %Y}',
                message=f'{expected} required student scores · {completed} completed · {missed} missed ({missed * PENALTY_UZS:,} UZS pending review).',
                url=reverse('manager_assessment_report') + f'?month={day:%Y-%m}',
            ) for manager in managers
        ])
    return True


def send_pending_daily_manager_reports():
    """Catch up after outages without duplicating already-sent daily reports."""
    today = timezone.localdate()
    sent = 0
    candidate_days = AssessmentObligation.objects.filter(
        lesson_date__lt=today, lesson_date__gte=today - timedelta(days=90),
    ).order_by('lesson_date').values_list('lesson_date', flat=True).distinct()
    processed = set(AssessmentDailyReport.objects.filter(
        date__lt=today, date__gte=today - timedelta(days=90),
    ).values_list('date', flat=True))
    for day in candidate_days:
        if day not in processed:
            sent += int(send_daily_manager_report(day))
    return sent


def send_teacher_evening_reminders(now=None):
    """Send exactly one on-platform reminder per teacher with pending mandatory assessments.

    Only today's snapshotted obligations count. Run via Celery Beat at 21:00
    Asia/Tashkent; late retries before midnight are safe and idempotent.
    No message is sent for cancelled lessons or completed classes.
    """
    from collections import defaultdict
    from django.db.models import Q

    now = now or timezone.now()
    local_now = timezone.localtime(now)
    if local_now.hour < 21 or local_now.date() != timezone.localdate(now):
        return 0
    day = local_now.date()
    prepare_today_obligations(day=day)
    cancelled = set(AssessmentCalendarException.objects.filter(
        date=day, action=AssessmentCalendarException.CANCELLED,
    ).values_list('schedule_id', flat=True))
    obligations = AssessmentObligation.objects.filter(
        lesson_date=day, schedule__teacher__is_active=True,
    ).select_related('schedule')
    assessed = set(RatingAssessment.objects.filter(lesson_date=day).values_list(
        'classroom_id', 'teacher_id', 'student_id',
    ))
    pending_by_teacher = defaultdict(int)
    for ob in obligations.iterator(chunk_size=500):
        if ob.schedule_id in cancelled:
            continue
        if (ob.schedule.classroom_id, ob.schedule.teacher_id, ob.student_id) not in assessed:
            pending_by_teacher[ob.schedule.teacher_id] += 1

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
                message=(f'{count} student assessment(s) still missing today. '
                         'Complete them before 23:59:59 Tashkent time.'),
                url='/teacher/assessments/',
            )
            sent += 1
    return sent
