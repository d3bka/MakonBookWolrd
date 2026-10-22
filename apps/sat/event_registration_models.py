import uuid

from django.conf import settings
from django.db import models


class EventRegistration(models.Model):
    TYPE_MAKONBOOK = "makonbook"
    TYPE_EXTERNAL = "external"
    PARTICIPANT_TYPE_CHOICES = [
        (TYPE_MAKONBOOK, "MakonBook student"),
        (TYPE_EXTERNAL, "External participant"),
    ]

    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_CANCELLED = "cancelled"
    STATUS_ATTENDED = "attended"
    STATUS_NO_SHOW = "no_show"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending verification"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_ATTENDED, "Attended"),
        (STATUS_NO_SHOW, "No show"),
        (STATUS_EXPIRED, "Verification expired"),
    ]

    event = models.ForeignKey("sat.GlobalEvent", on_delete=models.CASCADE, related_name="registrations")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="global_event_registrations",
        null=True,
        blank=True,
    )
    guest = models.OneToOneField(
        "sat.GuestParticipant",
        on_delete=models.SET_NULL,
        related_name="event_registration",
        null=True,
        blank=True,
    )

    participant_type = models.CharField(max_length=20, choices=PARTICIPANT_TYPE_CHOICES, db_index=True)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32, blank=True, db_index=True)
    email = models.EmailField(db_index=True)
    telegram_username = models.CharField(max_length=64, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    verification_code_hash = models.CharField(max_length=128, blank=True)
    verification_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    verification_sent_at = models.DateTimeField(null=True, blank=True)
    verification_attempts = models.PositiveSmallIntegerField(default=0)
    verified_at = models.DateTimeField(null=True, blank=True)

    registration_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "user"],
                condition=models.Q(user__isnull=False),
                name="unique_user_event_registration_v5581",
            )
        ]
        indexes = [
            models.Index(fields=["event", "status"], name="eventreg_event_status_v5581"),
            models.Index(fields=["event", "email"], name="eventreg_event_email_v5581"),
            models.Index(fields=["event", "phone"], name="eventreg_event_phone_v5581"),
        ]

    def __str__(self):
        return f"{self.full_name} · {self.event} · {self.get_status_display()}"

    @property
    def registration_id(self):
        if not self.pk:
            return "MB-PENDING"
        return f"MB-{self.event.start_at:%y%m%d}-{self.pk:04d}"
