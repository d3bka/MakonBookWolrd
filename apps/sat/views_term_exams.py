"""V117: Mid-term / Final exams — manager setup, teacher overview, the student's Exams page."""
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from . import term_exams as svc
from .exam_models import SUBJECT_CHOICES, ExamSeat, ExamSession, TermExam, current_academic_year
from .models import Classroom, Test
from .roles import is_manager, is_platform_admin, is_teacher
from .student_workspace import should_use_student_workspace, student_workspace_context


def _manager(user):
    return is_manager(user) or is_platform_admin(user)


def _int(value):
    value = (value or "").strip()
    return int(value) if value.isdecimal() else None


def _session_rows(sessions):
    rows = []
    for session in sessions:
        counts = session.seats.aggregate(
            total=Count("pk"), entered=Count("pk", filter=~Q(answers={})),
            pending=Count("pk", filter=Q(status=ExamSeat.STATUS_PENDING)),
        )
        rows.append({"session": session, **counts})
    return rows


# ------------------------------------------------------------------ manager

@login_required(login_url="/login/")
def manager_exams(request):
    if not _manager(request.user):
        return HttpResponseForbidden("Manager access required.")
    classrooms = list(Classroom.objects.filter(is_active=True).select_related("teacher").order_by("name"))
    if request.method == "POST":
        try:
            exam = svc.create_exam(
                kind=request.POST.get("kind", ""), academic_year=request.POST.get("academic_year") or current_academic_year(),
                title=request.POST.get("title", ""),
                classrooms=[c for c in classrooms if str(c.pk) in request.POST.getlist("classrooms")],
                created_by=request.user,
            )
        except svc.ExamError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"{exam.display_title} created. Now add a session for each subject.")
            return redirect("manager_exam_detail_root", exam_id=exam.pk)
    exams = TermExam.objects.prefetch_related("classrooms").annotate(
        session_count=Count("sessions", distinct=True),
    ).order_by("-created_at")[:100]
    return render(request, "sat/term_exams/manager_list.html", {
        "exams": exams,
        "classrooms": classrooms,
        "kinds": TermExam.KIND_CHOICES,
        "default_year": current_academic_year(),
    })


def _parse_start(request):
    try:
        day = datetime.strptime(request.POST.get("date", ""), "%Y-%m-%d").date()
        moment = datetime.strptime(request.POST.get("time", ""), "%H:%M").time()
    except ValueError:
        raise svc.ExamError("Enter the date and the time of the session.")
    return timezone.make_aware(datetime.combine(day, moment), timezone.get_current_timezone())


