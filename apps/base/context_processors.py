from datetime import timedelta

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.conf import settings


def site_meta(request):
    """Expose the canonical site root to templates.

    Social-card scrapers and ``rel=canonical`` both need absolute URLs, and the
    app answers on several hostnames. Building them from ``request.get_host()``
    would make every alias advertise itself as a separate copy of the site, so
    templates use this fixed value instead.
    """
    return {
        "SITE_URL": settings.SITE_URL,
        "makonbook_world_enabled": getattr(settings, "MAKONBOOK_WORLD_ENABLED", False),
    }


def test_import_meta(request):
    empty = {
        "test_import_center_allowed": False,
        "test_import_pending_reviews": 0,
        "test_import_unread_notifications": 0,
        "test_import_notifications": [],
    }
    if not getattr(request.user, "is_authenticated", False):
        return empty
    try:
        from apps.sat.models import MakonNotification, TestImportReview
        from apps.sat.roles import SUPPORT_TEACHER_GROUP

        role_names = getattr(request.user, "_makon_workspace_role_names", None)
        if role_names is None:
            role_names = {name.casefold() for name in request.user.groups.values_list("name", flat=True)}
            request.user._makon_workspace_role_names = role_names
        manager_allowed = bool(
            request.user.is_superuser
            or request.user.is_staff
            or "admin" in role_names
            or "manager" in role_names
        )
        reviewer = False
        if SUPPORT_TEACHER_GROUP.casefold() in role_names:
            try:
                reviewer = bool(request.user.support_teacher_profile.is_active)
            except Exception:
                reviewer = False
        pending = (
            TestImportReview.objects.filter(
                reviewer=request.user,
                verdict=TestImportReview.VERDICT_PENDING,
            ).count()
            if reviewer else 0
        )
        # Deleted-homework notices were noisy and are no longer part of the product.
        # Remove historical copies as users encounter the workspace so the panel
        # immediately reflects the new notification policy.
        MakonNotification.objects.filter(
            user=request.user,
            type=MakonNotification.TYPE_HOMEWORK,
            title__startswith='Homework removed:',
        ).delete()

        # Deadline notices are generated lazily on normal authenticated page loads.
        # This keeps them accurate without requiring Celery/cron and avoids noisy
        # "homework deleted" messages that are no longer useful to students.
        try:
            from apps.sat.models import ClassroomHomeworkAssignment
            now = timezone.now()
            urgent_assignments = (
                ClassroomHomeworkAssignment.objects
                .filter(
                    is_active=True,
                    due_at__gt=now,
                    due_at__lte=now + timedelta(hours=24),
                    classroom__memberships__user=request.user,
                    classroom__memberships__role='student',
                    classroom__memberships__status='approved',
                )
                .filter(Q(assign_all=True) | Q(assigned_students=request.user))
                .select_related('classroom')
                .distinct()
                .order_by('due_at')[:4]
            )
            for assignment in urgent_assignments:
                remaining = assignment.due_at - now
                critical = remaining <= timedelta(hours=3)
                title = ('Deadline soon: ' if critical else 'Homework due today: ') + assignment.title
                due_local = timezone.localtime(assignment.due_at)
                MakonNotification.objects.update_or_create(
                    user=request.user,
                    type=MakonNotification.TYPE_HOMEWORK,
                    url=reverse('student_homework_launch_root', args=[assignment.pk]),
                    defaults={
                        'title': title,
                        'message': f'{assignment.classroom.name} · due {due_local:%d %b, %H:%M}',
                    },
                )
        except Exception:
            # Notifications must never make the workspace unavailable.
            pass

        notices_qs = MakonNotification.objects.filter(user=request.user)
        unread = notices_qs.filter(is_read=False).count()
        notices = list(notices_qs.order_by("-created_at")[:12])
        return {
            "test_import_center_allowed": bool(manager_allowed or reviewer),
            "test_import_pending_reviews": pending,
            "test_import_unread_notifications": unread,
            "test_import_notifications": notices,
        }
    except Exception:
        # Keeps login/admin pages alive during the deployment window before the migration is applied.
        return empty


