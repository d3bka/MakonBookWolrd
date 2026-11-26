"""V114: "Weak topics" — where a class makes the most mistakes, and a plan for the next lesson."""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from .class_weak_topics import DEFAULT_PERIOD, MIN_ANSWERS, MIN_STUDENTS, PERIODS, class_weak_topics
from .models import Classroom
from .rich_text import question_display
from .roles import is_manager, is_platform_admin, is_teacher


def _int(value):
    value = (value or "").strip()
    return int(value) if value.isdecimal() else None


def _render(request, classrooms, *, scope, teachers=None):
    selected_teacher = _int(request.GET.get("teacher"))
    choices = sorted(classrooms, key=lambda c: (not c.is_active, c.name.casefold()))
    if selected_teacher:
        choices = [c for c in choices if c.teacher_id == selected_teacher]
    by_id = {c.pk: c for c in classrooms}
    classroom = by_id.get(_int(request.GET.get("classroom")))
    if classroom is None:
        classroom = next((c for c in choices if c.is_active), choices[0] if choices else None)
    period = request.GET.get("period") or DEFAULT_PERIOD
    period = period if period in PERIODS else DEFAULT_PERIOD

    result = class_weak_topics(classroom, period) if classroom else None
    if result:
        for item in result["top_questions"]:
            question = item["question"]
            item["passage_html"] = question_display(question, "passage")
            item["question_html"] = question_display(question, "question")
            item["choices"] = [
                (letter.upper(), question_display(question, letter, inline=True))
                for letter in "abcd" if getattr(question, letter, None)
            ]
    return render(request, "sat/class_weak_topics.html", {
        "scope": scope,
        "classroom": classroom,
        "classrooms": [c for c in choices if c.is_active or (classroom and c.pk == classroom.pk)],
        "teachers": teachers or [],
        "selected_teacher": selected_teacher,
        "period": period,
        "periods": [("30", "Last 30 days"), ("90", "Last 90 days"), ("all", "All time")],
        "result": result,
        "rules": {"min_answers": MIN_ANSWERS, "min_students": MIN_STUDENTS},
    })


@login_required(login_url="/login/")
def teacher_weak_topics(request):
    if not is_teacher(request.user):
        return HttpResponseForbidden("Teacher access required.")
    from .views import _teacher_managed_classrooms

    classrooms = list(_teacher_managed_classrooms(request.user).only("pk", "name", "is_active", "teacher_id"))
    wanted = _int(request.GET.get("classroom"))
    if wanted and wanted not in {c.pk for c in classrooms} and (is_manager(request.user) or is_platform_admin(request.user)):
        return manager_weak_topics(request)  # a Teacher + Manager opened another teacher's class
    return _render(request, classrooms, scope="teacher")


@login_required(login_url="/login/")
def manager_weak_topics(request):
    if not (is_manager(request.user) or is_platform_admin(request.user)):
        return HttpResponseForbidden("Manager access required.")
    classrooms = list(Classroom.objects.select_related("teacher").only(
        "pk", "name", "is_active", "teacher_id", "teacher__first_name", "teacher__last_name", "teacher__username",
    ))
    teachers = {}
    for classroom in classrooms:
        if classroom.is_active and classroom.teacher_id:
            teachers[classroom.teacher_id] = classroom.teacher.get_full_name() or classroom.teacher.username
    return _render(
        request, classrooms, scope="manager",
        teachers=sorted(teachers.items(), key=lambda item: item[1].casefold()),
    )
