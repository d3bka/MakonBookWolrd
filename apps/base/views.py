# base/views.py
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import SetPasswordForm, PasswordChangeForm
from django.core.mail import EmailMultiAlternatives
from django.utils.crypto import get_random_string
from django.urls import reverse
from .forms import EditProfileForm, ForgotPasswordRequestForm, PasswordResetCodeForm
from datetime import timedelta
from django.utils import timezone
from .models import EmailVerification, PasswordResetCode
from .auth_rate_limit import check_auth_rate_limit
from .decorators import *
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password, get_default_password_validators
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
import unicodedata


@login_required(login_url='/login/')
def legacy_sat_test_import_redirect(request, rest=''):
    """Keep old /sat/test-imports links as compatibility redirects only.

    New workspace pages never render under the implementation prefix.
    """
    groups = set(request.user.groups.values_list('name', flat=True))
    is_manager = request.user.is_superuser or request.user.is_staff or 'Manager' in groups
    base = '/manager/tests-import/' if is_manager else '/support-teacher/reviewer/'
    safe_rest = rest or ''
    if not is_manager and safe_rest.startswith(('published/', 'new/', 'clear-failed/')):
        safe_rest = ''
    target = base + safe_rest
    if request.META.get('QUERY_STRING'):
        target += '?' + request.META['QUERY_STRING']
    if request.method not in {'GET', 'HEAD'}:
        response = HttpResponse(status=307)
        response['Location'] = target
        return response
    return redirect(target)


@login_required(login_url='/login/')
def legacy_sat_goal_redirect(request):
    if request.method == 'POST':
        from apps.sat.views import student_goal_settings
        return student_goal_settings(request)
    target = reverse('student_dashboard_root') + '?goal=1'
    return redirect(target)

def software(request):
    return render(request, 'software.html')

