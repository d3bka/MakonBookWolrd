from django.apps import AppConfig


class ContentSyncConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.content_sync"
    label = "content_sync"
    verbose_name = "makonbook-api content sync"
