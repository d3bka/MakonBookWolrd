"""V102: "Import units" — copy units with their materials from any classroom of the school."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Prefetch, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .lesson_copy import copy_homework, copy_units, source_label
from .models import Classroom, ClassroomHomeworkAssignment, ClassroomLesson, ClassroomLessonResource, MakonNotification
from .roles import can_manage_classroom

RESULT_LIMIT = 30


def _ids(values):
    return sorted({int(v) for v in values if str(v).strip().isdecimal()})


def _search(target, user, query):
    classrooms = (
        Classroom.objects.exclude(pk=target.pk)
        .annotate(unit_count=Count("lessons", distinct=True))
        .filter(unit_count__gt=0)
        .select_related("teacher")
    )
    if query:
        words = query.split()
        for word in words:
            classrooms = classrooms.filter(
                Q(name__icontains=word) | Q(teacher__first_name__icontains=word)
                | Q(teacher__last_name__icontains=word) | Q(teacher__username__icontains=word)
                | Q(lessons__title__icontains=word)
            )
        classrooms = classrooms.distinct().order_by("-is_active", "name")[:RESULT_LIMIT]
    else:
        # Your own classes first, then the classes whose units changed most recently.
        own = list(classrooms.filter(teacher=user).order_by("-is_active", "name")[:12])
        others = list(
            classrooms.exclude(teacher=user).filter(is_active=True)
            .annotate(last_unit=Max("lessons__created_at")).order_by("-last_unit")[: max(0, 12 - len(own))]
        )
        classrooms = own + others
    classrooms = list(classrooms)
    if query:
        matches = {}
        lesson_q = Q()
        for word in query.split():
            lesson_q &= Q(title__icontains=word)
        for lesson in ClassroomLesson.objects.filter(lesson_q, classroom__in=classrooms).order_by("order").only("classroom_id", "title", "order"):
            matches.setdefault(lesson.classroom_id, []).append(lesson)
        for classroom in classrooms:
            classroom.matched_units = matches.get(classroom.pk, [])[:5]
    return classrooms


@login_required(login_url="/login/")
def teacher_classroom_units_import(request, classroom_id):
    target = get_object_or_404(Classroom, pk=classroom_id)
    if not can_manage_classroom(request.user, target):
        return HttpResponseForbidden("You can manage only your own classrooms.")
    target_lessons = list(ClassroomLesson.objects.filter(classroom=target).order_by("order"))
    target_titles = {lesson.title.strip().casefold(): lesson for lesson in target_lessons}

    source_id = request.POST.get("source") or request.GET.get("source") or ""
    source = None
    if str(source_id).isdecimal():
        source = Classroom.objects.select_related("teacher").filter(pk=int(source_id)).exclude(pk=target.pk).first()

    if request.method == "POST":
        if source is None:
            messages.error(request, "Choose a class to import from.")
            return redirect("teacher_classroom_units_import_root", classroom_id=target.pk)
        units = list(ClassroomLesson.objects.filter(classroom=source, pk__in=_ids(request.POST.getlist("units"))).select_related("classroom__teacher"))
        homework = list(ClassroomHomeworkAssignment.objects.filter(classroom=source, pk__in=_ids(request.POST.getlist("homework"))).order_by("created_at"))
        if not units and not homework:
            messages.error(request, "Tick at least one unit or homework to import.")
            return redirect(f"{reverse('teacher_classroom_units_import_root', args=[target.pk])}?source={source.pk}")
        position = (request.POST.get("insert_after") or "").strip()
        insert_after = int(position) if position.isdecimal() else None
        publish = request.POST.get("publish") == "1"
        created, skipped = copy_units(target, units, user=request.user, insert_after=insert_after, publish=publish)
        copied_homework = copy_homework(target, homework, user=request.user)
        if publish and created:
            from .views import _notify_classroom_students

            _notify_classroom_students(
                target, notice_type=MakonNotification.TYPE_LESSON,
                title=f"New unit: {created[0].title}" if len(created) == 1 else f"{len(created)} new units",
                message=target.name, url=reverse("student_classroom_home_root", args=[target.pk]),
            )
        parts = []
        if created:
            materials = sum(lesson.resources.count() for lesson in created)
            parts.append(f"{len(created)} unit{'s' if len(created) != 1 else ''} with {materials} material{'s' if materials != 1 else ''}")
        if copied_homework:
            parts.append(f"{len(copied_homework)} homework as hidden drafts")
        messages.success(request, f"Imported {' and '.join(parts)} from {source.name}." + ("" if publish or not created else " The units are hidden from students until you publish them."))
        if skipped or len(copied_homework) < len(homework):
            messages.warning(request, "Some materials could not be copied because their file, test or vocabulary unit no longer exists.")
        return redirect(f"{reverse('teacher_classroom_root', args=[target.pk])}?edit=1#course")

    context = {"classroom": target, "target_lessons": target_lessons, "query": (request.GET.get("q") or "").strip()[:120]}
    if source is not None:
        units = list(
            ClassroomLesson.objects.filter(classroom=source).order_by("order")
            .prefetch_related(Prefetch("resources", queryset=ClassroomLessonResource.objects.order_by("order", "created_at")))
        )
        for unit in units:
            unit.duplicate_of = target_titles.get(unit.title.strip().casefold())
        context.update({
            "source": source,
            "source_label": source_label(source),
            "units": units,
            "duplicate_count": sum(1 for unit in units if unit.duplicate_of),
            "source_homework": list(ClassroomHomeworkAssignment.objects.filter(classroom=source).order_by("-created_at")[:60]),
        })
    else:
        context["results"] = _search(target, request.user, context["query"])
    return render(request, "sat/teacher_units_import.html", context)
