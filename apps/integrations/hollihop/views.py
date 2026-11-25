from __future__ import annotations

import logging
import secrets
from collections import Counter

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Count, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods

from apps.integrations.models import (
    HollihopAttendance,
    HollihopCredentialDelivery,
    HollihopSyncConflict,
    HollihopSyncLog,
    HollihopSyncState,
)
from apps.sat.models import Classroom
from apps.sat.roles import can_manage_classroom, is_manager, is_platform_admin

from . import activity
from .error_reporting import safe_sync_error_details

logger = logging.getLogger(__name__)
from .credentials import deliver_new_temporary_access
from .tasks import (
    manual_full_hollihop_reconciliation,
    manual_initial_hollihop_sync,
    manual_membership_hollihop_sync,
    manual_smart_hollihop_sync,
    process_student_webhook,
    sync_resolved_classroom_mapping,
)

User = get_user_model()


def _manager_allowed(user):
    return bool(user.is_authenticated and (is_manager(user) or is_platform_admin(user)))


def _sync_precheck(request):
    if not _manager_allowed(request.user):
        return HttpResponseForbidden("Manager access required.")
    if not settings.HOLLIHOP_ENABLED or settings.SCHOOL_DATA_PROVIDER != "hollihop":
        messages.error(request, "Hollihop is disabled. Set SCHOOL_DATA_PROVIDER=hollihop and restart the app first.")
        return redirect("hollihop_dashboard")
    if not settings.HOLLIHOP_API_URL or not settings.HOLLIHOP_AUTH_KEY:
        messages.error(request, "Hollihop API URL/auth key are not configured.")
        return redirect("hollihop_dashboard")
    state = HollihopSyncState.objects.filter(provider="hollihop").first()
    if state and state.lock_token and state.lock_expires_at and state.lock_expires_at > timezone.now():
        messages.warning(request, "A Hollihop synchronization is already running.")
        return redirect("hollihop_dashboard")
    return None


def _initial_result(state):
    """V95: what the last initial import did, so the button never looks like it did nothing."""
    if not state:
        return None
    if state.initial_sync_completed:
        log = HollihopSyncLog.objects.filter(event_type="initial_sync_completed").order_by("-created_at").first()
        details = log.details if log and isinstance(log.details, dict) else {}
        return {
            "finished": True,
            "at": state.initial_sync_completed_at,
            "row_errors": int(details.get("row_errors") or details.get("errors") or 0),
            "students": details.get("students_found"),
            "classrooms": details.get("classrooms_found"),
        }
    if state.last_attempt and state.last_status in {HollihopSyncState.STATUS_PARTIAL, HollihopSyncState.STATUS_ERROR}:
        return {
            "finished": False,
            "at": state.last_attempt,
            "status": state.get_last_status_display(),
            "reason": state.last_error_safe,
            "students": state.students_synced,
            "classrooms": state.classrooms_synced,
        }
    return None


