"""V93: how many times a student may start each SAT practice test, and extra attempts from teachers."""
from django.conf import settings
from django.db import models
from django.db.models import Q


class SatAttemptUse(models.Model):
    """One started SAT practice-test attempt that counts toward the student's limit.

    Rows exist only for attempts started after the limit was introduced, so every
    student begins with a full allowance. An attempt that is discarded because it was
    abandoned without a single answer gives the attempt back.
    """

    SOURCE_START = "start"
    SOURCE_RETAKE = "retake"
    SOURCE_SECTION = "section"
    SOURCE_CHOICES = [
        (SOURCE_START, "Start"),
        (SOURCE_RETAKE, "Full retake"),
        (SOURCE_SECTION, "Section retake"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sat_attempt_uses")
    test = models.ForeignKey("sat.Test", on_delete=models.CASCADE, related_name="attempt_uses")
    attempt_id = models.UUIDField()
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default=SOURCE_START)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "test", "attempt_id"], name="uniq_sat_attempt_use")]
        indexes = [models.Index(fields=["user", "test"], name="sat_attuse_user_test")]

    def __str__(self):
        return f"{self.user_id} · {self.test_id} · {self.attempt_id}"


class SatAttemptRequest(models.Model):
    """A student asks their teacher for more attempts at one SAT practice test."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    STATUS_CHOICES = [
        (PENDING, "Waiting for the teacher"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
        (WITHDRAWN, "Withdrawn"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sat_attempt_requests")
    test = models.ForeignKey("sat.Test", on_delete=models.CASCADE, related_name="attempt_requests")
    message = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    granted = models.PositiveSmallIntegerField(default=0)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sat_attempt_decisions",
    )
    decision_note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "test"], condition=Q(status="pending"), name="uniq_pending_sat_attempt_request",
            ),
        ]

    def __str__(self):
        return f"{self.user_id} · {self.test_id} · {self.status}"
