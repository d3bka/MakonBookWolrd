"""Manager-only, read-only attendance intelligence from synchronized Hollihop rows."""
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.integrations.models import HollihopAttendance
from apps.sat.models import Classroom
from apps.sat.roles import is_manager, is_platform_admin


def _date_param(value, default):
    try:
        return parse_date(value) or default
    except (TypeError, ValueError):
        return default


@login_required(login_url='/login/')
def manager_attendance_insights(request):
    if not (is_manager(request.user) or is_platform_admin(request.user)):
        return HttpResponseForbidden('Manager access required.')

    today = timezone.localdate()
    start = _date_param(request.GET.get('from'), today - timedelta(days=59))
    end = _date_param(request.GET.get('to'), today)
    if start > end:
        start, end = end, start
    # Bound expensive cross-organization queries to a year at most.
    if (end - start).days > 365:
        start = end - timedelta(days=365)
    end = min(end, today)
    start = min(start, end)
    boundary = start + timedelta(days=(end - start).days // 2)
    classroom_id = request.GET.get('classroom', '')
    classroom = None
    if classroom_id.isdecimal():
        classroom = Classroom.objects.filter(pk=int(classroom_id)).first()

    q = HollihopAttendance.objects.filter(date__gte=start, date__lte=end)
    if classroom is not None:
        q = q.filter(classroom=classroom)
    search = (request.GET.get('search') or '').strip()[:80]
    if search:
        q = q.filter(Q(student__first_name__icontains=search) | Q(student__last_name__icontains=search) | Q(student__username__icontains=search))

    # Values-level aggregation avoids materializing thousands of attendance records.
    aggregate = q.values('student_id', 'student__first_name', 'student__last_name', 'student__username').annotate(
        present=Count('pk', filter=Q(status='present')),
        absent=Count('pk', filter=Q(status='absent')),
        previous_present=Count('pk', filter=Q(status='present', date__lte=boundary)),
        previous_total=Count('pk', filter=Q(date__lte=boundary)),
        recent_present=Count('pk', filter=Q(status='present', date__gt=boundary)),
        recent_total=Count('pk', filter=Q(date__gt=boundary)),
    )
    rows = []
    for item in aggregate:
        total = item['present'] + item['absent']
        earlier = item['previous_total']
        later = item['recent_total']
        prev_rate = 100 * item['previous_present'] / earlier if earlier else None
        recent_rate = 100 * item['recent_present'] / later if later else None
        delta = round(recent_rate - prev_rate, 1) if prev_rate is not None and recent_rate is not None else None
        rows.append({
            'name': (' '.join([item['student__first_name'], item['student__last_name']]).strip() or item['student__username']),
            'username': item['student__username'], 'total': total,
            'present': item['present'], 'absent': item['absent'],
            'attendance_pct': round(100 * item['present'] / total, 1) if total else None,
            'delta': delta, 'previous_rate': round(prev_rate, 1) if prev_rate is not None else None,
            'recent_rate': round(recent_rate, 1) if recent_rate is not None else None,
            'student_id': item['student_id'],
        })
    trend = request.GET.get('trend', 'all')
    if trend == 'declining':
        rows = [r for r in rows if r['delta'] is not None and r['delta'] < 0]
    elif trend == 'low':
        rows = [r for r in rows if r['attendance_pct'] is not None and r['attendance_pct'] < 80]
    sort = request.GET.get('sort', 'absent')
    if sort == 'decline':
        rows.sort(key=lambda r: (r['delta'] is None, r['delta'] if r['delta'] is not None else 0, -r['absent']))
    elif sort == 'rate':
        rows.sort(key=lambda r: (r['attendance_pct'], -r['absent']))
    else:
        rows.sort(key=lambda r: (-r['absent'], r['attendance_pct']))
    return render(request, 'sat/manager_attendance.html', {
        'attendance_rows': rows[:500], 'matched_students': len(rows),
        'start': start, 'end': end, 'boundary': boundary,
        'classroom_id': classroom_id if classroom else '', 'classrooms': Classroom.objects.filter(is_active=True).order_by('name'),
        'search': search, 'trend': trend, 'sort': sort, 'source': 'Hollihop',
    })
