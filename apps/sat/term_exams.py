"""V117: Mid-term / Final exams — sessions, seats and exam test variants."""
from __future__ import annotations

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from .exam_models import SUBJECT_ENGLISH, SUBJECT_MATH, ExamSeat, ExamSession, TermExam
from .models import (
    ClassroomMembership, English_Question, Math_Question, StudentPracticeTestAccess, Test, TestReview,
)

QUESTION_MODELS = {SUBJECT_ENGLISH: English_Question, SUBJECT_MATH: Math_Question}


class ExamError(ValueError):
    """A rule of the exam flow was broken; the message is shown to the manager."""


# ------------------------------------------------------------------ exam test variants

def exam_tests():
    """Tests of type Exam with how many questions each subject has."""
    return list(
        Test.objects.filter(test_type=Test.TYPE_EXAM)
        .annotate(english_count=Count("english_question", distinct=True), math_count=Count("math_question", distinct=True))
        .order_by("-created")
    )


def convertible_tests():
    """Tests that can become an exam variant: nobody attempted them and they are hidden from students."""
    attempted = TestReview.objects.filter(test__isnull=False).values_list("test_id", flat=True).distinct()
    return list(
        Test.objects.exclude(test_type=Test.TYPE_EXAM).filter(is_available=False).exclude(pk__in=attempted)
        .annotate(english_count=Count("english_question", distinct=True), math_count=Count("math_question", distinct=True))
        .filter(Q(english_count__gt=0) | Q(math_count__gt=0)).order_by("-created")[:200]
    )


@transaction.atomic
def mark_as_exam(test):
    """Make ``test`` an exam variant: hidden, out of Practice and out of every group."""
    if TestReview.objects.filter(test=test).exists():
        raise ExamError("Students already took this test, so its questions are not secret. Import a new variant.")
    if test.is_available:
        raise ExamError("Hide the test first (Published tests → Available off), then mark it as an exam.")
    test.test_type = Test.TYPE_EXAM
    test.is_available = False
    test.save(update_fields=["test_type", "is_available"])
    StudentPracticeTestAccess.objects.filter(test=test).delete()
    if hasattr(test, "groups"):
        test.groups.clear()
    return test


def questions_for(test, subject):
    """The subject's questions in paper order: module 1 then module 2, by number."""
    model = QUESTION_MODELS[subject]
    return list(model.objects.filter(test=test).order_by("module", "number", "pk"))


def question_count(test, subject):
    return QUESTION_MODELS[subject].objects.filter(test=test).count()


# ------------------------------------------------------------------ sessions and seats

def exam_students(exam):
    """[(student, classroom)] of every approved, active student in the exam's classes (first class wins)."""
    seen = {}
    for membership in ClassroomMembership.objects.filter(
        classroom__in=exam.classrooms.all(), role="student", status="approved", user__is_active=True,
    ).select_related("user", "classroom").order_by("classroom__name", "user__first_name", "user__last_name"):
        seen.setdefault(membership.user_id, (membership.user, membership.classroom))
    return list(seen.values())


def fill_main_seats(session):
    """Give every student of the exam's classes a seat in a main session. Returns how many were added."""
    if session.is_retake:
        return 0
    have = set(session.seats.values_list("student_id", flat=True))
    new = [ExamSeat(session=session, student=student, classroom=classroom)
           for student, classroom in exam_students(session.exam) if student.pk not in have]
    ExamSeat.objects.bulk_create(new, ignore_conflicts=True)
    return len(new)


def add_retake_students(session, student_ids):
    """Seats in a retake for these students of the exam (they keep their class). Returns how many were added."""
    if not session.is_retake:
        raise ExamError("Students are added by hand only to a retake.")
    classes = {student.pk: classroom for student, classroom in exam_students(session.exam)}
    wanted = [int(pk) for pk in student_ids if str(pk).isdecimal() and int(pk) in classes]
    have = set(session.seats.values_list("student_id", flat=True))
    new = [ExamSeat(session=session, student_id=pk, classroom=classes[pk]) for pk in wanted if pk not in have]
    ExamSeat.objects.bulk_create(new, ignore_conflicts=True)
    return len(new)


@transaction.atomic
def create_session(exam, *, subject, test, starts_at, duration_minutes, room="", teacher=None, is_retake=False):
    if subject not in QUESTION_MODELS:
        raise ExamError("Choose Math or Reading and Writing.")
    if test.test_type != Test.TYPE_EXAM:
        raise ExamError("Only a test of type Exam can be used. Mark the test as an exam first.")
    if not question_count(test, subject):
        raise ExamError(f"{test.name} has no {dict(ExamSession._meta.get_field('subject').choices)[subject]} questions.")
    main = exam.sessions.filter(subject=subject, is_retake=False).first()
    if not is_retake and main:
        raise ExamError("This exam already has a main session for this subject. Add a retake instead.")
    if is_retake:
        if not main:
            raise ExamError("Add the main session for this subject first.")
        if main.test_id == test.pk:
            raise ExamError("A retake must use a different test variant, so nobody can pass the answers on.")
    used_elsewhere = ExamSession.objects.filter(test=test).exclude(exam=exam).exists()
    if used_elsewhere:
        raise ExamError(f"{test.name} was already used in another exam. Use a new variant.")
    session = ExamSession.objects.create(
        exam=exam, subject=subject, test=test, starts_at=starts_at, duration_minutes=duration_minutes,
        room=room.strip()[:120], teacher=teacher, is_retake=is_retake,
    )
    fill_main_seats(session)
    return session


def delete_session(session):
    if session.seats.exclude(answers={}).exists() or session.seats.exclude(status=ExamSeat.STATUS_PENDING).exists():
        raise ExamError("Answers are already entered for this session, so it cannot be deleted.")
    session.delete()


# ------------------------------------------------------------------ who sees what

def teacher_classroom_ids(user):
    from .views import _teacher_managed_classrooms

    return list(_teacher_managed_classrooms(user).values_list("pk", flat=True))


def sessions_for_teacher(user):
    class_ids = teacher_classroom_ids(user)
    return (
        ExamSession.objects.filter(Q(exam__classrooms__in=class_ids) | Q(teacher=user))
        .select_related("exam", "test", "teacher").distinct().order_by("-starts_at")
    )


def seats_for_student(user):
    return list(
        ExamSeat.objects.filter(student=user).select_related("session", "session__exam", "session__teacher")
        .order_by("session__starts_at")
    )


def student_result_state(seat, now=None):
    """What the student sees for a seat: upcoming, in_progress, waiting or published."""
    now = now or timezone.now()
    session = seat.session
    if session.is_published and seat.status == ExamSeat.STATUS_CHECKED:
        return "published"
    if now < session.starts_at:
        return "upcoming"
    if now < session.ends_at:
        return "in_progress"
    if seat.status in (ExamSeat.STATUS_ABSENT, ExamSeat.STATUS_LATE, ExamSeat.STATUS_MOVED):
        return "retake"
    return "waiting"


def staff_teachers():
    return list(User.objects.filter(is_active=True, groups__name="Teacher").distinct()
                .order_by("first_name", "last_name", "username"))


def create_exam(*, kind, academic_year, classrooms, title="", created_by=None):
    if kind not in dict(TermExam.KIND_CHOICES):
        raise ExamError("Choose Mid-term or Final.")
    if not classrooms:
        raise ExamError("Choose at least one class.")
    exam = TermExam.objects.create(kind=kind, academic_year=academic_year.strip()[:16], title=title.strip()[:160],
                                   created_by=created_by)
    exam.classrooms.set(classrooms)
    return exam
