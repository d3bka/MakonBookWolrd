"""V79: Mistakes — retry the questions a student got wrong or skipped in practice tests."""
import json
from collections import OrderedDict

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .mistakes import (
    correct_answer_text, load_questions, question_model, record_drill_answer, sync_student_mistakes,
)
from .models import StudentMistake
from .rich_text import is_makon, question_display
from .student_workspace import should_use_student_workspace, student_workspace_context

DRILL_SIZE = 20


@login_required(login_url='/login/')
def student_learn_redirect(request):
    """V79: Learn only repeated links that already live in the sidebar; it became Mistakes."""
    return redirect('student_mistakes_root')


@login_required(login_url='/login/')
def student_mistakes(request):
    if not should_use_student_workspace(request.user):
        return redirect('student_dashboard_root')
    sync_student_mistakes(request.user)
    rows = load_questions(list(
        StudentMistake.objects.filter(user=request.user).select_related('test').order_by('status', '-last_wrong_at')
    ))
    open_rows = [row for row in rows if row.status == StudentMistake.STATUS_OPEN]
    fixed_rows = [row for row in rows if row.status == StudentMistake.STATUS_FIXED]

    topics = OrderedDict()
    for row in open_rows:
        question = row.question
        type_obj = getattr(question, 'type', None)
        key = (row.section, type_obj.pk if type_obj else 0)
        topic = topics.setdefault(key, {
            'section': row.section,
            'section_label': 'Reading and Writing' if row.section == 'english' else 'Math',
            'type_id': type_obj.pk if type_obj else 0,
            'name': type_obj.name if type_obj else 'Other questions',
            'count': 0,
        })
        topic['count'] += 1

    context = student_workspace_context(request.user, active='mistakes')
    context.update({
        'mistake_open': open_rows,
        'mistake_fixed': fixed_rows[:30],
        'mistake_open_count': len(open_rows),
        'mistake_fixed_count': len(fixed_rows),
        'mistake_english_count': sum(1 for row in open_rows if row.section == 'english'),
        'mistake_math_count': sum(1 for row in open_rows if row.section == 'math'),
        'mistake_topics': sorted(topics.values(), key=lambda item: (-item['count'], item['name'])),
        'mistake_total': len(rows),
        'mistake_drill_size': DRILL_SIZE,
    })
    return render(request, 'sat/student_mistakes.html', context)


def _drill_rows(user, params):
    qs = StudentMistake.objects.filter(user=user).select_related('test')
    mode = (params.get('mode') or 'all').lower()
    title, subtitle = 'Fix all mistakes', 'Open mistakes first, then ones you fixed once.'
    if params.get('mistake', '').isdigit():
        qs = qs.filter(pk=int(params['mistake']))
        title, subtitle = 'Fix this mistake', ''
    elif mode == 'open':
        qs = qs.filter(status=StudentMistake.STATUS_OPEN)
        title, subtitle = 'Mistakes to fix', 'Only the questions you have not fixed yet.'
    elif mode == 'topic':
        section = (params.get('section') or '').lower()
        qs = qs.filter(status=StudentMistake.STATUS_OPEN, section=section)
        type_id = params.get('type', '')
        title, subtitle = 'Topic drill', ''
        rows = load_questions(list(qs.order_by('first_wrong_at')))
        if type_id.isdigit():
            wanted = int(type_id)
            rows = [row for row in rows if (row.question.type_id or 0) == wanted]
            if rows and rows[0].question.type:
                title = rows[0].question.type.name
        return rows[:DRILL_SIZE], title, subtitle
    # "all": open (oldest first) then fixed-once ones, so the quick test also re-checks fixes
    rows = load_questions(list(qs.order_by('first_wrong_at', 'pk')))
    rows.sort(key=lambda row: row.status != StudentMistake.STATUS_OPEN)  # stable: open first, then fixed once
    return rows[:DRILL_SIZE], title, subtitle


@login_required(login_url='/login/')
@ensure_csrf_cookie  # the drill checks answers with fetch(); a fresh session had no CSRF cookie
def student_mistakes_drill(request):
    if not should_use_student_workspace(request.user):
        return redirect('student_dashboard_root')
    sync_student_mistakes(request.user)
    rows, title, subtitle = _drill_rows(request.user, request.GET)
    context = student_workspace_context(request.user, active='mistakes')
    context.update({'drill_rows': rows, 'drill_title': title, 'drill_subtitle': subtitle})
    return render(request, 'sat/student_mistakes_drill.html', context)


@login_required(login_url='/login/')
@require_POST
def student_mistake_check(request):
    try:
        payload = json.loads(request.body.decode('utf-8'))
        section = str(payload.get('section') or '').lower()
        question_id = int(payload.get('question_id'))
        response = payload.get('answer')
    except (TypeError, ValueError, AttributeError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'error': 'Invalid answer payload.'}, status=400)
    model = question_model(section)
    if model is None:
        return JsonResponse({'ok': False, 'error': 'Invalid section.'}, status=400)
    # Only questions in this student's own mistake log can be checked here.
    if not StudentMistake.objects.filter(user=request.user, section=section, question_id=question_id).exists():
        return JsonResponse({'ok': False, 'error': 'This question is not in your mistakes.'}, status=403)
    question = model.objects.filter(pk=question_id).first()
    if question is None:
        return JsonResponse({'ok': False, 'error': 'Question not found.'}, status=404)
    correct, row = record_drill_answer(request.user, section, question, response)
    result = {
        'ok': True,
        'correct': correct,
        'answer': correct_answer_text(section, question),
        'explanation': question.explained or '',
        'status': row.status if row else '',
    }
    if is_makon(question):
        result['explanation_html'] = str(question_display(question, 'explained'))
    return JsonResponse(result)
