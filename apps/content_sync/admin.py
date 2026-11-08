from django.contrib import admin

from .models import ContentSyncState, SyncedImage


@admin.register(ContentSyncState)
class ContentSyncStateAdmin(admin.ModelAdmin):
    list_display = ("key", "value", "last_run_at", "last_success_at")
    readonly_fields = ("key", "value", "last_run_at", "last_success_at", "last_error", "last_summary")


@admin.register(SyncedImage)
class SyncedImageAdmin(admin.ModelAdmin):
    list_display = ("source_key", "bytes", "created_at")
    search_fields = ("source_key",)
    readonly_fields = ("source_key", "url", "bytes", "created_at")
