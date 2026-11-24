from django.shortcuts import render


class MakonErrorPageMiddleware:
    """Render MakonBook-style error pages for normal HTML requests.

    JSON/AJAX/API responses are intentionally left untouched.
    Chrome DevTools sometimes requests /.well-known/appspecific/com.chrome.devtools.json;
    that request should not be converted into a custom TemplateResponse.
    """

    HTML_ERROR_STATUSES = {400, 403, 404, 405}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return self._maybe_replace_response(request, response)

    def process_exception(self, request, exception):
        # Do not hide debug tracebacks during development. Production uses handler500.
        return None

    def _wants_html(self, request):
        accept = request.headers.get("Accept", "")
        requested_with = request.headers.get("X-Requested-With", "")
        path = request.path or ""

        if requested_with.lower() == "xmlhttprequest":
            return False
        if path.startswith("/.well-known/"):
            return False
        if path.startswith("/static/") or path.startswith("/media/"):
            return False
        if path.startswith("/sat/check_the_answers"):
            return False
        if path.startswith("/accounts/") or path.startswith("/admin/"):
            return False
        if "application/json" in accept and "text/html" not in accept:
            return False
        return True

    def _maybe_replace_response(self, request, response):
        if response.status_code not in self.HTML_ERROR_STATUSES:
            return response
        # API/webhook responses must stay machine-readable. In particular, a
        # JSON 403 from the Hollihop webhook must never be replaced with the
        # branded HTML error template (which can also require collected static
        # files that are intentionally absent in the test environment).
        content_type = (response.get("Content-Type", "") or "").lower()
        if "application/json" in content_type:
            return response
        if not self._wants_html(request):
            return response
        if getattr(response, "streaming", False):
            return response

        from apps.base.error_views import ERROR_MESSAGES, build_error_navigation

        details = ERROR_MESSAGES.get(response.status_code, ERROR_MESSAGES[404])
        navigation = build_error_navigation(request)
        # Important: return a fully rendered HttpResponse, not TemplateResponse.
        # Otherwise django.middleware.common.CommonMiddleware can access
        # response.content before render() and raise ContentNotRenderedError.
        return render(
            request,
            "errors/makon_error.html",
            {
                "status_code": response.status_code,
                "error_title": details["title"],
                "error_headline": details["headline"],
                "error_message": details["message"],
                **navigation,
            },
            status=response.status_code,
        )


class TemporaryPasswordChangeMiddleware:
    """Force server-side password change before any normal authenticated page."""

    ALLOWED_PREFIXES = (
        "/change-temporary-password/",
        "/logout/",
        "/static/",
        "/media/",
        "/admin/logout/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            try:
                must_change = bool(user.profile.must_change_password)
            except Exception:
                must_change = False
            if must_change and not any((request.path or "").startswith(prefix) for prefix in self.ALLOWED_PREFIXES):
                from django.shortcuts import redirect
                return redirect("change_temporary_password")
        return self.get_response(request)


class SystemHealthWatchMiddleware:
    """V102: at most once a minute per process, check the background parts of MakonBook
    in a daemon thread (never on the request path) and send alerts when one goes quiet.
    The Telegram bot fetches /healthz/ every minute, so this also runs at night."""

    INTERVAL_SECONDS = 60
    _next_run = 0.0
    _lock = None

    def __init__(self, get_response):
        import threading

        self.get_response = get_response
        if SystemHealthWatchMiddleware._lock is None:
            SystemHealthWatchMiddleware._lock = threading.Lock()

    def __call__(self, request):
        response = self.get_response(request)
        self._maybe_start()
        return response

    def _maybe_start(self):
        import threading
        import time

        from django.conf import settings

        if not getattr(settings, "SYSTEM_HEALTH_WATCH_ENABLED", False):
            return
        now = time.monotonic()
        with SystemHealthWatchMiddleware._lock:
            if now < SystemHealthWatchMiddleware._next_run:
                return
            SystemHealthWatchMiddleware._next_run = now + self.INTERVAL_SECONDS
        threading.Thread(target=_run_web_watch, name="makonbook-health-watch", daemon=True).start()


def _run_web_watch():
    import logging

    from django.db import connections

    try:
        from apps.base.system_health import run_watch

        run_watch("web")
    except Exception:  # noqa: BLE001 - the watcher must never take the site down
        logging.getLogger(__name__).exception("System health watch failed")
    finally:
        connections.close_all()
