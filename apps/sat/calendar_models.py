"""V116: the student's calendar feed (a secret link Google / Apple Calendar subscribe to)."""
import secrets

from django.contrib.auth.models import User
from django.db import models


def new_feed_token():
    return secrets.token_urlsafe(24)


class StudentCalendarFeed(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="calendar_feed")
    token = models.CharField(max_length=64, unique=True, default=new_feed_token)
    created_at = models.DateTimeField(auto_now_add=True)
    last_fetched_at = models.DateTimeField(null=True, blank=True)

    def reset(self):
        self.token = new_feed_token()
        self.save(update_fields=["token"])

    def __str__(self):
        return f"Calendar feed of {self.user}"
