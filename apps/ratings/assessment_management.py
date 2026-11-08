"""Manager-only V61 schedule, compliance, Excel and actual-user dashboards."""
from collections import defaultdict
from datetime import date, timedelta
from io import BytesIO
from calendar import monthrange

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.sat.models import Classroom
from apps.sat.roles import is_manager, is_platform_admin
from .assessment_policy import (
    ASSESSMENTS_PER_WEEK, PENALTY_UZS, lesson_dates, prepare_today_obligations,
    settle_missed_assessments, send_pending_daily_manager_reports,
)
from .models import (
    AssessmentCalendarException, AssessmentObligation, AssessmentPenalty,
    AssessmentSchedule, UserActivityDay,
)


def _manager(user):
    return is_manager(user) or is_platform_admin(user)


def _month_value(value):
    try:
        y, m = (int(x) for x in value.split('-'))
        return date(y, m, 1)
    except (ValueError, TypeError, AttributeError):
        return timezone.localdate().replace(day=1)


def _month_interval(value):
    start = _month_value(value)
    return start, date(start.year, start.month, monthrange(start.year, start.month)[1])


@login_required

def manager_assessment_schedules(request):
    if not _manager(request.user):
        return HttpResponseForbidden('Manager access required.')
    schedules = list(AssessmentSchedule.objects.select_related('teacher', 'classroom').prefetch_related('exceptions').order_by('classroom__name', 'teacher__username'))
    classrooms = list(Classroom.objects.filter(is_active=True).select_related('teacher').prefetch_related('memberships').order_by('name'))
    for classroom in classrooms:
        teacher_ids = {classroom.teacher_id} | {m.user_id for m in classroom.memberships.all() if m.role == 'teacher' and m.status == 'approved'}
        classroom.teacher_options = User.objects.filter(pk__in=teacher_ids, is_active=True).order_by('first_name', 'username')
    today = timezone.localdate()
    return render(request, 'ratings/manager_assessment_schedules.html', {
        'schedules': schedules, 'classrooms': classrooms, 'today': today,
        'weekdays': [(1, 'Mon'), (2, 'Tue'), (3, 'Wed'), (4, 'Thu'), (5, 'Fri'), (6, 'Sat'), (7, 'Sun')],
    })


@login_required
@require_POST
def manager_save_schedule(request):
    if not _manager(request.user):
        return HttpResponseForbidden('Manager access required.')
    classroom = get_object_or_404(Classroom, pk=request.POST.get('classroom_id'), is_active=True)
    teacher = get_object_or_404(User, pk=request.POST.get('teacher_id'), is_active=True)
    try:
        weekdays = sorted({int(x) for x in request.POST.getlist('weekdays')})
        start = date.fromisoformat(request.POST.get('starts_on', ''))
        if start < timezone.localdate():
            raise ValueError('Start date cannot be in the past.')
        end = date.fromisoformat(request.POST['ends_on']) if request.POST.get('ends_on') else None
    except (ValueError, TypeError) as exc:
        messages.error(request, f'Invalid schedule: {exc}')
        return redirect('manager_assessment_schedules')
    old = AssessmentSchedule.objects.filter(classroom=classroom, teacher=teacher).first()
    # Once obligations exist, the effective start date and historical record
    # must not be rewritten. Changing recurring weekdays affects future only.
    if old and old.obligations.exists() and start != old.starts_on:
        # Preserve historical effective start; otherwise changing date would
        # rewrite the interpretation of prior obligation snapshots.
        start = old.starts_on
    schedule = old or AssessmentSchedule(classroom=classroom, teacher=teacher)
    schedule.weekdays = weekdays
    schedule.starts_on = start
    schedule.ends_on = end
    schedule.enabled = request.POST.get('enabled') == '1'
    schedule.approved_by = request.user
    try:
        schedule.full_clean()
        schedule.save()
    except ValidationError as exc:
        messages.error(request, f'Invalid schedule: {exc}')
        return redirect('manager_assessment_schedules')
    messages.success(request, 'Assessment schedule saved. New rules take effect on the selected dates.')
    return redirect('manager_assessment_schedules')


