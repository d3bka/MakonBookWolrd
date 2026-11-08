from django.db import models


class SyncedImage(models.Model):
    """An image copied from makonbook-api's private bucket into this app's
    public bucket. Files there are named by their bytes, so each is copied once."""

    source_key = models.CharField(max_length=300, primary_key=True)  # e.g. p/img/<sha>.png
    url = models.URLField(max_length=600)
    bytes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.source_key


class ContentSyncState(models.Model):
    """What the last sync of one part (practice, vocabulary) saw and did."""

    key = models.CharField(max_length=40, primary_key=True)
    value = models.CharField(max_length=200, blank=True, default="")  # e.g. the vocab deck version
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    last_summary = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.key