def integration_dashboard(request):
    if not _manager_allowed(request.user):
        return HttpResponseForbidden("Manager access required.")
    state = HollihopSyncState.objects.filter(provider="hollihop").first()
    conflicts = HollihopSyncConflict.objects.filter(status=HollihopSyncConflict.STATUS_PENDING).order_by("-updated_at")[:30]
    failed_deliveries = HollihopCredentialDelivery.objects.filter(
        overall_status__in=["failed", "partial", "no_contact"]
    ).select_related("user", "user__profile")[:30]
    recent_logs = HollihopSyncLog.objects.select_related("user", "classroom")[:50]
    # Credential delivery failures and synchronization failures are distinct.
    # Link error rows to the latest attempted sync, not to last successful sync.
    sync_errors = HollihopSyncLog.objects.filter(event_type="sync_error").order_by("-created_at")
    last_run_error_qs = sync_errors.filter(created_at__gte=state.last_attempt) if state and state.last_attempt else sync_errors.none()
    last_run_error_count = last_run_error_qs.count()

    def display_error(log):
        safe = safe_sync_error_details(log.details)
        # A validated status is safe; raw legacy `details` are never rendered.
        code = (log.details or {}).get("http_status") if isinstance(log.details, dict) else None
        return {
            "created_at": log.created_at,
            "entity_type": log.entity_type or "sync",
            "external_id": log.external_id,
            "error_type": safe["error"],
            "reason": safe["reason"],
            "http_status": code if type(code) is int and 400 <= code <= 599 else None,
        }

    last_run_errors = [display_error(log) for log in last_run_error_qs[:30]]
    # Historical errors are useful even if the latest run succeeded. Keep them
    # in a separate expandable table to avoid implying they are still active.
    previous_errors = [display_error(log) for log in sync_errors[:30]]
    delivery_qs = HollihopCredentialDelivery.objects.all()
    delivery_counts = Counter(delivery_qs.values_list("overall_status", flat=True))
    delivery_channel_counts = {
        "email_sms": delivery_qs.filter(email_status="sent", sms_status="sent").count(),
        "email_only": delivery_qs.filter(email_status="sent", sms_status="not_available").count(),
        "sms_only": delivery_qs.filter(email_status="not_available", sms_status="sent").count(),
        "failed": delivery_qs.filter(overall_status__in=["failed", "no_contact"]).count(),
    }
    teacher_choices = (
        User.objects
        .filter(Q(profile__hollihop_teacher_id__isnull=False) | Q(groups__name="Teacher"))
        .distinct()
        .order_by("first_name", "last_name", "username")
    )
    context = {
        "provider": settings.SCHOOL_DATA_PROVIDER,
        "enabled": settings.HOLLIHOP_ENABLED,
        "mode": settings.HOLLIHOP_MODE,
        "allowed_learning_types": ", ".join(settings.HOLLIHOP_ALLOWED_LEARNING_TYPES) or "ALL",
        "sync_interval_minutes": settings.HOLLIHOP_SYNC_INTERVAL_MINUTES,
        "teacher_poll_minutes": settings.HOLLIHOP_TEACHER_POLL_MINUTES,
        "manager_poll_minutes": settings.HOLLIHOP_MANAGER_POLL_MINUTES,
        "membership_sweep_minutes": settings.HOLLIHOP_MEMBERSHIP_SWEEP_MINUTES,
        "student_profile_sweep_minutes": settings.HOLLIHOP_STUDENT_PROFILE_SWEEP_MINUTES,
        "edunit_catalog_sweep_minutes": settings.HOLLIHOP_EDUNIT_CATALOG_SWEEP_MINUTES,
        "configured": bool(settings.HOLLIHOP_API_URL and settings.HOLLIHOP_AUTH_KEY),
        "webhook_configured": bool(settings.HOLLIHOP_WEBHOOK_SECRET),
        "state": state,
        "initial_sync_completed": bool(state and state.initial_sync_completed),
        "students_count": User.objects.filter(profile__hollihop_client_id__isnull=False).count(),
        "teachers_count": User.objects.filter(profile__hollihop_teacher_id__isnull=False).count(),
        "managers_count": User.objects.filter(profile__hollihop_employee_id__isnull=False, groups__name="Manager").distinct().count(),
        "classrooms_count": Classroom.objects.filter(hollihop_edunit_id__isnull=False).count(),
        "attendance_count": HollihopAttendance.objects.count(),
        "conflicts_count": HollihopSyncConflict.objects.filter(status="pending").count(),
        "conflicts": conflicts,
        "failed_deliveries": failed_deliveries,
        "recent_logs": recent_logs,
        "last_run_errors": last_run_errors,
        "last_run_error_count": last_run_error_count,
        "previous_sync_errors": previous_errors,
        "delivery_counts": delivery_counts,
        "delivery_channel_counts": delivery_channel_counts,
        "credentials_auto_send": settings.HOLLIHOP_AUTO_SEND_CREDENTIALS,
        "sms_provider": getattr(settings, "MAKONBOOK_SMS_PROVIDER", "disabled"),
        "teacher_choices": teacher_choices,
        "sync_activity": activity.current(state),
        "initial_result": _initial_result(state),
    }
    return render(request, "integrations/hollihop/dashboard.html", context)


