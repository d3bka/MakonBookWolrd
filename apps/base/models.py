from django.db import models

from apps.base.upload_paths import RandomUploadPath
from django.contrib.auth.models import User
import uuid
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import timedelta


def email_verification_expiry():
    return timezone.now() + timedelta(hours=24)


def password_reset_expiry():
    return timezone.now() + timedelta(minutes=10)


def referral_code_default():
    # Short enough to share manually, random enough to avoid predictable IDs.
    return uuid.uuid4().hex[:10].upper()


class EmailVerification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    expires_at = models.DateTimeField(default=email_verification_expiry)

    def __str__(self):
        return f"{self.user.username} - {self.token}"


def registration_code_expiry():
    return timezone.now() + timedelta(minutes=15)


def satmakon_link_code_expiry():
    return timezone.now() + timedelta(minutes=10)


class PendingRegistration(models.Model):
    """V84: a sign-up waiting for its email code. The User is created only after the
    code is confirmed, so an unconfirmed address never blocks the real owner."""

    email = models.EmailField(db_index=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    password_hash = models.CharField(max_length=128)
    code_hash = models.CharField(max_length=128)
    attempts = models.PositiveSmallIntegerField(default=0)
    sends = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=registration_code_expiry)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Sign-up {self.email}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at


class SatmakonLinkCode(models.Model):
    """V84: an SMS code that proves a self-registered student owns the phone of a
    SATMakon (Hollihop) student account before that account is joined to theirs."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="satmakon_link_codes")
    phone = models.CharField(max_length=32)
    code_hash = models.CharField(max_length=128)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=satmakon_link_code_expiry)
    verified_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"SATMakon link for {self.user_id}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at


class PasswordResetCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_codes")
    email = models.EmailField()
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=password_reset_expiry)
    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email", "is_used", "expires_at"]),
            models.Index(fields=["user", "is_used", "created_at"]),
        ]

    def __str__(self):
        return f"Password reset for {self.email}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    english_time_minutes = models.PositiveIntegerField(
        default=32,
        help_text="Time limit for English section in minutes (default: 32)"
    )
    math_time_minutes = models.PositiveIntegerField(
        default=35,
        help_text="Time limit for Math section in minutes (default: 35)"
    )
    middle_name = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(max_length=32, null=True, blank=True)
    hollihop_client_id = models.BigIntegerField(null=True, blank=True, unique=True)
    hollihop_teacher_id = models.BigIntegerField(null=True, blank=True, unique=True)
    hollihop_employee_id = models.BigIntegerField(null=True, blank=True, unique=True)
    hollihop_status = models.CharField(max_length=150, blank=True)
    hollihop_created = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=False)
    credentials_delivery_status = models.CharField(max_length=30, default="not_applicable", db_index=True)
    credentials_last_sent_at = models.DateTimeField(null=True, blank=True)
    hollihop_last_synced_at = models.DateTimeField(null=True, blank=True)
    # V84: public self-registration. A self-registered account proved its email with a
    # code; Hollihop sync never overwrites a verified email and never links an
    # unverified self-registered account by contact data.
    self_registered = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    def is_offline_user(self):
        return self.user.groups.filter(name="OFFLINE").exists()

    def get_english_time_seconds(self):
        return self.english_time_minutes * 60

    def get_math_time_seconds(self):
        return self.math_time_minutes * 60


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, "profile"):
        instance.profile.save()
    else:
        UserProfile.objects.get_or_create(user=instance)

class GeneralIssueReport(models.Model):
    CATEGORY_CHOICES = [
        ("technical", "Technical problem"),
        ("content", "Question or content problem"),
        ("account", "Account or access problem"),
        ("rating", "Rating problem"),
        ("suggestion", "Suggestion"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("new", "New"),
        ("reviewing", "Reviewing"),
        ("resolved", "Resolved"),
        ("rejected", "Rejected"),
    ]

    reporter = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="general_issue_reports",
    )
    reporter_name = models.CharField(max_length=160, blank=True)
    reporter_email = models.EmailField(blank=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="technical")
    message = models.TextField(max_length=4000)
    page_url = models.CharField(max_length=1000, blank=True)
    page_title = models.CharField(max_length=300, blank=True)
    user_agent = models.CharField(max_length=1000, blank=True)
    context_data = models.JSONField(default=dict, blank=True)
    attachment = models.FileField(upload_to=RandomUploadPath("issue_reports"), blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new", db_index=True)
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"], name="base_issue_status_date")]

    def __str__(self):
        return f"Issue #{self.pk} - {self.get_category_display()}"


class ReferralInvite(models.Model):
    """A referral becomes earned only after the invited student joins a classroom."""
    referrer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sent_referral_invites"
    )
    referred_user = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="referral_invite"
    )
    code = models.CharField(max_length=12, unique=True, default=referral_code_default, db_index=True)
    activated_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_activated(self):
        return bool(self.activated_at)

    def __str__(self):
        state = "active" if self.activated_at else "pending"
        return f"{self.referrer.username} · {self.code} · {state}"


class SeasonalTheme(models.Model):
    """V70: one platform-wide seasonal theme (singleton row, pk=1).

    ``mode`` is either ``auto`` (season follows the Tashkent calendar) or a
    season pinned by an Admin/Manager. Read it through ``apps.base.seasons``,
    which caches the row; never query this model per request directly.
    """

    MODE_AUTO = "auto"
    MODE_CHOICES = (
        (MODE_AUTO, "Automatic (calendar)"),
        ("winter", "Winter"),
        ("spring", "Spring"),
        ("summer", "Summer"),
        ("autumn", "Autumn"),
    )

    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=MODE_AUTO)
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Seasonal theme"
        verbose_name_plural = "Seasonal theme"

    def __str__(self):
        return f"Seasonal theme: {self.get_mode_display()}"


class HolidayTheme(models.Model):
    """V85: holiday decor and greetings on the public pages (and the workspace).

    Rows hold concrete dates per year so holidays with moving dates (Ramazon and
    Qurbon Hayit) can be corrected by a manager once they are officially announced.
    When several holidays overlap, the shortest window wins.
    """

    KEY_CHOICES = (
        ("new-year", "New Year"),
        ("navruz", "Navruz"),
        ("ramazon-hayit", "Ramazon Hayit (Eid al-Fitr)"),
        ("qurbon-hayit", "Qurbon Hayit (Eid al-Adha)"),
        ("womens-day", "8 March"),
        ("independence", "Independence Day"),
        ("teachers-day", "Teachers' Day"),
        ("constitution", "Constitution Day"),
    )

    key = models.CharField(max_length=20, choices=KEY_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    note = models.CharField(max_length=200, blank=True, help_text="For example: date confirmed by decree.")

    class Meta:
        ordering = ["start_date"]
        verbose_name = "Holiday theme"
        verbose_name_plural = "Holiday themes"

    def __str__(self):
        return f"{self.get_key_display()} {self.start_date:%Y-%m-%d} – {self.end_date:%Y-%m-%d}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValidationError({"end_date": "The last day cannot be before the first day."})
            if (self.end_date - self.start_date).days > 31:
                raise ValidationError({"end_date": "A holiday theme can last at most a month."})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from apps.base.seasons import clear_holiday_cache

        clear_holiday_cache()

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        from apps.base.seasons import clear_holiday_cache

        clear_holiday_cache()
        return result


class SystemHeartbeat(models.Model):
    """V102: one row per background part of MakonBook (Celery, the Telegram bot, the site).

    Each part writes ``last_seen`` about once a minute. The watchers compare it with a
    threshold and send one alert when a part goes quiet, and one when it is back.
    ``alert_open`` is flipped with a conditional UPDATE, so several web workers and the
    bot can watch at the same time without sending the same alert twice.
    """

    component = models.CharField(max_length=40, unique=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    alert_open = models.BooleanField(default=False)
    down_since = models.DateTimeField(null=True, blank=True)
    alerted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["component"]

    def __str__(self):
        return f"{self.component} · {self.last_seen or 'never'}"
