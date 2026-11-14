"""V70: Admin/Manager page that switches the platform-wide seasonal theme."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.base.models import SeasonalTheme
from apps.base.seasons import SEASON_KEYS, SEASONS, can_change_season, current_season, season_for_date, set_season_mode


@login_required
@require_http_methods(["GET", "POST"])
def seasonal_theme_settings(request):
    if not can_change_season(request.user):
        return HttpResponseForbidden("Only Admins and Managers can change the seasonal theme.")

    if request.method == "POST":
        mode = (request.POST.get("mode") or "").strip()
        try:
            set_season_mode(mode, request.user)
        except ValueError:
            messages.error(request, "Unknown theme.")
        else:
            label = "Automatic" if mode == SeasonalTheme.MODE_AUTO else SEASONS[mode]["label"]
            messages.success(request, f"Seasonal theme set to {label}.")
        return redirect("manager_seasonal_theme")

    state = current_season()
    row = SeasonalTheme.objects.filter(pk=1).select_related("updated_by").first()
    calendar_key = season_for_date(timezone.localdate())
    return render(request, "base/seasonal_theme.html", {
        "state": state,
        "row": row,
        "calendar_season": SEASONS[calendar_key],
        "season_cards": [{**SEASONS[key], "active": state.mode == key} for key in SEASON_KEYS],
    })
