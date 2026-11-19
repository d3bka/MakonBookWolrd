"""V93: SAT practice-test attempt limits.

* Teachers, support teachers, managers, admins and testers: unlimited.
* Current SATMakon students: 5 attempts per test.
* Everyone else: 3 attempts per test.

Every start of a practice test counts (first start, full retake and section retake),
so leaving a test half-way does not give free looks at the questions. Homework that a
teacher assigned is not limited. Counting began when the limit was introduced.

When a SATMakon student runs out, they can ask the teachers of their classes. A teacher
grants 1-3 more attempts (or rejects) and the student is notified either way. Students
who are not with SATMakon cannot ask; they are invited to join SATMakon instead.
"""
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

from .attempt_limit_models import SatAttemptRequest, SatAttemptUse
from .roles import in_group, is_manager, is_platform_admin, is_support_teacher, is_teacher
from .student_access import is_active_satmakon_student

log = logging.getLogger("makonbook.attempt_limits")

MAX_GRANT = 3


class LimitError(Exception):
    pass


def student_limit():
    return int(getattr(settings, "SAT_ATTEMPTS_SATMAKON_STUDENT", 5))


def public_limit():
    return int(getattr(settings, "SAT_ATTEMPTS_PUBLIC", 3))


def is_unlimited(user):
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(
        is_platform_admin(user) or is_manager(user) or is_teacher(user)
        or is_support_teacher(user) or in_group(user, "Tester") or in_group(user, "Dev")
    )


def base_limit(user):
    """None means unlimited."""
    if is_unlimited(user):
        return None
    return student_limit() if is_active_satmakon_student(user) else public_limit()


def used(user, test):
    return SatAttemptUse.objects.filter(user=user, test=test).count()


def extra(user, test):
    total = SatAttemptRequest.objects.filter(
        user=user, test=test, status=SatAttemptRequest.APPROVED,
    ).aggregate(total=Sum("granted"))["total"]
    return int(total or 0)


def teachers_for(user):
    """Teachers of the active classes the student is an approved member of."""
    from django.contrib.auth import get_user_model

    from .models import ClassroomMembership

    classroom_ids = list(
        ClassroomMembership.objects.filter(
            user=user, role="student", status="approved", classroom__is_active=True,
        ).values_list("classroom_id", flat=True)
    )
    if not classroom_ids:
        return []
    from .models import Classroom

    ids = set(
        Classroom.objects.filter(pk__in=classroom_ids, teacher__isnull=False).values_list("teacher_id", flat=True)
    )
    ids.update(
        ClassroomMembership.objects.filter(
            classroom_id__in=classroom_ids, role="teacher", status="approved",
        ).values_list("user_id", flat=True)
    )
    ids.discard(user.pk)
    teachers = get_user_model().objects.filter(pk__in=ids, is_active=True).order_by("first_name", "username")
    return [teacher for teacher in teachers if is_teacher(teacher)]


def state(user, test):
    """Everything the pages need to show the student's attempts at this test."""
    limit = base_limit(user)
    if limit is None:
        return {"unlimited": True, "limit": None, "used": 0, "extra": 0, "total": None, "remaining": None,
                "exhausted": False, "satmakon": True, "can_request": False, "pending": None, "teachers": []}
    count = used(user, test)
    bonus = extra(user, test)
    total = limit + bonus
    remaining = max(0, total - count)
    satmakon = is_active_satmakon_student(user)
    pending = SatAttemptRequest.objects.filter(user=user, test=test, status=SatAttemptRequest.PENDING).first()
    teachers = teachers_for(user) if satmakon else []
    return {
        "unlimited": False,
        "limit": limit,
        "used": count,
        "extra": bonus,
        "total": total,
        "remaining": remaining,
        "exhausted": remaining <= 0,
        "satmakon": satmakon,
        "can_request": bool(satmakon and teachers and not pending),
        "pending": pending,
        "teachers": teachers,
    }


def can_start(user, test):
    limit = base_limit(user)
    if limit is None:
        return True
    return used(user, test) < limit + extra(user, test)


def record(user, test, attempt_id, source=SatAttemptUse.SOURCE_START):
    """Count a newly started attempt. Unlimited users are not counted."""
    if not attempt_id or base_limit(user) is None:
        return
    try:
        with transaction.atomic():
            SatAttemptUse.objects.get_or_create(user=user, test=test, attempt_id=attempt_id,
                                                defaults={"source": source})
    except IntegrityError:
        pass


def refund(user, test, attempt_id):
    """Give back an attempt that was discarded without a single answer."""
    if attempt_id:
        SatAttemptUse.objects.filter(user=user, test=test, attempt_id=attempt_id).delete()