def sync_activity(request):
    """V89: live status for the Manager Panel badge (polled every few seconds)."""
    if not _manager_allowed(request.user):
        return HttpResponseForbidden("Manager access required.")
    response = JsonResponse(activity.current())
    response["Cache-Control"] = "private, no-store"
    return response


@require_POST
def initial_sync(request):
    precheck = _sync_precheck(request)
    if precheck:
        return precheck
    state = HollihopSyncState.objects.filter(provider="hollihop").first()
    if state and state.initial_sync_completed:
        messages.warning(request, "Initial sync is already completed for this database. Use Full reconciliation if you really need a complete re-check.")
        return redirect("hollihop_dashboard")
    if request.POST.get("confirm") != "INITIAL":
        messages.error(request, "Initial synchronization confirmation is missing.")
        return redirect("hollihop_dashboard")
    # Prevent double-clicks / two browser tabs from queueing two expensive first
    # imports before the Celery worker has had time to acquire the DB lock.
    try:
        queued = cache.add("hollihop:initial-sync-queued", 1, timeout=30 * 60)
    except Exception:
        queued = True  # DB lock in the worker remains the second line of defence.
    if not queued:
        messages.warning(request, "Initial Hollihop synchronization is already queued or running.")
        return redirect("hollihop_dashboard")
    try:
        manual_initial_hollihop_sync.delay()
        activity.mark_queued("initial")
        messages.success(request, "Initial Hollihop import was queued. Automatic 5-minute smart sync will remain disabled until this import finishes successfully.")
    except Exception:
        try:
            cache.delete("hollihop:initial-sync-queued")
        except Exception:
            pass
        messages.error(request, "Background worker is unavailable. Run: python manage.py sync_hollihop --all --mark-initial")
    return redirect("hollihop_dashboard")


@require_POST
def smart_sync_now(request):
    precheck = _sync_precheck(request)
    if precheck:
        return precheck
    state = HollihopSyncState.objects.filter(provider="hollihop").first()
    if not state or not state.initial_sync_completed:
        messages.warning(request, "Run the Initial sync first. Smart synchronization is intentionally gated for local/test safety.")
        return redirect("hollihop_dashboard")
    try:
        manual_smart_hollihop_sync.delay()
        activity.mark_queued("smart")
        messages.success(request, "Lightweight Hollihop update check was queued.")
    except Exception:
        messages.error(request, "Background worker is unavailable.")
    return redirect("hollihop_dashboard")


@require_POST
def membership_sync_now(request):
    precheck = _sync_precheck(request)
    if precheck:
        return precheck
    state = HollihopSyncState.objects.filter(provider="hollihop").first()
    if not state or not state.initial_sync_completed:
        messages.warning(request, "Run the Initial sync first.")
        return redirect("hollihop_dashboard")
    if request.POST.get("confirm") != "MEMBERSHIPS":
        messages.error(request, "Membership reconciliation confirmation is missing.")
        return redirect("hollihop_dashboard")
    try:
        manual_membership_hollihop_sync.delay()
        activity.mark_queued("memberships")
        messages.success(request, "Relation-only Hollihop membership reconciliation was queued (Days/payments are not requested).")
    except Exception:
        messages.error(request, "Background worker is unavailable.")
    return redirect("hollihop_dashboard")