STAFF_WORKSPACE_ROUTE_MAP = {
    "admin_dashboard": "home",
    "admin_users": "users",
    "admin_user_detail": "users",
    "admin_user_edit": "users",
    "admin_user_delete": "users",
    "admin_user_create": "users",
    "admin_groups": "groups",
    "admin_group_detail": "groups",
    "admin_group_delete": "groups",
    "admin_group_remove_user": "groups",
    "edit_group_tests": "groups",
    "admin_tests": "tests",
    "admin_test_detail": "tests",
    "admin_mocks": "mocks",
    "admin_mock_create": "mocks",
    "admin_mock_detail": "mocks",
    "admin_mock_download": "mocks",
    "admin_mock_delete": "mocks",
    "admin_support_teachers": "support-teachers",
    "admin_support_teacher_create": "support-teachers",
    "admin_support_teacher_edit": "support-teachers",
    "admin_support_teacher_toggle": "support-teachers",
    "admin_support_teacher_availability_add": "support-teachers",
    "admin_support_teacher_availability_delete": "support-teachers",
    "admin_support_bookings": "support-bookings",
    "teacher_dashboard_root": "home",
    "teacher_classrooms_root": "classrooms",
    "teacher_classroom_list": "classrooms",
    "create_classroom": "classrooms",
    "edit_classroom": "classrooms",
    "teacher_classroom_dashboard": "classrooms",
    "teacher_homework_root": "homework",
    "teacher_practice_tests_root": "practice-tests",
    "teacher_lessons_root": "lessons",
    "teacher_progress_root": "progress",
    "teacher_assessments_root": "ratings",
    "teacher_access_root": "access",
    "teacher_vocabulary_units_root": "vocabulary",
    "teacher_classroom_homework": "homework",
    "teacher_student_practice_progress_root": "progress",
    "teacher_student_vocab_progress_root": "progress",
    "teacher_student_admission_progress_root": "progress",
    "teacher_classroom_student_review_root": "progress",
    "teacher_classroom_student_review_question_root": "progress",
    "teacher_classroom_lessons": "lessons",
    "classroom_join_requests": "classrooms",
    "update_student_section_access": "access",
    "update_student_practice_test_access": "access",
    "update_classroom_section_access": "access",
    "update_classroom_practice_test_access": "access",
    "update_classroom_ap_test_access": "access",
    "classroom_practice_tests": "access",
    "classroom_practice_tests_root": "practice-tests",
    "classroom_ap_tests_root": "access",
    "classroom_ap_tests": "access",
    "classroom_chat": "classrooms",
    "classroom_progress_dashboard": "progress",
    "classroom_student_review_results": "progress",
    "classroom_student_review_question": "progress",
    "classroom_student_practice_progress": "progress",
    "classroom_student_vocab_progress": "progress",
    "classroom_student_admission_progress": "progress",
    "teacher_vocabulary_units": "vocabulary",
    "teacher_vocabulary_unit_detail": "vocabulary",
    "create_vocabulary_unit": "vocabulary",
    "create_vocabulary_word": "vocabulary",
    "create_vocabulary_question": "vocabulary",
    "bulk_import_vocabulary_words": "vocabulary",
    "manager_dashboard_root": "home",
    "manager_attendance_insights": "attendance",
    "manager_assessment_report": "assessment",
    "manager_assessment_schedules": "schedules",
    "manager_activity_report": "activity",
    "manager_teacher_list_root": "teachers",
    "manager_support_teacher_list_root": "support",
    "manager_dashboard": "manager",
    "manager_teacher_detail": "manager",
    "manager_classroom_detail": "manager",
    "hollihop_dashboard": "hollihop",
    "hollihop_classroom_attendance": "classrooms",
    "support_teacher_list": "support",
    "support_teacher_detail": "support",
    "support_teacher_dashboard_root": "home",
    "support_teacher_planner_root": "support",
    "support_teacher_profile_edit_root": "support-profile",
    "support_teacher_planner": "support",
    "support_teacher_profile_edit": "support-profile",
    "mentor_profile_edit_root": "mentor-profile",
    "edit_profile": "account",
    "settings_page": "account",
    "test_import_list": "imports",
    "test_import_create": "imports",
    "test_import_detail": "imports",
    "test_import_preview": "imports",
    "test_import_review": "imports",
    "test_import_question_edit": "imports",
    "managed_test_list": "published-tests",
    "managed_test_edit": "published-tests",
    "managed_test_question_edit": "published-tests",
    "managed_test_delete": "published-tests",
    "manager_test_import_list_root": "imports",
    "manager_test_import_create_root": "imports",
    "manager_test_import_detail_root": "imports",
    "manager_test_import_preview_root": "imports",
    "manager_test_import_review_root": "imports",
    "manager_test_import_question_edit_root": "imports",
    "support_teacher_review_list_root": "imports",
    "support_teacher_review_detail_root": "imports",
    "support_teacher_review_preview_root": "imports",
    "support_teacher_review_submit_root": "imports",
    "support_teacher_review_question_edit_root": "imports",
    "manager_managed_test_list_root": "published-tests",
    "manager_managed_test_edit_root": "published-tests",
    "manager_managed_test_question_edit_root": "published-tests",
    "manager_managed_test_delete_root": "published-tests",
    "rating_teacher_classroom": "ratings",
    "rating_assess_student": "ratings",
    "rating_edit_assessment": "ratings",
}