@login_required
@require_POST
def manager_schedule_exception(request, schedule_id):
    if not _manager(request.user):
        return HttpResponseForbidden('Manager access required.')
    schedule = get_object_or_404(AssessmentSchedule, pk=schedule_id)
    try:
        day = date.fromisoformat(request.POST.get('date', ''))
    except ValueError:
        messages.error(request, 'Invalid lesson date.')
        return redirect('manager_assessment_schedules')
    if day < timezone.localdate():
        messages.error(request, 'Historical dates cannot be changed. Waive incorrect penalties with an audit note.')
        return redirect('manager_assessment_schedules')
    action = request.POST.get('action')
    if action == 'delete':
        AssessmentCalendarException.objects.filter(schedule=schedule, date=day).delete()
    elif action in (AssessmentCalendarException.CANCELLED, AssessmentCalendarException.ADDED):
        AssessmentCalendarException.objects.update_or_create(
            schedule=schedule, date=day,
            defaults={'action': action, 'reason': request.POST.get('reason', '')[:220], 'changed_by': request.user},
        )
    else:
        messages.error(request, 'Invalid calendar action.')
        return redirect('manager_assessment_schedules')
    messages.success(request, 'Calendar exception updated.')
    return redirect('manager_assessment_schedules')


def _fine_queryset(start, end):
    return AssessmentPenalty.objects.filter(
        obligation__lesson_date__range=(start, end),
    ).select_related('obligation__schedule__teacher', 'obligation__schedule__classroom', 'obligation__student', 'reviewed_by').order_by('obligation__schedule__teacher__username', 'obligation__lesson_date', 'obligation__student__username')


def _fines_and_summary(start, end):
    fines = list(_fine_queryset(start, end))
    totals = {}
    for fine in fines:
        s = fine.obligation.schedule
        bucket = totals.setdefault(s.teacher_id, {'teacher': s.teacher, 'count': 0, 'open': 0, 'amount': 0})
        bucket['count'] += 1
        if fine.status == AssessmentPenalty.OPEN:
            bucket['open'] += 1
            bucket['amount'] += fine.amount_uzs
    return fines, sorted(totals.values(), key=lambda row: (-row['amount'], row['teacher'].username))


@login_required
def manager_assessment_report(request):
    if not _manager(request.user):
        return HttpResponseForbidden('Manager access required.')
    start, end = _month_interval(request.GET.get('month'))
    fines, totals = _fines_and_summary(start, end)
    today = timezone.localdate()
    expected = AssessmentObligation.objects.filter(lesson_date__range=(start, min(end, today))).count()
    schedules = AssessmentSchedule.objects.filter(enabled=True, classroom__is_active=True).select_related('classroom', 'teacher')
    underscheduled = []
    # Highlight impossible three-days/week targets (no invented penalties).
    monday = start - timedelta(days=start.weekday())
    while monday <= min(end, today):
        for schedule in schedules:
            days = lesson_dates(schedule, max(start, monday), min(end, monday + timedelta(days=6)))
            if days and len(days) < ASSESSMENTS_PER_WEEK:
                underscheduled.append((schedule, monday, len(days)))
        monday += timedelta(days=7)
    return render(request, 'ratings/manager_assessment_report.html', {
        'month': start.strftime('%Y-%m'), 'start': start, 'end': end,
        'fines': fines[:1000], 'total_rows': len(fines), 'totals': totals,
        'open_amount': sum(t['amount'] for t in totals), 'open_count': sum(t['open'] for t in totals),
        'expected': expected, 'under_scheduled': underscheduled[:50], 'today': today,
    })


@login_required
@require_POST
def manager_review_penalty(request, penalty_id):
    if not _manager(request.user):
        return HttpResponseForbidden('Manager access required.')
    fine = get_object_or_404(AssessmentPenalty, pk=penalty_id)
    status = request.POST.get('status')
    reason = request.POST.get('note', '').strip()
    if status not in (AssessmentPenalty.OPEN, AssessmentPenalty.WAIVED):
        return HttpResponseForbidden('Invalid status')
    if status == AssessmentPenalty.WAIVED and not reason:
        messages.error(request, 'Waiving a fine requires a written reason.')
    else:
        fine.status = status
        fine.reviewed_by = request.user
        fine.reviewed_at = timezone.now()
        fine.review_note = reason[:500]
        fine.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_note'])
        messages.success(request, 'Penalty review saved.')
    return redirect(f'{reverse("manager_assessment_report")}?month={fine.obligation.lesson_date:%Y-%m}')