@require_POST
def full_reconciliation(request):
    precheck = _sync_precheck(request)
    if precheck:
        return precheck
    state = HollihopSyncState.objects.filter(provider="hollihop").first()
    if not state or not state.initial_sync_completed:
        messages.warning(request, "Run the Initial sync first.")
        return redirect("hollihop_dashboard")
    if request.POST.get("confirm") != "FULL":
        messages.error(request, "Full reconciliation confirmation is missing.")
        return redirect("hollihop_dashboard")
    try:
        manual_full_hollihop_reconciliation.delay()
        activity.mark_queued("full")
        messages.success(request, "Full Hollihop reconciliation was queued. This is manual only and is never run on app startup.")
    except Exception:
        messages.error(request, "Background worker is unavailable. Run: python manage.py sync_hollihop --all")
    return redirect("hollihop_dashboard")


@require_POST
def sync_now(request):
    """Backward-compatible action used by older templates/bookmarks."""
    state = HollihopSyncState.objects.filter(provider="hollihop").first()
    if state and state.initial_sync_completed:
        return smart_sync_now(request)
    # Old button did not include the new explicit confirmation; do not silently
    # start a full import. Redirect with a clear instruction instead.
    if not _manager_allowed(request.user):
        return HttpResponseForbidden("Manager access required.")
    messages.warning(request, "Initial synchronization now requires the explicit Initial sync button for safety.")
    return redirect("hollihop_dashboard")


@require_POST
def resend_credentials(request, user_id):
    if not _manager_allowed(request.user):
        return HttpResponseForbidden("Manager access required.")
    if request.POST.get("confirm") != "RESET":
        messages.error(request, "Confirmation missing. Password was not reset.")
        return redirect("hollihop_dashboard")
    user = get_object_or_404(User.objects.select_related("profile"), id=user_id)
    profile = user.profile
    if not (profile.hollihop_client_id or profile.hollihop_teacher_id or profile.hollihop_employee_id):
        messages.error(request, "This user is not linked to Hollihop.")
        return redirect("hollihop_dashboard")
    delivery = deliver_new_temporary_access(user)
    if delivery.overall_status == "sent":
        messages.success(request, "A new temporary password was generated and delivered.")
    else:
        messages.warning(request, f"Password was reset, but delivery status is {delivery.get_overall_status_display().lower()}.")
    return redirect("hollihop_dashboard")


@require_POST
def resolve_conflict(request, conflict_id):
    if not _manager_allowed(request.user):
        return HttpResponseForbidden("Manager access required.")
    conflict = get_object_or_404(HollihopSyncConflict, id=conflict_id, status="pending")
    action = request.POST.get("action")
    if action == "ignore":
        conflict.status = "ignored"
        conflict.save(update_fields=["status", "updated_at"])
        messages.success(request, "Conflict marked as ignored.")
        return redirect("hollihop_dashboard")
    if conflict.external_type not in {"student", "teacher", "manager", "classroom"}:
        messages.error(request, "This conflict type cannot be linked from the dashboard.")
        return redirect("hollihop_dashboard")
    try:
        user_id = int(request.POST.get("user_id") or 0)
    except ValueError:
        user_id = 0
    user = User.objects.filter(id=user_id).select_related("profile").first()
    if not user:
        messages.error(request, "Select a valid MakonBook user.")
        return redirect("hollihop_dashboard")

    if conflict.external_type == "classroom":
        is_teacher_user = bool(
            user.profile.hollihop_teacher_id is not None
            or user.groups.filter(name__in=["Teacher", "Support Teacher"]).exists()
            or user.is_staff
            or user.is_superuser
        )
        if not is_teacher_user:
            messages.error(request, "For a classroom conflict, select a MakonBook teacher user.")
            return redirect("hollihop_dashboard")
        conflict.status = HollihopSyncConflict.STATUS_RESOLVED
        conflict.resolved_user = user
        conflict.save(update_fields=["status", "resolved_user", "updated_at"])
        try:
            sync_resolved_classroom_mapping.delay(int(conflict.external_id))
            messages.success(request, "Classroom teacher mapping saved. A targeted Hollihop membership sync was queued for this EdUnit.")
        except Exception:
            messages.warning(request, "Classroom teacher mapping saved. It will be applied on the next membership reconciliation.")
        return redirect("hollihop_dashboard")

    field = {
        "student": "hollihop_client_id",
        "teacher": "hollihop_teacher_id",
        "manager": "hollihop_employee_id",
    }[conflict.external_type]
    external_id = int(conflict.external_id)
    if User.objects.filter(**{f"profile__{field}": external_id}).exclude(id=user.id).exists():
        messages.error(request, "That Hollihop ID is already linked to another user.")
        return redirect("hollihop_dashboard")
    setattr(user.profile, field, external_id)
    user.profile.save(update_fields=[field, "updated_at"])
    conflict.status = "resolved"
    conflict.resolved_user = user
    conflict.save(update_fields=["status", "resolved_user", "updated_at"])
    messages.success(request, "Hollihop object linked. The next sync will refresh the user's fields.")
    return redirect("hollihop_dashboard")


