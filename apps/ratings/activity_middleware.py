"""Count unique authenticated users who actually browse MakonBook.

Starts accumulating after V61 deployment. Never claims historical activity.
No request body, IP or session token is saved.
"""
import logging
from datetime import timedelta

from django.core.cache import cache
from django.db import IntegrityError
from django.utils import timezone

from .models import UserActivityDay

logger = logging.getLogger(__name__)


class UserActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user_id = request.user.pk if request.user.is_authenticated and request.user.is_active else None
        response = self.get_response(request)
        if user_id and response.status_code < 400 and not request.path.startswith(('/static/', '/media/', '/admin/', '/logout/')):
            day = timezone.localdate()
            key = f'mb61:activity:{user_id}:{day}'
            try:
                if cache.add(key, '1', timeout=600):
                    now = timezone.now()
                    obj, created = UserActivityDay.objects.get_or_create(
                        user_id=user_id, date=day,
                        defaults={'first_seen_at': now, 'last_seen_at': now},
                    )
                    if not created and now - obj.last_seen_at >= timedelta(minutes=5):
                        UserActivityDay.objects.filter(pk=obj.pk).update(last_seen_at=now)
            except Exception:
                # Analytics must never break application traffic.
                logger.exception('Failed to record authenticated activity')
        return response
