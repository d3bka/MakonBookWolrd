from django.conf import settings
from django.contrib import admin
from django.templatetags.static import static
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.views.decorators.cache import cache_control
from django.views.generic import RedirectView, TemplateView
from apps.base import error_views
from apps.base.sitemaps import sitemaps
from django.http import HttpResponsePermanentRedirect


def favicon_redirect(request):
    # V74: browsers ask for /favicon.ico on pages without an icon link (allauth, error pages).
    return HttpResponsePermanentRedirect(static("assets/img/icons/original-icon-nobg.png"))


def healthz(request):
    """V102: the bot's uptime check. Says only whether the site and its database answer."""
    from django.db import connection
    from django.http import HttpResponse

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:  # noqa: BLE001
        response = HttpResponse("database unavailable", status=503, content_type="text/plain")
    else:
        response = HttpResponse("ok", content_type="text/plain")
    response["Cache-Control"] = "no-store"
    return response


urlpatterns = [
    # V74: browsers ask for /favicon.ico on pages without an icon link (allauth, error pages).
    # V99: resolved per request, not at import time (background processes have no static manifest).
    path("favicon.ico", favicon_redirect, name="favicon"),
    path("healthz/", healthz, name="healthz"),
    path(
        "robots.txt",
        cache_control(max_age=60 * 60 * 24)(
            TemplateView.as_view(
                template_name="robots.txt",
                content_type="text/plain",
                extra_context={"sitemap_url": f"{settings.SITE_URL}/sitemap.xml"},
            )
        ),
        name="robots_txt",
    ),
    path(
        "sitemap.xml",
        cache_control(max_age=60 * 60 * 6)(sitemap),
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),

    path("practices", RedirectView.as_view(url="/tests/", permanent=False), name="practices_alias_no_slash"),
    path("practices/", RedirectView.as_view(url="/tests/", permanent=False), name="practices_alias"),
    path("practice-tests", RedirectView.as_view(url="/tests/", permanent=False), name="practice_tests_alias_no_slash"),
    path("practice-tests/", RedirectView.as_view(url="/tests/", permanent=False), name="practice_tests_alias"),
    path("accounts/", include("allauth.urls")),

    path("", include("apps.base.urls")),
    path("sat/", include("apps.sat.urls")),
    path("rating/", include("apps.ratings.urls")),
    path("world/", include("apps.world.urls")),
    path("integrations/", include("apps.integrations.urls")),
    path("ap-classes/admin-panel/", RedirectView.as_view(pattern_name="apclasses:event_list", permanent=False), name="ap_admin_exam_list"),
    path("ap-classes/", include("apps.apclasses.urls")),
    path("admin/", admin.site.urls),
]


handler400 = error_views.bad_request
handler403 = error_views.permission_denied
handler404 = error_views.page_not_found
handler500 = error_views.server_error
