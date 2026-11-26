"""V115: manager page for the parents' weekly Telegram report."""
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.sat.roles import is_manager, is_platform_admin

from .parent_reports import bot_token, overview


@login_required(login_url="/login/")
def manager_parent_reports(request):
    if not (is_manager(request.user) or is_platform_admin(request.user)):
        return HttpResponseForbidden("Manager access required.")
    username = getattr(settings, "TELEGRAM_PARENT_BOT_USERNAME", "")
    return render(request, "ratings/manager_parent_reports.html", {
        "data": overview(),
        "bot_enabled": bool(bot_token()),
        "bot_username": username,
        "bot_link": f"https://t.me/{username}" if username else "",
    })