@login_required(login_url="/login/")
def manager_exam_detail(request, exam_id):
    if not _manager(request.user):
        return HttpResponseForbidden("Manager access required.")
    exam = get_object_or_404(TermExam.objects.prefetch_related("classrooms"), pk=exam_id)
    if request.method == "POST":
        action = request.POST.get("action", "")
        try:
            if action == "add_session":
                test = Test.objects.filter(pk=request.POST.get("test", ""), test_type=Test.TYPE_EXAM).first()
                if test is None:
                    raise svc.ExamError("Choose an exam test variant.")
                duration = _int(request.POST.get("duration")) or 0
                if not 10 <= duration <= 300:
                    raise svc.ExamError("Duration must be 10–300 minutes.")
                teacher = User.objects.filter(pk=_int(request.POST.get("teacher")), is_active=True).first()
                session = svc.create_session(
                    exam, subject=request.POST.get("subject", ""), test=test, starts_at=_parse_start(request),
                    duration_minutes=duration, room=request.POST.get("room", ""), teacher=teacher,
                    is_retake=request.POST.get("is_retake") == "1",
                )
                messages.success(request, f"Session added: {session.get_subject_display()}"
                                          f"{' retake' if session.is_retake else ''}, {session.seats.count()} students.")
            elif action == "delete_session":
                svc.delete_session(get_object_or_404(ExamSession, pk=_int(request.POST.get("session")), exam=exam))
                messages.success(request, "Session deleted.")
            elif action == "refresh_seats":
                session = get_object_or_404(ExamSession, pk=_int(request.POST.get("session")), exam=exam, is_retake=False)
                added = svc.fill_main_seats(session)
                messages.success(request, f"{added} new student{'s' if added != 1 else ''} added from the classes.")
            elif action == "add_retake_students":
                session = get_object_or_404(ExamSession, pk=_int(request.POST.get("session")), exam=exam, is_retake=True)
                added = svc.add_retake_students(session, request.POST.getlist("students"))
                messages.success(request, f"{added} student{'s' if added != 1 else ''} added to the retake.")
            elif action == "mark_exam_test":
                test = get_object_or_404(Test, pk=request.POST.get("test", ""))
                svc.mark_as_exam(test)
                messages.success(request, f"{test.name} is now an exam variant: hidden from students and out of Practice.")
            elif action == "update_classes":
                ids = request.POST.getlist("classrooms")
                classes = list(Classroom.objects.filter(pk__in=[i for i in ids if i.isdecimal()]))
                if not classes:
                    raise svc.ExamError("Choose at least one class.")
                exam.classrooms.set(classes)
                messages.success(request, "Classes updated. Use “Add new students” on a session to give them seats.")
        except svc.ExamError as exc:
            messages.error(request, str(exc))
        return redirect("manager_exam_detail_root", exam_id=exam.pk)

    sessions = list(exam.sessions.select_related("test", "teacher").order_by("subject", "is_retake", "starts_at"))
    students = svc.exam_students(exam)
    seated = {}
    for seat in ExamSeat.objects.filter(session__exam=exam).values("student_id", "session__subject", "status"):
        seated.setdefault((seat["student_id"], seat["session__subject"]), []).append(seat["status"])
    # Students marked absent or late in the main session come first and are pre-ticked.
    retake_candidates = {}
    for subject, _ in SUBJECT_CHOICES:
        rows = []
        for student, classroom in students:
            statuses = seated.get((student.pk, subject), [])
            missed = next((s for s in statuses if s in (ExamSeat.STATUS_ABSENT, ExamSeat.STATUS_LATE)), "")
            rows.append({"student": student, "classroom": classroom, "missed": missed})
        rows.sort(key=lambda r: (not r["missed"], (r["student"].get_full_name() or r["student"].username).casefold()))
        retake_candidates[subject] = rows
    tests = svc.exam_tests()
    used = dict(ExamSession.objects.exclude(exam=exam).values_list("test_id", "exam_id"))
    session_rows = _session_rows(sessions)
    for row in session_rows:
        row["retake_rows"] = retake_candidates.get(row["session"].subject, []) if row["session"].is_retake else []
    return render(request, "sat/term_exams/manager_detail.html", {
        "exam": exam,
        "session_rows": session_rows,
        "students": students,
        "exam_tests": [t for t in tests if t.pk not in used],
        "convertible_tests": svc.convertible_tests(),
        "teachers": svc.staff_teachers(),
        "subjects": SUBJECT_CHOICES,
        "all_classrooms": Classroom.objects.filter(Q(is_active=True) | Q(term_exams=exam)).distinct().order_by("name"),
        "exam_classroom_ids": {c.pk for c in exam.classrooms.all()},
        "rooms": sorted({r for r in ExamSession.objects.exclude(room="").values_list("room", flat=True)}),
        "today": timezone.localdate(),
    })


# ------------------------------------------------------------------ teacher

@login_required(login_url="/login/")
def teacher_exams(request):
    if not (is_teacher(request.user) or _manager(request.user)):
        return HttpResponseForbidden("Teacher access required.")
    sessions = list(svc.sessions_for_teacher(request.user)[:100])
    return render(request, "sat/term_exams/teacher_list.html", {
        "session_rows": _session_rows(sessions),
        "now": timezone.now(),
    })


# ------------------------------------------------------------------ student

@login_required(login_url="/login/")
def student_exams(request):
    if not should_use_student_workspace(request.user):
        return redirect("student_dashboard_root")
    now = timezone.now()
    upcoming, past = [], []
    for seat in svc.seats_for_student(request.user):
        seat.state = svc.student_result_state(seat, now)
        (upcoming if seat.state in ("upcoming", "in_progress") else past).append(seat)
    past.reverse()
    context = student_workspace_context(request.user, active="exams")
    context.update({"exam_upcoming": upcoming, "exam_past": past})
    return render(request, "sat/term_exams/student_exams.html", context)
