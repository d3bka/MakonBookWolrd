"""V77: who counts as a current SATMakon student (full MakonBook access).

A student is current when Hollihop says so:
  * their Hollihop status is an active one ("Занимается", Active, Working) -> current;
  * any other non-empty status ("Не занимается", "Закончил обучение", ...) -> not current,
    even if they are still listed in a Hollihop group (the status wins);
  * no status yet -> current when they have an approved membership in an active
    Hollihop-managed classroom.
Everyone else keeps MakonBook but only the first practice tests of the library.
"""
from django.conf import settings

_CACHE_ATTR = "_makon_active_satmakon_student"


def is_active_satmakon_student(user):
    if not getattr(user, "is_authenticated", False):
        return False
    cached = getattr(user, _CACHE_ATTR, None)
    if cached is not None:
        return cached
    status_active = _hollihop_status_active(user)
    active = status_active if status_active is not None else _in_hollihop_group(user)
    try:
        setattr(user, _CACHE_ATTR, active)
    except Exception:  # noqa: BLE001 - lazy/anonymous wrappers may refuse attributes
        pass
    return active


def _hollihop_status_active(user):
    """True / False from the Hollihop status, or None when there is no status to go by."""
    try:
        profile = user.profile
    except Exception:  # noqa: BLE001 - a user without a profile is simply not linked
        return None
    if not getattr(profile, "hollihop_client_id", None):
        return None
    status = (getattr(profile, "hollihop_status", "") or "").strip().casefold()
    if not status:
        return None
    return status in settings.HOLLIHOP_ACTIVE_STUDENT_STATUSES


def _in_hollihop_group(user):
    from apps.sat.models import ClassroomMembership

    return ClassroomMembership.objects.filter(
        user=user,
        role="student",
        status="approved",
        classroom__is_active=True,
        classroom__hollihop_managed=True,
    ).exists()


def free_practice_test_limit():
    return max(0, int(getattr(settings, "MAKONBOOK_FREE_PRACTICE_TESTS", 5) or 0))


def classroom_join_codes_enabled():
    return bool(getattr(settings, "MAKONBOOK_CLASSROOM_JOIN_CODES", False))


# V78: every role has its own practice-test library address (/<role>/practice-tests/).
PRACTICE_LIBRARY_ROUTES = {
    "student": "practice_tests_root",
    "teacher": "teacher_practice_tests_root",
    "manager": "manager_practice_tests_root",
    "support": "support_teacher_practice_tests_root",
    "admin": "admin_practice_tests",
}


def practice_library_role(user):
    """The workspace a user's practice-test library belongs to."""
    from apps.sat.roles import is_manager, is_platform_admin, is_support_teacher, is_teacher
    from apps.sat.student_workspace import should_use_student_workspace

    if not getattr(user, "is_authenticated", False) or should_use_student_workspace(user):
        return "student"
    if is_teacher(user):
        return "teacher"
    if is_manager(user):
        return "manager"
    if is_support_teacher(user):
        return "support"
    if is_platform_admin(user):
        return "admin"
    return "student"


def practice_library_url(user):
    from django.urls import reverse

    return reverse(PRACTICE_LIBRARY_ROUTES[practice_library_role(user)])