def staff_workspace_meta(request):
    """Cheap role-aware context used only by the staff workspace shell.

    Group names are cached on the User object for the lifetime of the request so
    this context processor does not add one query per role check. Related
    business objects never grant roles by themselves.
    """
    empty = {
        "staff_workspace_enabled": False,
        "staff_workspace_active": "",
        "staff_workspace_mode": "",
        "staff_has_teacher": False,
        "staff_has_manager": False,
        "staff_has_support": False,
        "staff_has_admin": False,
        "staff_role_count": 0,
    }
    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return empty

    role_names = getattr(user, "_makon_workspace_role_names", None)
    if role_names is None:
        role_names = {name.casefold() for name in user.groups.values_list("name", flat=True)}
        user._makon_workspace_role_names = role_names

    has_teacher = "teacher" in role_names
    has_manager = "manager" in role_names
    has_admin = bool(user.is_superuser or user.is_staff or "admin" in role_names)
    has_support = False
    if "support teacher" in role_names:
        try:
            has_support = bool(user.support_teacher_profile.is_active)
        except Exception:
            has_support = False

    route_name = getattr(getattr(request, "resolver_match", None), "url_name", "") or ""
    active = STAFF_WORKSPACE_ROUTE_MAP.get(route_name, "")
    if getattr(request, "resolver_match", None) and request.resolver_match.app_name == "apclasses":
        if route_name in {"event_list", "event_detail"}:
            active = "ap"

    enabled = bool(has_teacher or has_manager or has_support or has_admin)
    requested_account_mode = ""
    if route_name in {"settings_page", "edit_profile"}:
        active = "account"
        candidate = (request.GET.get("workspace") or "").strip().lower()
        allowed = {
            "teacher": has_teacher,
            "manager": bool(has_manager or has_admin),
            "admin": has_admin,
            "support": has_support,
        }
        if candidate in allowed and allowed[candidate]:
            requested_account_mode = candidate

    # V50.2.12: account pages preserve the workspace the user explicitly
    # opened. A multi-role Teacher/Manager should not switch back to Teacher
    # chrome just because Settings/Profile are shared routes.
    admin_route = route_name.startswith("admin_") and route_name != "admin:index"
    if requested_account_mode:
        mode = requested_account_mode
    elif admin_route and has_admin:
        mode = "admin"
    elif route_name.startswith('manager_') or active == "manager":
        mode = "manager"
    elif route_name.startswith('support_teacher_') or active in {"support", "support-profile"}:
        # A Manager/Admin may inspect support-teacher pages without actually
        # owning the Support Teacher role. Keep their workspace identity as
        # Manager instead of showing a misleading Support Teacher shell label.
        if has_support:
            mode = "support"
        elif has_manager or has_admin:
            mode = "manager"
        else:
            mode = "teacher" if has_teacher else ""
    elif active:
        mode = "teacher" if has_teacher else ("manager" if has_manager or has_admin else "support")
    else:
        mode = "teacher" if has_teacher else ("manager" if has_manager else ("support" if has_support else ("admin" if has_admin else "")))

    return {
        "staff_workspace_enabled": enabled,
        "staff_workspace_active": active,
        "staff_workspace_mode": mode,
        "staff_has_teacher": has_teacher,
        "staff_has_manager": has_manager,
        "staff_has_support": has_support,
        "staff_has_admin": has_admin,
        # Admin remains a distinct switchable workspace. Manager access is still
        # available to platform admins for backwards-compatible operational overrides.
        "staff_role_count": sum((has_teacher, has_manager or has_admin, has_admin, has_support)),
    }
