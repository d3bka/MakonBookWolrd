"""V91: teachers report cancelled or covered lessons; managers approve; reports.

Rules agreed with SATMakon:
* A teacher reports only for today or a future day on which their schedule has a lesson.
* Every manager is notified. Approval turns the day into a "cancelled" calendar exception,
  so the lesson is not mandatory and no fine is created; a fine that was already created
  for that day (approval after the nightly settlement) is waived automatically.
* A cover ("another teacher covers") is treated as a cancellation for the scheduled
  teacher. The cover teacher is only recorded for the reports.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import MakonNotification

from .assessment_policy import lesson_dates
from .models import AssessmentCalendarException, AssessmentPenalty, LessonChangeRequest

UPCOMING_DAYS = 21


def _name(user):
    return (user.get_full_name() or user.username) if user else ''


def upcoming_lesson_dates(schedule, *, days=UPCOMING_DAYS):
    today = timezone.localdate()
    return lesson_dates(schedule, today, today + timedelta(days=days))


def _managers():
    return User.objects.filter(is_active=True).filter(
        models.Q(groups__name__iexact='Manager') | models.Q(is_superuser=True)
    ).distinct()


def request_change(schedule, *, day, kind, reason, requested_by, cover_teacher=None, cover_name=''):
    reason = (reason or '').strip()
    cover_name = (cover_name or '').strip()[:150]
    if requested_by.pk != schedule.teacher_id:
        raise ValidationError('Only the scheduled teacher can report a change for this class.')
    if kind not in (LessonChangeRequest.CANCEL, LessonChangeRequest.COVER):
        raise ValidationError('Choose what happened to the lesson.')
    if day < timezone.localdate():
        raise ValidationError('Changes can be reported only for today or a future lesson.')
    if day not in lesson_dates(schedule, day, day):
        raise ValidationError('There is no scheduled lesson on that day (or it is already cancelled).')
    if len(reason) < 3:
        raise ValidationError('Write a short reason.')
    if kind == LessonChangeRequest.COVER:
        if cover_teacher is not None and cover_teacher.pk == schedule.teacher_id:
            raise ValidationError('Choose the teacher who covers the lesson, not yourself.')
        if cover_teacher is None and not cover_name:
            raise ValidationError('Choose or type the teacher who covers the lesson.')
    else:
        cover_teacher, cover_name = None, ''
    try:
        with transaction.atomic():
            change = LessonChangeRequest.objects.create(
                schedule=schedule, date=day, kind=kind, reason=reason[:300], requested_by=requested_by,
                cover_teacher=cover_teacher, cover_name=cover_name,
            )
            url = reverse('manager_assessment_schedules') + '#requests'
            what = 'cancelled' if kind == LessonChangeRequest.CANCEL else f'covered by {change.cover_label}'
            MakonNotification.objects.bulk_create([
                MakonNotification(
                    user=manager, type=MakonNotification.TYPE_ASSESSMENT,
                    title=f'Lesson change: {schedule.classroom.name}, {day:%d %b}',
                    message=f'{_name(requested_by)} reports the lesson is {what}. Reason: {reason[:160]}',
                    url=url,
                ) for manager in _managers()
            ])
    except IntegrityError as exc:
        raise ValidationError('A request for this lesson is already waiting for a manager.') from exc
    return change


def decide(change, *, approve, manager, note=''):
    note = (note or '').strip()[:300]
    with transaction.atomic():
        change = LessonChangeRequest.objects.select_for_update().select_related('schedule__classroom').get(pk=change.pk)
        if change.status != LessonChangeRequest.PENDING:
            raise ValidationError('This request was already decided.')
        change.status = LessonChangeRequest.APPROVED if approve else LessonChangeRequest.REJECTED
        change.decided_by = manager
        change.decided_at = timezone.now()
        change.decision_note = note
        change.save(update_fields=['status', 'decided_by', 'decided_at', 'decision_note'])
        waived = 0
        if approve:
            label = 'Cancelled' if change.kind == LessonChangeRequest.CANCEL else f'Covered by {change.cover_label}'
            AssessmentCalendarException.objects.update_or_create(
                schedule=change.schedule, date=change.date,
                defaults={'action': AssessmentCalendarException.CANCELLED,
                          'reason': f'{label}: {change.reason}'[:220], 'changed_by': manager},
            )
            waived = AssessmentPenalty.objects.filter(
                obligation__schedule=change.schedule, obligation__lesson_date=change.date,
                status=AssessmentPenalty.OPEN,
            ).update(
                status=AssessmentPenalty.WAIVED, reviewed_by=manager, reviewed_at=timezone.now(),
                review_note=f'Lesson change #{change.pk} approved ({label.lower()}).'[:500],
            )
        verdict = 'approved' if approve else 'rejected'
        MakonNotification.objects.create(
            user=change.requested_by, type=MakonNotification.TYPE_ASSESSMENT,
            title=f'Lesson change {verdict}: {change.schedule.classroom.name}, {change.date:%d %b}',
            message=(('No assessments are required that day.' if approve else 'The lesson stays mandatory.')
                     + (f' Note: {note}' if note else '')),
            url=reverse('teacher_classroom_assessments_root', args=[change.schedule.classroom_id]),
        )
    return change, waived


def withdraw(change, *, user):
    if change.requested_by_id != user.pk:
        raise ValidationError('Only the teacher who sent the request can withdraw it.')
    updated = LessonChangeRequest.objects.filter(pk=change.pk, status=LessonChangeRequest.PENDING).update(
        status=LessonChangeRequest.WITHDRAWN, decided_at=timezone.now(),
    )
    if not updated:
        raise ValidationError('This request was already decided.')


# ---------------------------------------------------------------- reports

def monthly_rows(start, end):
    """Every lesson change in the month: teacher requests plus exceptions a manager set directly."""
    rows = []
    requests = (LessonChangeRequest.objects.filter(date__range=(start, end))
                .select_related('schedule__classroom', 'schedule__teacher', 'cover_teacher', 'decided_by', 'requested_by'))
    from_requests = set()
    for change in requests:
        if change.status == LessonChangeRequest.APPROVED:
            from_requests.add((change.schedule_id, change.date))
        rows.append({
            'date': change.date, 'classroom': change.schedule.classroom.name, 'teacher': change.schedule.teacher,
            'kind': change.get_kind_display(), 'kind_key': change.kind, 'cover': change.cover_label,
            'reason': change.reason, 'status': change.get_status_display(), 'status_key': change.status,
            'source': 'Teacher request', 'decided_by': _name(change.decided_by), 'note': change.decision_note,
            'reported_at': change.created_at,
        })
    exceptions = (AssessmentCalendarException.objects.filter(date__range=(start, end))
                  .select_related('schedule__classroom', 'schedule__teacher', 'changed_by'))
    for exception in exceptions:
        if (exception.schedule_id, exception.date) in from_requests:
            continue
        rows.append({
            'date': exception.date, 'classroom': exception.schedule.classroom.name, 'teacher': exception.schedule.teacher,
            'kind': exception.get_action_display(), 'kind_key': exception.action, 'cover': '',
            'reason': exception.reason, 'status': 'Set by manager', 'status_key': 'manager',
            'source': 'Manager', 'decided_by': _name(exception.changed_by), 'note': '', 'reported_at': exception.created_at,
        })
    rows.sort(key=lambda row: (row['date'], row['classroom'], _name(row['teacher'])))
    return rows


def summary_by_teacher(rows):
    totals = OrderedDict()
    for row in sorted(rows, key=lambda r: _name(r['teacher']).casefold()):
        bucket = totals.setdefault(row['teacher'].pk, {
            'teacher': row['teacher'], 'cancelled': 0, 'covered': 0, 'manager': 0, 'pending': 0, 'rejected': 0,
        })
        if row['status_key'] == LessonChangeRequest.APPROVED:
            bucket['covered' if row['kind_key'] == LessonChangeRequest.COVER else 'cancelled'] += 1
        elif row['status_key'] == 'manager':
            bucket['manager'] += 1
        elif row['status_key'] == LessonChangeRequest.PENDING:
            bucket['pending'] += 1
        elif row['status_key'] == LessonChangeRequest.REJECTED:
            bucket['rejected'] += 1
    return list(totals.values())


def lessons_held(schedules, start, end):
    """Scheduled minus cancelled lessons per teacher in the month (up to today)."""
    today = timezone.localdate()
    held = {}
    for schedule in schedules:
        held[schedule.teacher_id] = held.get(schedule.teacher_id, 0) + len(lesson_dates(schedule, start, min(end, today)))
    return held