@login_required
@require_POST
def manager_run_assessment_settlement(request):
    if not _manager(request.user):
        return HttpResponseForbidden('Manager access required.')
    prepared = prepare_today_obligations()
    fines = settle_missed_assessments()
    send_pending_daily_manager_reports()
    messages.success(request, f'Prepared {prepared} student obligations; detected {len(fines)} new missed assessments.')
    return redirect('manager_assessment_report')


@login_required
def manager_penalties_xlsx(request):
    if not _manager(request.user):
        return HttpResponseForbidden('Manager access required.')
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    start, end = _month_interval(request.GET.get('month'))
    fines, totals = _fines_and_summary(start, end)
    wb = Workbook()
    def safe_excel(value):
        value = str(value or '')
        return "'" + value if value.startswith(('=', '+', '-', '@')) else value
    summary = wb.active
    summary.title = 'By Teacher'
    summary.append(['Teacher', 'Total incidents', 'Pending incidents', 'Pending UZS'])
    for row in totals:
        summary.append([safe_excel(row['teacher'].get_full_name() or row['teacher'].username), row['count'], row['open'], row['amount']])
    summary.append(['TOTAL', sum(r['count'] for r in totals), sum(r['open'] for r in totals), sum(r['amount'] for r in totals)])
    detail = wb.create_sheet('Per Student')
    detail.append(['Teacher', 'Classroom', 'Student', 'Lesson date', 'Fine (UZS)', 'Status', 'Reviewed by', 'Review note'])
    for fine in fines:
        ob = fine.obligation
        detail.append([
            safe_excel(ob.schedule.teacher.get_full_name() or ob.schedule.teacher.username),
            safe_excel(ob.schedule.classroom.name),
            safe_excel(ob.student.get_full_name() or ob.student.username),
            ob.lesson_date,
            fine.amount_uzs if fine.status == AssessmentPenalty.OPEN else 0,
            fine.get_status_display(),
            safe_excel(fine.reviewed_by.get_full_name() or fine.reviewed_by.username) if fine.reviewed_by else '',
            safe_excel(fine.review_note),
        ])
        detail.cell(detail.max_row, 4).number_format = 'YYYY-MM-DD'
    for ws in wb:
        ws.freeze_panes = 'A2'
        ws.auto_filter.ref = ws.dimensions
        for cell in ws[1]:
            cell.fill = PatternFill('solid', fgColor='31205A')
            cell.font = Font(bold=True, color='FFFFFF')
        for column in ws.columns:
            letter = column[0].column_letter
            ws.column_dimensions[letter].width = min(55, max(15, max(len(str(cell.value or '')) for cell in column) + 3))
    buf = BytesIO()
    wb.save(buf)
    response = HttpResponse(buf.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="makonbook-assessment-fines-{start:%Y-%m}.xlsx"'
    return response


@login_required
def manager_activity_report(request):
    if not _manager(request.user):
        return HttpResponseForbidden('Manager access required.')
    today = timezone.localdate()
    def count(days):
        return UserActivityDay.objects.filter(date__gte=today - timedelta(days=days - 1), date__lte=today).values('user_id').distinct().count()
    previous_month_end = today.replace(day=1) - timedelta(days=1)
    previous_month_start = previous_month_end.replace(day=1)
    count_previous_month = UserActivityDay.objects.filter(
        date__gte=previous_month_start, date__lte=previous_month_end,
    ).values('user_id').distinct().count()
    by_day = list(UserActivityDay.objects.filter(date__gte=today - timedelta(days=29), date__lte=today)
                  .values('date').annotate(count=models.Count('user_id', distinct=True)).order_by('date'))
    return render(request, 'ratings/manager_activity_report.html', {
        'today_count': count(1), 'count_15': count(15), 'count_30': count(30),
        'count_previous_month': count_previous_month,
        'previous_month_label': previous_month_start.strftime('%B %Y'),
        'day_rows': list(reversed(by_day)),
        'today': today,
    })


from django.db import models  # noqa: E402