def my_attendance(request):
    if not request.user.is_authenticated:
        return redirect("login")
    records = HollihopAttendance.objects.filter(student=request.user).select_related("classroom")[:120]
    totals = HollihopAttendance.objects.filter(student=request.user).aggregate(
        total=Count("id"), present=Count("id", filter=Q(status="present")), absent=Count("id", filter=Q(status="absent"))
    )
    total = totals["total"] or 0
    totals["percentage"] = round((totals["present"] or 0) * 100 / total, 1) if total else None
    return render(request, "integrations/hollihop/my_attendance.html", {"records": records, "totals": totals})


def classroom_attendance(request, classroom_id):
    if not request.user.is_authenticated:
        return redirect("login")
    classroom = get_object_or_404(Classroom, id=classroom_id)
    if not (_manager_allowed(request.user) or can_manage_classroom(request.user, classroom)):
        return HttpResponseForbidden("You do not have access to this classroom attendance.")
    records = HollihopAttendance.objects.filter(classroom=classroom).select_related("student")[:300]
    return render(request, "integrations/hollihop/classroom_attendance.html", {"classroom": classroom, "records": records})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def webhook(request):
    if not settings.HOLLIHOP_ENABLED or settings.SCHOOL_DATA_PROVIDER != "hollihop":
        return JsonResponse({"Error": "Hollihop integration is disabled."}, status=503)
    expected = settings.HOLLIHOP_WEBHOOK_SECRET
    supplied = request.POST.get("key") or request.GET.get("key") or ""
    if not expected or not secrets.compare_digest(str(expected), str(supplied)):
        return JsonResponse({"Error": "Unauthorized."}, status=403)

    from apps.base.client_ip import client_ip
    remote_ip = client_ip(request)
    rate_key = f"hollihop:webhook-rate:{remote_ip}"
    try:
        count = cache.get(rate_key, 0)
        if count >= settings.HOLLIHOP_WEBHOOK_RATE_LIMIT:
            return JsonResponse({"Error": "Rate limit exceeded."}, status=429)
        if count == 0:
            cache.set(rate_key, 1, timeout=60)
        else:
            try:
                cache.incr(rate_key)
            except ValueError:
                cache.set(rate_key, count + 1, timeout=60)
    except Exception:
        return JsonResponse({"Error": "Webhook temporarily unavailable."}, status=503)

    trigger_type = request.POST.get("TriggerType") or request.GET.get("TriggerType") or ""
    object_type = request.POST.get("ObjectType") or request.GET.get("ObjectType") or ""
    object_id = request.POST.get("ObjectId") or request.GET.get("ObjectId") or ""
    allowed_triggers = {"Created", "StatusSet", "PassSet"}
    if object_type != "StudentClient" or trigger_type not in allowed_triggers:
        return JsonResponse({"ok": True, "ignored": True})
    try:
        client_id = int(object_id)
    except (TypeError, ValueError):
        return JsonResponse({"Error": "Invalid ObjectId."}, status=400)

    HollihopSyncLog.objects.create(
        event_type="webhook_received", entity_type="student", external_id=str(client_id),
        details={"trigger_type": trigger_type, "object_type": object_type},
    )
    try:
        process_student_webhook.delay(trigger_type, client_id)
    except Exception:
        # Broker unavailable. Never run the multi-request sync inside a gunicorn
        # worker (a webhook burst would exhaust the pool), and never answer "ok"
        # for an event that was not queued: 503 lets Hollihop redeliver it.
        logger.exception("Hollihop webhook could not be queued (client_id=%s)", client_id)
        return JsonResponse({"Error": "Temporarily unavailable, retry later."}, status=503)
    return JsonResponse({"ok": True})