@login_required(login_url='/login/')
def edit_profile(request):
    user = request.user
    action = (request.POST.get('profile_action') or 'profile').strip().lower() if request.method == 'POST' else ''
    profile_modal_open = ''

    if request.method == 'POST' and action == 'password':
        form = EditProfileForm(instance=user)
        password_form = PasswordChangeForm(user=user, data=request.POST)
        if password_form.is_valid():
            password_user = password_form.save()
            update_session_auth_hash(request, password_user)
            messages.success(request, 'Password updated. You are still signed in on this device.')
            return redirect('edit_profile')
        profile_modal_open = 'password'
    elif request.method == 'POST':
        form = EditProfileForm(request.POST, instance=user)
        password_form = PasswordChangeForm(user=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated.')
            return redirect('edit_profile')
        profile_modal_open = 'profile'
    else:
        form = EditProfileForm(instance=user)
        password_form = PasswordChangeForm(user=user)

    context = {
        'form': form,
        'password_form': password_form,
        'profile_modal_open': profile_modal_open,
    }
    use_workspace = False
    try:
        from apps.sat.student_workspace import student_workspace_context
        workspace_context = student_workspace_context(user, active='profile')
        context.update(workspace_context)
        use_workspace = bool(workspace_context.get('use_student_workspace'))
    except Exception:
        pass
    if use_workspace:
        try:
            from apps.gamification.services import gamification_shell_context
            from apps.sat.models import ClassroomMembership, StudentGoalProfile
            context['profile_classrooms'] = ClassroomMembership.objects.filter(user=user, role='student', status='approved').select_related('classroom', 'classroom__teacher')[:6]
            context['student_goal'] = StudentGoalProfile.objects.filter(user=user).select_related('dream_university').first()
            context['profile_user_profile'] = getattr(user, 'profile', None)
            context.update(gamification_shell_context(user))
        except Exception:
            pass

    if use_workspace:
        template_name = 'base/edit_profile.html'
    else:
        # Keep operational users inside the unified V50.2.7 staff shell instead
        # of dropping them back into the legacy public-page profile layout.
        try:
            from apps.sat.roles import is_teacher, is_manager, is_support_teacher, is_platform_admin
            use_staff_workspace = bool(
                is_teacher(user) or is_manager(user) or is_support_teacher(user) or is_platform_admin(user)
            )
        except Exception:
            use_staff_workspace = False
        template_name = 'base/edit_profile_staff_v527.html' if use_staff_workspace else 'base/edit_profile_legacy_v523.html'
    return render(request, template_name, context)


@login_required(login_url='/login/')
def settings_page(request):
    """One Settings experience for students and every staff role."""
    try:
        from apps.sat.student_workspace import student_workspace_context
        context = student_workspace_context(request.user, active='settings')
    except Exception:
        context = {'use_student_workspace': False}
    if not context.get('use_student_workspace'):
        try:
            from apps.sat.roles import is_teacher, is_manager, is_support_teacher, is_platform_admin
            if is_teacher(request.user) or is_manager(request.user) or is_support_teacher(request.user) or is_platform_admin(request.user):
                context['settings_base_template'] = 'sat/staff_workspace.html'
            else:
                context['settings_base_template'] = 'template.html'
        except Exception:
            context['settings_base_template'] = 'template.html'
    return render(request, 'base/settings.html', context)

PROFILE_NAME_APOSTROPHES = {"'", "’", "‘", "ʻ", "ʼ", "`", "´"}
PROFILE_NAME_SEPARATORS = PROFILE_NAME_APOSTROPHES | {"-", " "}


def _normalize_profile_name(value):
    """Normalize harmless whitespace/Unicode differences without changing casing."""
    value = unicodedata.normalize("NFC", (value or "").strip())
    return " ".join(value.split())


def _validate_profile_name(value, label):
    """Return a human-readable validation error, or None when the name is valid."""
    if not value:
        return f"Enter your {label.lower()}."

    if len(value) < 2 or len(value) > 50:
        return f"{label} must be between 2 and 50 characters."

    letter_count = 0
    for char in value:
        category = unicodedata.category(char)
        if category.startswith("L"):
            letter_count += 1
            continue
        if category.startswith("M"):
            # Combining marks are safe after NFC normalization and allow names
            # written with less-common diacritics.
            continue
        if char in PROFILE_NAME_SEPARATORS:
            continue
        return f"{label} can contain only letters, spaces, hyphens, and apostrophes."

    if letter_count < 2:
        return f"{label} must contain at least 2 letters."

    first_category = unicodedata.category(value[0])
    last_category = unicodedata.category(value[-1])
    if not first_category.startswith("L") or not (last_category.startswith("L") or last_category.startswith("M")):
        return f"{label} must start and end with a letter."

    punctuation = PROFILE_NAME_APOSTROPHES | {"-"}
    for previous, current in zip(value, value[1:]):
        if previous in punctuation and current in punctuation:
            return f"{label} has repeated punctuation."

    return None


@login_required(login_url='/login/')
@require_POST
def complete_profile_name(request):
    """Save the required display name from the post-login profile prompt."""
    from django.http import JsonResponse

    first_name = _normalize_profile_name(request.POST.get('first_name'))
    last_name = _normalize_profile_name(request.POST.get('last_name'))

    errors = {}
    first_error = _validate_profile_name(first_name, 'First name')
    last_error = _validate_profile_name(last_name, 'Last name')
    if first_error:
        errors['first_name'] = first_error
    if last_error:
        errors['last_name'] = last_error

    if errors:
        return JsonResponse({'ok': False, 'errors': errors}, status=400)

    user = request.user
    user.first_name = first_name
    user.last_name = last_name
    user.save(update_fields=['first_name', 'last_name'])

    return JsonResponse({
        'ok': True,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'full_name': user.get_full_name() or user.get_username(),
    })


def home(request):
    """Public landing page plus verified upcoming mock registrations."""
    if request.user.is_authenticated:
        return redirect('student_dashboard_root')

    from apps.sat.models import GlobalEvent
    from apps.sat.event_registration import event_confirmed_count, event_pending_hold_count, registration_for_request, registration_window, seats_left

    now_value = timezone.now()
    landing_mock_events = []
    candidates = GlobalEvent.objects.filter(
        event_type=GlobalEvent.TYPE_EVENT,
        registration_enabled=True,
        show_on_landing=True,
        is_public=True,
        status__in=['scheduled', 'live'],
    ).select_related('test').order_by('start_at', 'title')[:12]
    for event in candidates:
        if event.end_at and event.end_at < now_value and not event.always_live:
            continue
        event.landing_registration_window = registration_window(event, now_value)
        event.landing_confirmed_count = event_confirmed_count(event)
        event.landing_pending_hold_count = event_pending_hold_count(event, now_value)
        event.landing_seats_left = seats_left(event, now_value)
        event.landing_registration = registration_for_request(request, event)
        landing_mock_events.append(event)

    return render(request, 'landing/home.html', {'landing_mock_events': landing_mock_events})

@unauthenticated_user
def loginUser(request):
    if request.method == "POST":
        credential = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""

        rate = check_auth_rate_limit(request, action="login", identifier=credential)
        if not rate.allowed:
            messages.error(request, "Too many sign-in attempts. Please wait a little before trying again.")
            response = render(request, "base/login.html", {}, status=429)
            response["Retry-After"] = str(rate.retry_after)
            return response

        user = authenticate(request, username=credential, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                return redirect("student_dashboard_root")
            messages.error(request, "Your account is not active. Please contact support.")
        else:
            messages.error(request, "Username, email, phone, or password is incorrect.")
    context = {}
    return render(request, 'base/login.html', context)

@login_required(login_url="login")
def logoutUser(request):
    logout(request)
    return redirect("/login")

@unauthenticated_user
def register(request):
    """Legacy public-registration endpoint.

    Student accounts are provisioned from Hollihop. Keep the URL as a safe
    redirect for old bookmarks and links, but never create a user here.
    """
    messages.info(
        request,
        "Student accounts are created by SATMakon through Hollihop. Use the login details sent to your phone, or contact SATMakon if you need access.",
    )
    return redirect("login")


@unauthenticated_user
def forgot_password(request):
    if request.method == "POST":
        form = ForgotPasswordRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()

            rate = check_auth_rate_limit(request, action="forgot_password", identifier=email)
            if not rate.allowed:
                messages.error(request, "Too many reset-code requests. Please wait before trying again.")
                response = render(request, "base/forgot_password.html", {"form": form}, status=429)
                response["Retry-After"] = str(rate.retry_after)
                return response
            request.session["password_reset_email"] = email

            User = get_user_model()
            user = User.objects.filter(email__iexact=email, is_active=True).order_by("id").first()

            if user:
                code = get_random_string(6, allowed_chars="0123456789")
                PasswordResetCode.objects.filter(user=user, is_used=False).update(is_used=True)
                reset_code = PasswordResetCode.objects.create(
                    user=user,
                    email=email,
                    code_hash=make_password(code),
                    expires_at=timezone.now() + timedelta(minutes=10),
                )

                subject = "Reset your MakonBook password"
                from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", "")
                support_email = getattr(settings, "EMAIL_HOST_USER", "") or "support@makonbook.uz"
                reset_url = request.build_absolute_uri(reverse("password_reset_confirm"))
                display_name = (user.get_full_name() or user.get_username()).strip()
                email_context = {
                    "display_name": display_name,
                    "code": code,
                    "expires_minutes": 10,
                    "reset_url": reset_url,
                    "support_email": support_email,
                    "current_year": timezone.localdate().year,
                }
                text_body = render_to_string("emails/password_reset_code.txt", email_context)
                html_body = render_to_string("emails/password_reset_code.html", email_context)

                try:
                    email_message = EmailMultiAlternatives(
                        subject=subject,
                        body=text_body,
                        from_email=from_email,
                        to=[user.email],
                        reply_to=[support_email] if support_email else None,
                    )
                    email_message.attach_alternative(html_body, "text/html")
                    email_message.send(fail_silently=False)
                except Exception as exc:
                    reset_code.delete()
                    if settings.DEBUG:
                        messages.error(request, f"Email sending failed: {exc}")
                    else:
                        messages.error(request, "Email sending failed. Please contact support.")
                    return redirect("forgot_password")

            messages.success(request, "If this email exists, a confirmation code has been sent.")
            return redirect("password_reset_confirm")
    else:
        form = ForgotPasswordRequestForm()

    return render(request, "base/forgot_password.html", {"form": form})


@unauthenticated_user
def password_reset_confirm(request):
    initial_email = request.session.get("password_reset_email", "")

    if request.method == "POST":
        form = PasswordResetCodeForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()
            code = form.cleaned_data["code"].strip()
            new_password = form.cleaned_data["new_password"]

            rate = check_auth_rate_limit(request, action="reset_password", identifier=email)
            if not rate.allowed:
                messages.error(request, "Too many password reset attempts. Please wait before trying again.")
                response = render(request, "base/password_reset_confirm.html", {"form": form}, status=429)
                response["Retry-After"] = str(rate.retry_after)
                return response

            User = get_user_model()
            user = User.objects.filter(email__iexact=email, is_active=True).order_by("id").first()
            generic_error = "Invalid or expired confirmation code."

            reset_code = None
            if user:
                reset_code = PasswordResetCode.objects.filter(
                    user=user,
                    email__iexact=email,
                    is_used=False,
                ).order_by("-created_at").first()

            if not user or not reset_code or reset_code.is_expired:
                messages.error(request, generic_error)
                return render(request, "base/password_reset_confirm.html", {"form": form})

            if reset_code.attempts >= 5:
                reset_code.is_used = True
                reset_code.save(update_fields=["is_used"])
                messages.error(request, "Too many wrong attempts. Request a new code.")
                return redirect("forgot_password")

            if not check_password(code, reset_code.code_hash):
                reset_code.attempts += 1
                reset_code.save(update_fields=["attempts"])
                messages.error(request, generic_error)
                return render(request, "base/password_reset_confirm.html", {"form": form})

            try:
                validate_password(new_password, user=user)
            except ValidationError as exc:
                for error in exc.messages:
                    messages.error(request, error)
                return render(request, "base/password_reset_confirm.html", {"form": form})

            user.set_password(new_password)
            user.save(update_fields=["password"])
            if hasattr(user, "profile") and user.profile.must_change_password:
                user.profile.must_change_password = False
                user.profile.save(update_fields=["must_change_password", "updated_at"])

            reset_code.is_used = True
            reset_code.save(update_fields=["is_used"])
            PasswordResetCode.objects.filter(user=user, is_used=False).update(is_used=True)
            request.session.pop("password_reset_email", None)

            messages.success(request, "Password changed successfully. You can now sign in with your new password.")
            return redirect("login")
    else:
        form = PasswordResetCodeForm(initial={"email": initial_email})

    return render(request, "base/password_reset_confirm.html", {"form": form})


@login_required(login_url="login")
@require_POST
def temporary_password_rules(request):
    """Return live status for Django password validators.

    The password is checked only in memory and is never saved or logged.
    Final form validation remains authoritative on submit.
    """
    profile = getattr(request.user, "profile", None)
    if not profile or not getattr(profile, "must_change_password", False):
        return JsonResponse({"detail": "password_change_not_required"}, status=403)

    password = request.POST.get("password", "")
    rule_map = {
        "UserAttributeSimilarityValidator": "similarity",
        "MinimumLengthValidator": "length",
        "CommonPasswordValidator": "common",
        "NumericPasswordValidator": "numeric",
    }
    rules = {key: False for key in rule_map.values()}

    if not password:
        return JsonResponse({"rules": rules})

    for validator in get_default_password_validators():
        rule_key = rule_map.get(validator.__class__.__name__)
        if not rule_key:
            continue
        try:
            validator.validate(password, request.user)
        except ValidationError:
            rules[rule_key] = False
        else:
            rules[rule_key] = True

    return JsonResponse({"rules": rules})

@login_required(login_url="login")
def change_temporary_password(request):
    if not getattr(request.user.profile, "must_change_password", False):
        return redirect("student_dashboard_root")
    if request.method == "POST":
        rate = check_auth_rate_limit(request, action="temporary_password", identifier=str(request.user.pk))
        if not rate.allowed:
            form = SetPasswordForm(request.user, request.POST)
            messages.error(request, "Too many password-change attempts. Please wait before trying again.")
            response = render(request, "base/change_temporary_password.html", {"form": form}, status=429)
            response["Retry-After"] = str(rate.retry_after)
            return response
        form = SetPasswordForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            user.profile.must_change_password = False
            user.profile.credentials_delivery_status = "completed"
            user.profile.save(update_fields=["must_change_password", "credentials_delivery_status", "updated_at"])
            messages.success(request, "Your password has been changed successfully.")
            return redirect("student_dashboard_root")
    else:
        form = SetPasswordForm(request.user)
    return render(request, "base/change_temporary_password.html", {"form": form})


@unauthenticated_user
def activate(request, token):
    try:
        verification = EmailVerification.objects.get(token=token, is_verified=False, expires_at__gte=timezone.now())
        user = verification.user
        user.is_active = True
        user.save()
        verification.is_verified = True
        verification.save()
        messages.success(request, f"Account activated! You can now log in with {user.username}.")
    except EmailVerification.DoesNotExist:
        messages.error(request, "Invalid or expired activation link.")
    return redirect('login')

@require_POST
def submit_general_issue_report(request):
    from django.http import JsonResponse
    from django.utils import timezone
    from .models import GeneralIssueReport

    # Lightweight per-session rate limit: at most 5 submissions in one hour.
    now_ts = int(timezone.now().timestamp())
    recent = [int(ts) for ts in request.session.get("issue_report_times", []) if now_ts - int(ts) < 3600]
    if len(recent) >= 5:
        return JsonResponse({"ok": False, "error": "Too many reports. Try again later."}, status=429)

    # Honeypot field for basic bot filtering.
    if (request.POST.get("website") or "").strip():
        return JsonResponse({"ok": True})

    message_text = (request.POST.get("message") or "").strip()
    if len(message_text) < 10:
        return JsonResponse({"ok": False, "error": "Describe the problem in at least 10 characters."}, status=400)

    category = (request.POST.get("category") or "technical").strip()
    valid_categories = {value for value, _ in GeneralIssueReport.CATEGORY_CHOICES}
    if category not in valid_categories:
        category = "other"

    context_payload = {}
    raw_context = (request.POST.get("context_json") or "")[:8000].strip()
    if raw_context:
        try:
            import json
            parsed_context = json.loads(raw_context)
            if isinstance(parsed_context, dict):
                # Keep only a small, non-secret snapshot useful for reproducing the issue.
                context_payload = {}
                for key, value in list(parsed_context.items())[:30]:
                    if isinstance(value, (str, int, float, bool)) or value is None:
                        context_payload[str(key)[:80]] = value[:2000] if isinstance(value, str) else value
        except (TypeError, ValueError, json.JSONDecodeError):
            context_payload = {}

    attachment = request.FILES.get('attachment')
    if attachment:
        if attachment.size > 8 * 1024 * 1024:
            return JsonResponse({"ok": False, "error": "Attachment must be 8 MB or smaller."}, status=400)
        allowed_types = {'image/png', 'image/jpeg', 'image/webp', 'image/gif', 'application/pdf'}
        content_type = (getattr(attachment, 'content_type', '') or '').lower()
        if content_type not in allowed_types:
            return JsonResponse({"ok": False, "error": "Attach PNG, JPG, WEBP, GIF, or PDF."}, status=400)

    report = GeneralIssueReport.objects.create(
        reporter=request.user if request.user.is_authenticated else None,
        reporter_name=(request.POST.get("reporter_name") or "")[:160].strip(),
        reporter_email=(request.POST.get("reporter_email") or "")[:254].strip(),
        category=category,
        message=message_text[:4000],
        page_url=(request.POST.get("page_url") or request.META.get("HTTP_REFERER") or "")[:1000],
        page_title=(request.POST.get("page_title") or "")[:300],
        user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:1000],
        context_data=context_payload,
        attachment=attachment,
    )
    recent.append(now_ts)
    request.session["issue_report_times"] = recent
    return JsonResponse({"ok": True, "report_id": report.pk})
