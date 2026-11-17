"""V84: public MakonBook sign-up with an email code.

* The account is created only after the 6-digit code from the email is entered, so an
  unconfirmed address never blocks its real owner.
* One email = one account (case-insensitive), across every existing account.
* A new account is a regular free student: the first practice tests, the first
  Admissions lessons. Current SATMakon students then link their SATMakon account with
  an SMS code (apps/base/satmakon_link.py) to get full access and their classrooms.
"""
import re
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import get_random_string

from apps.integrations.hollihop.normalization import email_is_valid, normalize_email

from .models import PendingRegistration

MAX_CODE_ATTEMPTS = 5
MAX_SENDS = 5


class RegistrationError(Exception):
    pass


def email_taken(email):
    return get_user_model().objects.filter(email__iexact=normalize_email(email)).exists()


def new_code():
    return get_random_string(6, allowed_chars="0123456789")


def unique_username(email):
    User = get_user_model()
    base = re.sub(r"[^a-z0-9._]+", "", normalize_email(email).split("@")[0])[:24] or "student"
    if base[0].isdigit() or base.startswith(("hstu", "htea", "hman")):
        base = f"mb.{base}"[:24]
    candidate, n = base, 1
    while User.objects.filter(username__iexact=candidate).exists():
        n += 1
        candidate = f"{base[:24]}{n}"
    return candidate


def send_code_email(pending, code):
    context = {
        "first_name": pending.first_name, "code": code, "expires_minutes": 15,
        "support_email": getattr(settings, "EMAIL_HOST_USER", "") or "support@makonbook.uz",
        "current_year": timezone.localdate().year,
    }
    message = EmailMultiAlternatives(
        subject="Your MakonBook sign-up code",
        body=render_to_string("emails/registration_code.txt", context),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", ""),
        to=[pending.email],
    )
    message.attach_alternative(render_to_string("emails/registration_code.html", context), "text/html")
    message.send(fail_silently=False)


def start_registration(*, first_name, last_name, email, password):
    """Create (or refresh) a pending sign-up and email its code. Returns the pending row."""
    email = normalize_email(email)
    if not email_is_valid(email):
        raise RegistrationError("Enter a valid email address.")
    if email_taken(email):
        raise RegistrationError("An account with this email already exists. Log in or reset your password.")
    code = new_code()
    with transaction.atomic():
        PendingRegistration.objects.filter(email__iexact=email, completed_at__isnull=True).delete()
        pending = PendingRegistration.objects.create(
            email=email, first_name=first_name.strip()[:150], last_name=last_name.strip()[:150],
            password_hash=make_password(password), code_hash=make_password(code),
        )
    send_code_email(pending, code)
    return pending


def resend_code(pending):
    if pending.completed_at or pending.sends >= MAX_SENDS:
        raise RegistrationError("Too many codes for this sign-up. Start again in a little while.")
    code = new_code()
    pending.code_hash = make_password(code)
    pending.attempts = 0
    pending.sends += 1
    pending.expires_at = timezone.now() + timedelta(minutes=15)
    pending.save(update_fields=["code_hash", "attempts", "sends", "expires_at"])
    send_code_email(pending, code)


def confirm_registration(pending, code):
    """Check the code and create the account. Returns the new User."""
    if pending.completed_at:
        raise RegistrationError("This sign-up is already complete. Log in.")
    if pending.is_expired:
        raise RegistrationError("The code has expired. Send a new one.")
    if pending.attempts >= MAX_CODE_ATTEMPTS:
        raise RegistrationError("Too many wrong codes. Send a new one.")
    if not check_password(str(code or "").strip(), pending.code_hash):
        pending.attempts += 1
        pending.save(update_fields=["attempts"])
        raise RegistrationError("The code is not correct.")
    User = get_user_model()
    with transaction.atomic():
        if User.objects.select_for_update().filter(email__iexact=pending.email).exists():
            raise RegistrationError("An account with this email already exists. Log in or reset your password.")
        user = User(username=unique_username(pending.email), email=pending.email,
                    first_name=pending.first_name, last_name=pending.last_name, is_active=True)
        user.password = pending.password_hash
        user.save()
        profile = user.profile
        profile.self_registered = True
        profile.email_verified_at = timezone.now()
        profile.save(update_fields=["self_registered", "email_verified_at"])
        pending.completed_at = timezone.now()
        pending.save(update_fields=["completed_at"])
    return user