def credential_campaign(request):
    """V105: send logins to the people the Hollihop import created — test first, then in batches."""
    from apps.integrations.models import CredentialCampaign

    from .credential_campaign import ROLES, active_campaign, eligible_users, find_test_people, overview, send_one
    from .credentials import _sms_channel_enabled
    from .tasks import run_credential_campaign_batch

    if not _manager_allowed(request.user):
        return HttpResponseForbidden("Manager access required.")
    campaign = active_campaign()
    workspace = "?workspace=admin" if request.GET.get("workspace") == "admin" or request.POST.get("workspace") == "admin" else ""

    if request.method == "POST" and request.POST.get("action") in {"check_sms", "sms_test"}:
        # V109: check the SMS provider from the site (the server wrapper cannot run manage.py).
        from .sms import SmsDeliveryError, send_sms, validate_sms_configuration

        ready, detail = validate_sms_configuration()
        if not ready:
            messages.error(request, f"SMS settings: {detail}")
        elif request.POST.get("action") == "check_sms":
            messages.success(request, f"SMS settings: {detail} Nothing was sent.")
        else:
            phone = (request.POST.get("phone") or "").strip()
            text = (request.POST.get("text") or "").strip()[:300] or "MakonBook: test SMS."
            if not phone:
                messages.error(request, "Enter a phone number for the test SMS.")
            else:
                try:
                    result = send_sms(phone, text)
                    extra = f", message id {result.message_id}" if result.message_id else ""
                    messages.success(request, f"Test SMS accepted by {result.provider}: status {result.status}{extra}. Check the phone.")
                except SmsDeliveryError as exc:
                    messages.error(request, f"Test SMS failed: {exc}")
                except Exception as exc:  # noqa: BLE001 - show the provider problem, never a 500
                    messages.error(request, f"Test SMS failed: {exc.__class__.__name__}")
        return redirect(f"{request.path}{workspace}")

    if request.method == "POST":
        action = request.POST.get("action")
        roles = [r for r in request.POST.getlist("roles") if r in ROLES]
        if action in {"test", "start"} and campaign.status == CredentialCampaign.STATUS_DRAFT:
            if not roles:
                messages.error(request, "Choose at least one group: students, teachers or managers.")
                return redirect(f"{request.path}{workspace}")
            campaign.roles = roles
            campaign.save(update_fields=["roles", "updated_at"])
        if action == "sample" and campaign.status == CredentialCampaign.STATUS_DRAFT:
            from .credential_campaign import send_sample
            from .sms import SmsDeliveryError

            phone = (request.POST.get("sample_phone") or "").strip()
            if not phone:
                messages.error(request, "Enter your phone number for the sample login SMS.")
            else:
                try:
                    result = send_sample(phone, manager=request.user)
                    campaign.test_sent_ok += 1
                    campaign.save(update_fields=["test_sent_ok", "updated_at"])
                    messages.success(request, f"Sample login SMS accepted by {result.provider}. Check that it arrived and reads well, then start sending.")
                except SmsDeliveryError as exc:
                    messages.error(request, f"Sample login SMS failed: {exc}")
                except Exception as exc:  # noqa: BLE001
                    messages.error(request, f"Sample login SMS failed: {exc.__class__.__name__}")
            return redirect(f"{request.path}{workspace}")
        if action == "test" and campaign.status == CredentialCampaign.STATUS_DRAFT:
            people, missing = find_test_people(request.POST.get("people", ""), campaign.roles)
            for user in people:
                result = send_one(user)
                status = getattr(result, "overall_status", result) or "skipped"
                if status in {"sent", "partial"}:
                    campaign.test_sent_ok += 1
                detail = ""
                if not isinstance(result, str) and result is not None:
                    detail = f" (SMS: {result.get_sms_status_display()}{', ' + result.sms_error_safe if result.sms_error_safe else ''}; e-mail: {result.get_email_status_display()})"
                level = messages.success if status in {"sent", "partial"} else messages.error
                level(request, f"Test · {user.get_full_name() or user.username}: {status}{detail}")
            campaign.save(update_fields=["test_sent_ok", "updated_at"])
            for raw in missing:
                messages.error(request, f"Test · “{raw}” is not among the people who would get a login (already sent, already logged in, or not from Hollihop).")
        elif action == "start" and campaign.status == CredentialCampaign.STATUS_DRAFT:
            if not campaign.test_sent_ok:
                messages.error(request, "Send a test to at least one person first and check that the SMS arrived.")
            elif request.POST.get("confirm") != "1":
                messages.error(request, "Tick the box to confirm that the test SMS arrived.")
            else:
                campaign.total = eligible_users(campaign.roles).count()
                campaign.status = CredentialCampaign.STATUS_RUNNING
                campaign.started_at = timezone.now()
                campaign.created_by = request.user
                campaign.save()
                run_credential_campaign_batch.delay(campaign.pk)
                messages.success(request, f"Sending started: {campaign.total} people.")
        elif action == "pause" and campaign.status == CredentialCampaign.STATUS_RUNNING:
            campaign.status = CredentialCampaign.STATUS_PAUSED
            campaign.save(update_fields=["status", "updated_at"])
            messages.success(request, "Paused. The current batch finishes, then sending stops.")
        elif action == "resume" and campaign.status == CredentialCampaign.STATUS_PAUSED:
            campaign.status = CredentialCampaign.STATUS_RUNNING
            campaign.save(update_fields=["status", "updated_at"])
            run_credential_campaign_batch.delay(campaign.pk)
            messages.success(request, "Sending resumed.")
        elif action == "stop" and campaign.status in {CredentialCampaign.STATUS_RUNNING, CredentialCampaign.STATUS_PAUSED}:
            campaign.status = CredentialCampaign.STATUS_CANCELLED
            campaign.finished_at = timezone.now()
            campaign.save(update_fields=["status", "finished_at", "updated_at"])
            messages.success(request, "Stopped. People who did not get a login yet can be sent later in a new campaign.")
        return redirect(f"{request.path}{workspace}")

    # V110: one row per person (their latest attempt), not one per retry.
    recent_failures, seen_users = [], set()
    for delivery in HollihopCredentialDelivery.objects.filter(
        overall_status__in=["failed", "partial", "no_contact"],
        created_at__gte=campaign.started_at or campaign.created_at,
    ).select_related("user").order_by("-created_at")[:200]:
        if delivery.user_id in seen_users:
            continue
        seen_users.add(delivery.user_id)
        recent_failures.append(delivery)
        if len(recent_failures) >= 30:
            break
    # V106: the duplicate warning shows only when the Duplicate accounts page has pairs.
    from apps.base.account_merge import find_duplicate_pairs

    duplicates = {"students": len(find_duplicate_pairs("students")), "staff": len(find_duplicate_pairs("staff"))}
    return render(request, "integrations/hollihop/credential_campaign.html", {
        "campaign": campaign,
        "overview": overview(),
        "roles": ROLES,
        "sms_enabled": _sms_channel_enabled(),
        "sms_provider": getattr(settings, "MAKONBOOK_SMS_PROVIDER", ""),
        "recent_failures": recent_failures,
        "past_campaigns": CredentialCampaign.objects.exclude(pk=campaign.pk)[:5],
        "workspace_query": workspace,
        "duplicates": duplicates,
        "duplicate_total": duplicates["students"] + duplicates["staff"],
    })
