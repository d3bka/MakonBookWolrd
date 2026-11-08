from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect


class WorldAvailabilityMiddleware:
    """Temporarily close MakonBook World without removing its routes or data."""

    message = "MakonBook World is upcoming. Competitive games will be available soon."

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ""
        is_world_route = path == "/world" or path.startswith("/world/")
        if is_world_route and not getattr(settings, "MAKONBOOK_WORLD_ENABLED", False):
            wants_json = (
                request.method != "GET"
                or request.headers.get("X-Requested-With") == "XMLHttpRequest"
                or "application/json" in request.headers.get("Accept", "")
            )
            if wants_json:
                return JsonResponse(
                    {
                        "ok": False,
                        "code": "world_upcoming",
                        "error": self.message,
                    },
                    status=423,
                )
            messages.info(request, self.message)
            return redirect("student_dashboard_root")
        return self.get_response(request)
