"""V89: what the Hollihop integration is doing right now, for the Manager Panel.

The DB lock in HollihopSyncState is the source of truth for "a sync is running" (it is
held by every kind of run and expires on its own if a worker dies). The cache adds the
details a manager wants to see: which kind of run, which stage, how much is done, and
"queued" between pressing a button and a worker picking the task up. Every cache call
is best-effort: Redis trouble never breaks a sync or the page.
"""
from __future__ import annotations

from django.core.cache import cache
from django.utils import timezone

ACTIVITY_KEY = "hollihop:activity:v89"
QUEUED_KEY = "hollihop:queued:v89"
QUEUED_SECONDS = 30 * 60

KIND_LABELS = {
    "initial": "Initial import",
    "full": "Full reconciliation",
    "smart": "Update check",
    "memberships": "Membership sweep",
    "webhook": "Student update from Hollihop",
    "mapping": "Classroom mapping",
    "command": "Command-line sync",
    "sync": "Synchronization",
}
STAGE_LABELS = {
    "managers": "Managers",
    "teachers": "Teachers",
    "students": "Students",
    "classrooms": "Classrooms",
    "memberships": "Memberships",
    "attendance": "Attendance",
    "student_delta": "Changed students",
    "edunit_delta": "Changed groups",
    "teacher_poll": "Teachers",
    "manager_poll": "Managers",
    "student_sweep": "Student profiles",
    "catalog_sweep": "Group catalog",
    "membership_sweep": "Memberships",
    "attendance_sweep": "Attendance",
    "webhook": "Student",
}
COUNT_FIELDS = (
    ("students_found", "students"), ("teachers_found", "teachers"), ("classrooms_found", "classrooms"),
    ("memberships_added", "memberships added"), ("memberships_removed", "memberships removed"),
    ("attendance_created", "attendance records"), ("errors", "errors"),
)


def _get(key):
    try:
        return cache.get(key)
    except Exception:  # noqa: BLE001 - a cache outage must not break the page or a sync
        return None


def _set(key, value, timeout):
    try:
        cache.set(key, value, timeout)
    except Exception:  # noqa: BLE001
        pass


def _delete(key):
    try:
        cache.delete(key)
    except Exception:  # noqa: BLE001
        pass


def mark_queued(kind):
    """A manager pressed a button; the task waits for a Celery worker."""
    _set(QUEUED_KEY, {"kind": kind, "at": timezone.now().isoformat()}, QUEUED_SECONDS)


def started(kind):
    _delete(QUEUED_KEY)
    _set(ACTIVITY_KEY, {"kind": kind, "stage": "", "counts": {}, "at": timezone.now().isoformat()}, 12 * 60 * 60)


def note(*, stage=None, summary=None):
    info = _get(ACTIVITY_KEY) or {"kind": "sync", "stage": "", "counts": {}}
    if stage is not None:
        info["stage"] = stage
    if summary is not None:
        info["counts"] = {name: getattr(summary, name, 0) for name, _label in COUNT_FIELDS}
    _set(ACTIVITY_KEY, info, 12 * 60 * 60)


def finished():
    _delete(ACTIVITY_KEY)


def _elapsed(since):
    seconds = max(0, int((timezone.now() - since).total_seconds()))
    if seconds < 60:
        return f"{seconds} s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} min {seconds:02d} s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d} min"


def current(state=None):
    """{"status": "running" | "queued" | "idle", ...} for the page and the JSON poll."""
    from apps.integrations.models import HollihopSyncState

    if state is None:
        state = HollihopSyncState.objects.filter(provider="hollihop").first()
    now = timezone.now()
    running = bool(state and state.lock_token and state.lock_expires_at and state.lock_expires_at > now)
    if running:
        info = _get(ACTIVITY_KEY) or {}
        kind = info.get("kind") or "sync"
        stage = info.get("stage") or ""
        counts = info.get("counts") or {}
        started_at = state.last_attempt or now
        return {
            "status": "running",
            "kind": kind,
            "kind_label": KIND_LABELS.get(kind, KIND_LABELS["sync"]),
            "stage": stage,
            "stage_label": STAGE_LABELS.get(stage, ""),
            "started_at": started_at.isoformat(),
            "elapsed": _elapsed(started_at),
            "counts": [
                {"label": label, "value": counts[name]}
                for name, label in COUNT_FIELDS if counts.get(name)
            ],
        }
    queued = _get(QUEUED_KEY)
    if queued:
        return {
            "status": "queued",
            "kind": queued.get("kind", "sync"),
            "kind_label": KIND_LABELS.get(queued.get("kind"), KIND_LABELS["sync"]),
        }
    return {
        "status": "idle",
        "last_status": getattr(state, "last_status", "") or "",
        "last_attempt": state.last_attempt.isoformat() if state and state.last_attempt else "",
    }


def is_busy():
    """Cheap check for the staff sidebar dot (one indexed row + one cache read)."""
    try:
        return current()["status"] in {"running", "queued"}
    except Exception:  # noqa: BLE001 - the sidebar must render even if the DB hiccups
        return False
