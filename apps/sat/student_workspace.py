"""Shared context for the V50 student workspace shell.

Keep role gating in one place so student-facing pages can adopt the new shell
without leaking it into Teacher, Manager, Support Teacher, or Admin workflows.
"""

from .models import ClassroomMembership
from apps.gamification.services import gamification_shell_context
from .roles import (
    ADMIN_GROUP,
    MANAGER_GROUP,
    SUPPORT_TEACHER_GROUP,
    TEACHER_GROUP,
)


STUDENT_WORKSPACE_TEMPLATE = "sat/student_workspace.html"
LEGACY_WORKSPACE_TEMPLATE = "template.html"


def should_use_student_workspace(user):
    """Return True only for the normal student-facing account experience.

    MakonBook intentionally allows multi-role accounts. Staff-side identities
    keep their operational navigation even if historical student data exists.
    Authenticated accounts with no staff-side role use the student workspace,
    matching the canonical student routing policy of ``/dashboard/``.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return False

    # One group query instead of four independent .exists() checks on every
    # workspace navigation. User objects are request-scoped, so this cache is
    # safe for the lifetime of the request and saves several DB round-trips.
    role_names = getattr(user, "_makon_workspace_role_names", None)
    if role_names is None:
        role_names = {name.casefold() for name in user.groups.values_list("name", flat=True)}
        user._makon_workspace_role_names = role_names
    staff_roles = {
        ADMIN_GROUP.casefold(),
        MANAGER_GROUP.casefold(),
        TEACHER_GROUP.casefold(),
        SUPPORT_TEACHER_GROUP.casefold(),
    }
    return not bool(role_names & staff_roles)


def student_workspace_context(user, *, active=None, enabled=None, approved_memberships=None):
    """Build shell/template context for a page that supports both layouts."""
    use_workspace = should_use_student_workspace(user) if enabled is None else bool(enabled)
    context = {
        "student_workspace_base_template": (
            STUDENT_WORKSPACE_TEMPLATE if use_workspace else LEGACY_WORKSPACE_TEMPLATE
        ),
        "use_student_workspace": use_workspace,
    }
    if not use_workspace:
        return context

    # Materialize this small navigation list once.  The shell only needs the
    # classroom and teacher labels; prefetching section_access here made every
    # student page pay for data it did not use, and .first() issued a second
    # query on top of the sidebar query.  Page-specific views that need section
    # access load it explicitly.
    if approved_memberships is None:
        approved_memberships = list(
            ClassroomMembership.objects.filter(
                user=user,
                role="student",
                status="approved",
                classroom__is_active=True,
            )
            .select_related("classroom", "classroom__teacher")
            .order_by("-approved_at", "-requested_at")
        )
    else:
        # Page views that already loaded memberships (for section access, chat
        # ordering, etc.) can hand the list to the shell and avoid repeating the
        # same navigation query.
        approved_memberships = list(approved_memberships)
    context.update(
        {
            "approved_memberships": approved_memberships,
            "dashboard_primary_membership": approved_memberships[0] if approved_memberships else None,
            "student_workspace_active": active,
        }
    )
    context.update(gamification_shell_context(user))
    return context
