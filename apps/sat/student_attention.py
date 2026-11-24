"""V102: which students need the teacher's attention, and why.

One row per (classroom, student) with the reasons that apply:

* missed homework  - past-due homework not done, or marked "Not done" by the teacher;
* partly done      - the teacher marked homework "Partly done" more than once;
* absences         - Hollihop attendance for this classroom;
* lower score      - the last test is clearly below the student's usual result;
* inactive         - no visit to MakonBook for a while.

Each reason has a weight; a student is listed when the weights add up to
``LIST_FROM``. Everything is read with a handful of aggregated queries, so the
page stays fast for a whole school.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from statistics import median

from django.db.models import Max, Q
from django.utils import timezone

WINDOW_DAYS = 30
SCORE_WINDOW_DAYS = 60
INACTIVE_DAYS = 14
SNOOZE_DAYS = 7
LIST_FROM = 2
SCORE_DROP_RATIO = 0.85


def _reason(kind, weight, title, detail):
    return {"kind": kind, "weight": weight, "title": title, "detail": detail}


def _homework_signals(members, student_ids, now):
    from .models import ClassroomHomeworkAssignment, ClassroomHomeworkSubmission

    since = now - timedelta(days=WINDOW_DAYS)
    assignments = list(
        ClassroomHomeworkAssignment.objects.filter(classroom_id__in=list(members), is_active=True)
        .filter(Q(due_at__gte=since, due_at__lt=now) | Q(created_at__gte=since))
        .prefetch_related("assigned_students")
        .only("pk", "classroom_id", "title", "due_at", "assign_all")
    )
    if not assignments:
        return {}
    submissions = {
        (row.assignment_id, row.student_id): row
        for row in ClassroomHomeworkSubmission.objects.filter(
            assignment_id__in=[a.pk for a in assignments], student_id__in=student_ids,
        ).only("assignment_id", "student_id", "status", "teacher_verdict")
    }

    result = defaultdict(lambda: {"missed": [], "partial": []})
    for assignment in assignments:
        targets = members[assignment.classroom_id] if assignment.assign_all else (
            {u.pk for u in assignment.assigned_students.all()} & members[assignment.classroom_id]
        )
        overdue = bool(assignment.due_at and since <= assignment.due_at < now)
        for student_id in targets:
            submission = submissions.get((assignment.pk, student_id))
            verdict = submission.teacher_verdict if submission else ""
            done = bool(submission and submission.status == ClassroomHomeworkSubmission.STATUS_SUBMITTED)
            key = (assignment.classroom_id, student_id)
            if verdict == ClassroomHomeworkSubmission.VERDICT_NOT_DONE or (overdue and not done):
                result[key]["missed"].append(assignment.title)
            elif verdict == ClassroomHomeworkSubmission.VERDICT_PARTIAL:
                result[key]["partial"].append(assignment.title)
    return result


def _attendance_signals(classroom_ids, student_ids, now):
    from django.db.models import Count

    from apps.integrations.models import HollihopAttendance

    since = timezone.localdate(now) - timedelta(days=WINDOW_DAYS)
    rows = (
        HollihopAttendance.objects.filter(classroom_id__in=classroom_ids, student_id__in=student_ids, date__gte=since)
        .values("classroom_id", "student_id")
        .annotate(total=Count("pk"), absent=Count("pk", filter=Q(status=HollihopAttendance.STATUS_ABSENT)))
    )
    return {(r["classroom_id"], r["student_id"]): (r["absent"], r["total"]) for r in rows}


def _score_signals(student_ids, now):
    from .models import TestReview

    since = now - timedelta(days=SCORE_WINDOW_DAYS)
    history = defaultdict(list)
    for row in (
        TestReview.objects.filter(user_id__in=student_ids, created_at__gte=since, score__isnull=False, test__isnull=False)
        .order_by("created_at")
        .values("user_id", "score", "run_mode", "test__name")
    ):
        history[row["user_id"]].append(row)
    result = {}
    for student_id, rows in history.items():
        latest = rows[-1]
        earlier = [r["score"] for r in rows[:-1] if r["run_mode"] == latest["run_mode"]][-4:]
        if len(earlier) < 2:
            continue
        usual = median(earlier)
        if usual > 0 and latest["score"] < usual * SCORE_DROP_RATIO:
            result[student_id] = (latest["score"], round(usual), latest["test__name"])
    return result


def _last_visits(student_ids):
    from apps.ratings.models import UserActivityDay

    return dict(
        UserActivityDay.objects.filter(user_id__in=student_ids)
        .values("user_id").annotate(last=Max("last_seen_at")).values_list("user_id", "last")
    )


def attention_rows(classrooms, now=None):
    """Students of ``classrooms`` who need attention, most urgent first.

    Returns ``(rows, snoozed_rows)``.
    """
    from .models import ClassroomMembership, StudentAttentionSnooze

    now = now or timezone.now()
    classrooms = list(classrooms)
    by_id = {c.pk: c for c in classrooms}
    memberships = list(
        ClassroomMembership.objects.filter(classroom_id__in=by_id, role="student", status="approved")
        .select_related("user")
        .only("classroom_id", "user_id", "approved_at", "user__first_name", "user__last_name", "user__username", "user__date_joined")
    )
    if not memberships:
        return [], []
    student_ids = sorted({m.user_id for m in memberships})
    members = defaultdict(set)
    for membership in memberships:
        members[membership.classroom_id].add(membership.user_id)
    homework = _homework_signals(members, student_ids, now)
    attendance = _attendance_signals(list(by_id), student_ids, now)
    scores = _score_signals(student_ids, now)
    visits = _last_visits(student_ids)
    snoozes = {
        (s.classroom_id, s.student_id): s
        for s in StudentAttentionSnooze.objects.filter(classroom_id__in=by_id, until__gt=now).select_related("snoozed_by")
    }

    rows, snoozed = [], []
    for membership in memberships:
        key = (membership.classroom_id, membership.user_id)
        reasons = []
        hw = homework.get(key, {"missed": [], "partial": []})
        missed = hw["missed"]
        if len(missed) >= 2:
            reasons.append(_reason(
                "homework", 3 if len(missed) >= 3 else 2, f"{len(missed)} homework missed",
                ", ".join(missed[:3]) + ("…" if len(missed) > 3 else ""),
            ))
        elif len(missed) == 1:
            reasons.append(_reason("homework", 1, "1 homework missed", missed[0]))
        if len(hw["partial"]) >= 2:
            reasons.append(_reason("partial", 1, f"{len(hw['partial'])} homework only partly done", ", ".join(hw["partial"][:3])))
        absent, total = attendance.get(key, (0, 0))
        if absent >= 2:
            reasons.append(_reason("attendance", 3 if absent >= 3 else 2, f"Missed {absent} of {total} lessons", f"Last {WINDOW_DAYS} days, from Hollihop"))
        if membership.user_id in scores:
            latest, usual, test_name = scores[membership.user_id]
            reasons.append(_reason("score", 2, "Lower test score", f"{test_name}: {latest}, usually about {usual}"))
        last_visit = visits.get(membership.user_id)
        joined = membership.approved_at or membership.user.date_joined
        quiet_since = last_visit or joined
        if quiet_since and now - quiet_since >= timedelta(days=INACTIVE_DAYS):
            days = (now - quiet_since).days
            reasons.append(_reason(
                "inactive", 1, f"Not on MakonBook for {days} days" if last_visit else "Never opened MakonBook",
                f"Last visit {timezone.localtime(last_visit):%d %b}" if last_visit else "Since joining the class",
            ))
        weight = sum(r["weight"] for r in reasons)
        if weight < LIST_FROM:
            continue
        reasons.sort(key=lambda r: -r["weight"])
        row = {
            "student": membership.user,
            "classroom": by_id[membership.classroom_id],
            "reasons": reasons,
            "weight": weight,
            "level": "high" if weight >= 5 else "medium" if weight >= 3 else "low",
            "snooze": snoozes.get(key),
        }
        (snoozed if row["snooze"] else rows).append(row)
    order = lambda r: (-r["weight"], (r["student"].get_full_name() or r["student"].username).casefold())  # noqa: E731
    rows.sort(key=order)
    snoozed.sort(key=order)
    return rows, snoozed
