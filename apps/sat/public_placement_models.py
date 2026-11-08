from django.db import models
from django.utils import timezone


class PublicPlacementLead(models.Model):
    """Anonymous public placement lead captured before a placement attempt starts."""

    event = models.ForeignKey(
        "sat.GlobalEvent",
        on_delete=models.CASCADE,
        related_name="public_placement_leads",
    )
    guest = models.OneToOneField(
        "sat.GuestParticipant",
        on_delete=models.CASCADE,
        related_name="public_placement_lead",
    )
    attempt = models.OneToOneField(
        "sat.GlobalEventAttempt",
        on_delete=models.SET_NULL,
        related_name="public_placement_lead",
        null=True,
        blank=True,
    )
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    phone_number = models.CharField(max_length=32, db_index=True)
    consent_to_contact = models.BooleanField(default=True)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # V5616: persist Telegram message IDs per destination so START/FINISH stay
    # attached to the same attempt even after worker/container restarts.
    # Shape: {"<chat_id>": {"start_message_id": 123, "completion_message_id": 456}}
    telegram_threads = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event", "-created_at"], name="sat_pubpl_event_created"),
            models.Index(fields=["phone_number", "-created_at"], name="sat_pubpl_phone_created"),
        ]

    @property
    def full_name(self):
        return " ".join(part for part in (self.first_name, self.last_name) if part).strip()

    def __str__(self):
        return f"{self.full_name} · {self.phone_number} · {self.event.title}"


class PlacementTelegramNotification(models.Model):
    KIND_STARTED = "started"
    KIND_COMPLETED = "completed"
    KIND_CHOICES = [
        (KIND_STARTED, "Placement started"),
        (KIND_COMPLETED, "Placement completed"),
    ]

    STATUS_PENDING = "pending"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
    ]

    lead = models.ForeignKey(
        PublicPlacementLead,
        on_delete=models.CASCADE,
        related_name="telegram_notifications",
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_error = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["lead", "kind"], name="unique_public_placement_notice_kind")
        ]

    def __str__(self):
        return f"{self.lead} · {self.kind} · {self.status}"
