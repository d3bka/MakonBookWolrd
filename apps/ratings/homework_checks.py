"""V107: homework check at every lesson.

At each lesson the teacher marks who did NOT do the homework; everybody else did. A
lesson without a saved check counts as "everyone did it" (no fine). Marks are saved on
the lesson day only, until 23:59:59 Asia/Tashkent, like assessments.

The marks are shown to the student, the parent, in "Needs attention" and in the
manager's assessment report.
"""
from collections import defaultdict
from datetime import timedelta

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from apps.sat.models import ClassroomMembership

from .models import AssessmentSchedule, LessonHomeworkCheck, LessonHomeworkMiss


def save_check(classroom, teacher, not_done_ids, day=None):
    """Replace today's check for ``classroom``. Only approved students of the class count."""
    day = day or timezone.localdate()
    members = set(ClassroomMembership.objects.filter(
        classroom=classroom, role='student', status='approved',
    ).values_list('user_id', flat=True))
    not_done = sorted({int(i) for i in not_done_ids if str(i).isdecimal() and int(i) in members})
    with transaction.atomic():
        check, _ = LessonHomeworkCheck.objects.update_or_create(
            classroom=classroom, lesson_date=day, defaults={'teacher': teacher},
        )
        check.misses.all().delete()
        LessonHomeworkMiss.objects.bulk_create([LessonHomeworkMiss(homework_check=check, student_id=s) for s in not_done])
    return check, not_done


def today_check(classroom, day=None):
    day = day or timezone.localdate()
    check = LessonHomeworkCheck.objects.filter(classroom=classroom, lesson_date=day).first()
    not_done = set(check.misses.values_list('student_id', flat=True)) if check else set()
    return check, not_done


def student_misses(student, days=30):
    """The lessons in the last ``days`` days where ``student`` did not do the homework."""
    since = timezone.localdate() - timedelta(days=days)
    return list(
        LessonHomeworkMiss.objects.filter(student=student, homework_check__lesson_date__gte=since)
        .select_related('homework_check__classroom')
        .order_by('-homework_check__lesson_date')
    )


def misses_by_class_student(classroom_ids, since):
    """{(classroom_id, student_id): [dates]} for "Needs attention"."""
    result = defaultdict(list)
    for classroom_id, student_id, lesson_date in LessonHomeworkMiss.objects.filter(
        homework_check__classroom_id__in=list(classroom_ids), homework_check__lesson_date__gte=since,
    ).values_list('homework_check__classroom_id', 'student_id', 'homework_check__lesson_date'):
        result[(classroom_id, student_id)].append(lesson_date)
    return result


def class_summary(start, end):
    """Per class and teacher: lessons, saved checks, misses and the share of homework done."""
    from .assessment_policy import lesson_dates

    today = timezone.localdate()
    last = min(end, today)
    rows = []
    schedules = AssessmentSchedule.objects.filter(enabled=True, classroom__is_active=True).select_related('classroom', 'teacher')
    checks = defaultdict(list)
    for check in LessonHomeworkCheck.objects.filter(lesson_date__range=(start, last)).prefetch_related('misses'):
        checks[check.classroom_id].append(check)
    students = dict(
        ClassroomMembership.objects.filter(role='student', status='approved', classroom__is_active=True)
        .values('classroom_id').annotate(n=Count('id'))
        .values_list('classroom_id', 'n')
    )
    for schedule in schedules:
        days = lesson_dates(schedule, start, last) if last >= start else []
        if not days:
            continue
        class_checks = checks.get(schedule.classroom_id, [])
        misses = sum(len(c.misses.all()) for c in class_checks)
        student_count = students.get(schedule.classroom_id, 0)
        possible = student_count * len(days)
        rows.append({
            'classroom': schedule.classroom, 'teacher': schedule.teacher, 'lessons': len(days),
            'checked': len(class_checks), 'misses': misses, 'students': student_count,
            'done_percent': round(100 * (possible - misses) / possible) if possible else None,
        })
    rows.sort(key=lambda r: (r['done_percent'] if r['done_percent'] is not None else 101, r['classroom'].name))
    return rows