def limit_url(test):
    return reverse("practice_test_attempts_root", kwargs={"pk": test.name})


def _notify(user_ids, title, message, url):
    from .models import MakonNotification

    rows = [
        MakonNotification(user_id=user_id, type=MakonNotification.TYPE_ATTEMPTS, title=title[:180],
                          message=(message or "")[:500], url=url[:500])
        for user_id in {uid for uid in user_ids if uid}
    ]
    if rows:
        try:
            MakonNotification.objects.bulk_create(rows)
        except Exception:  # noqa: BLE001 - a notice must never block the request itself
            log.exception("Could not create attempt notifications")


def _name(user):
    return user.get_full_name() or user.username


def ask_teacher(user, test, message=""):
    info = state(user, test)
    if info["unlimited"] or not info["exhausted"]:
        raise LimitError("You still have attempts left for this test.")
    if not info["satmakon"]:
        raise LimitError("Only SATMakon students can ask a teacher for more attempts.")
    if info["pending"]:
        raise LimitError("Your request is already waiting for a teacher.")
    if not info["teachers"]:
        raise LimitError("You are not in a class with a teacher yet, so there is no one to ask.")
    message = (message or "").strip()[:300]
    try:
        with transaction.atomic():
            request_row = SatAttemptRequest.objects.create(user=user, test=test, message=message)
    except IntegrityError as exc:
        raise LimitError("Your request is already waiting for a teacher.") from exc
    text = f"{_name(user)} used all {info['total']} attempts at {test.name} and asks for more."
    if message:
        text += f" “{message}”"
    _notify([t.pk for t in info["teachers"]], f"More attempts: {_name(user)} · {test.name}", text,
            reverse("teacher_attempt_requests_root"))
    return request_row


def can_decide(teacher, request_row):
    return requests_for(teacher).filter(pk=request_row.pk).exists()


def _students_of(teacher):
    from django.db.models import Q

    from .models import ClassroomMembership

    return ClassroomMembership.objects.filter(
        Q(classroom__teacher=teacher)
        | Q(classroom__memberships__user=teacher, classroom__memberships__role="teacher",
            classroom__memberships__status="approved"),
        role="student", status="approved", classroom__is_active=True,
    ).values("user_id")


def requests_for(teacher):
    """Requests from this teacher's students (managers and admins see all)."""
    rows = SatAttemptRequest.objects.select_related("user", "test", "decided_by")
    if is_platform_admin(teacher) or is_manager(teacher):
        return rows
    if not is_teacher(teacher):
        return rows.none()
    return rows.filter(user_id__in=_students_of(teacher))


def pending_for(teacher):
    """Waiting requests this teacher may decide."""
    return list(requests_for(teacher).filter(status=SatAttemptRequest.PENDING).order_by("created_at"))


def pending_count(teacher):
    return requests_for(teacher).filter(status=SatAttemptRequest.PENDING).count()


def decide(teacher, request_row, *, approve, granted=1, note=""):
    note = (note or "").strip()[:300]
    with transaction.atomic():
        row = SatAttemptRequest.objects.select_for_update().get(pk=request_row.pk)
        if row.status != SatAttemptRequest.PENDING:
            raise LimitError("This request was already decided.")
        if not can_decide(teacher, row):
            raise LimitError("You are not a teacher of this student.")
        if approve:
            try:
                granted = int(granted)
            except (TypeError, ValueError):
                granted = 1
            row.granted = max(1, min(MAX_GRANT, granted))
            row.status = SatAttemptRequest.APPROVED
        else:
            row.granted = 0
            row.status = SatAttemptRequest.REJECTED
        row.decided_by = teacher
        row.decision_note = note
        row.decided_at = timezone.now()
        row.save(update_fields=["granted", "status", "decided_by", "decision_note", "decided_at"])
    if approve:
        plural = "attempt" if row.granted == 1 else "attempts"
        title = f"{row.test.name}: +{row.granted} {plural} from {_name(teacher)}"
        message = note or "You can start the test again."
    else:
        title = f"{row.test.name}: request for more attempts was rejected"
        message = note or f"{_name(teacher)} did not give more attempts."
    _notify([row.user_id], title, message, limit_url(row.test))
    return row


def withdraw(user, request_row):
    if request_row.user_id != user.pk or request_row.status != SatAttemptRequest.PENDING:
        raise LimitError("This request cannot be withdrawn.")
    request_row.status = SatAttemptRequest.WITHDRAWN
    request_row.decided_at = timezone.now()
    request_row.save(update_fields=["status", "decided_at"])
