"""V102: is every part of MakonBook alive, and who gets told when one is not.

Celery stopped on 15.11 and nobody noticed for nine days. Each part now writes a
heartbeat row (``SystemHeartbeat``) about once a minute:

* ``celery``        - a Beat-scheduled task executed by the worker (proves both run);
* ``telegram_bot``  - the bot's own watch loop;
* ``web``           - the bot fetches ``/healthz/`` and records a success;
* ``broker``        - Redis answered a PING;
* ``hollihop``      - the last good Hollihop synchronization (read from its own state).

Two independent watchers judge the rows: the website (from a background thread
started by ``SystemHealthWatchMiddleware``) and the Telegram bot. A part that is
quiet longer than its threshold gets one alert; a recovery gets one message; a
part that stays down is reminded every ``REMINDER_EVERY``. Alerts go to Telegram
and e-mail. ``alert_open`` is switched with a conditional UPDATE, so only the
watcher that wins the switch sends the message.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

REMINDER_EVERY = timedelta(hours=6)
WEB_WATCHED = ("broker", "celery", "telegram_bot", "hollihop")
BOT_WATCHED = ("web", "celery")


@dataclass(frozen=True)
class Component:
    key: str
    label: str
    threshold: timedelta
    impact: str
    hint: str
    depends_on: str = ""


def _hollihop_threshold() -> timedelta:
    interval = int(getattr(settings, "HOLLIHOP_SYNC_INTERVAL_MINUTES", 5) or 5)
    return timedelta(minutes=max(60, interval * 4))


COMPONENTS = {
    "web": Component(
        "web", "Website", timedelta(minutes=5),
        "Students and staff cannot open MakonBook.",
        "On the server: sudo makonbook ps, then sudo makonbook logs web.",
    ),
    "broker": Component(
        "broker", "Redis (job queue)", timedelta(minutes=3),
        "Background jobs cannot be queued.",
        "On the server: sudo makonbook ps. Redis is started from docker-compose.override.yml.",
    ),
    "celery": Component(
        "celery", "Celery worker and Beat", timedelta(minutes=5),
        "Hollihop sync, reminders, test imports and other background jobs do not run.",
        "On the server: sudo makonbook ps, then sudo makonbook logs celery-worker.",
        depends_on="broker",
    ),
    "telegram_bot": Component(
        "telegram_bot", "Telegram bot", timedelta(minutes=5),
        "Placement notifications and the admin bot do not work.",
        "On the server: sudo makonbook logs telegram-bot.",
    ),
    "hollihop": Component(
        "hollihop", "Hollihop synchronization", timedelta(hours=1),
        "New students, groups and attendance from Hollihop do not reach MakonBook.",
        "Open Hollihop in the Admin workspace and check the last error.",
        depends_on="celery",
    ),
}


# --------------------------------------------------------------------------- heartbeats

def beat(component: str, **detail) -> None:
    """Record that ``component`` is alive now. Never raises."""
    from apps.base.models import SystemHeartbeat

    try:
        now = timezone.now()
        updated = SystemHeartbeat.objects.filter(component=component).update(last_seen=now, detail=detail)
        if not updated:
            SystemHeartbeat.objects.get_or_create(component=component, defaults={"last_seen": now, "detail": detail})
    except Exception:  # noqa: BLE001 - a heartbeat must never break the caller
        logger.exception("Could not record the %s heartbeat", component)


def check_broker() -> dict:
    """PING the Celery broker and read the queue length. Records the ``broker`` heartbeat."""
    url = getattr(settings, "CELERY_BROKER_URL", "") or ""
    if not url.startswith(("redis://", "rediss://")):
        return {"configured": False, "ok": False, "queued": None, "error": ""}
    try:
        import redis

        client = redis.Redis.from_url(url, socket_timeout=2, socket_connect_timeout=2)
        try:
            client.ping()
            queued = int(client.llen("celery"))
        finally:
            client.close()
    except Exception as exc:  # noqa: BLE001
        return {"configured": True, "ok": False, "queued": None, "error": exc.__class__.__name__}
    beat("broker", queued=queued)
    return {"configured": True, "ok": True, "queued": queued, "error": ""}


def check_site() -> bool:
    """Fetch /healthz/ like a visitor would. Records the ``web`` heartbeat on success."""
    url = getattr(settings, "MONITORING_SITE_CHECK_URL", "")
    if not url:
        return False
    request = urllib.request.Request(url, headers={"User-Agent": "MakonBookHealthCheck/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - our own URL
            ok = response.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        ok = False
    if ok:
        beat("web", via="healthz")
    return ok


# --------------------------------------------------------------------------- evaluation

def _enabled(key: str) -> bool:
    if key == "telegram_bot":
        return bool(os.getenv("TELEGRAM_BOT_TOKEN"))
    if key == "web":
        return bool(getattr(settings, "MONITORING_SITE_CHECK_URL", ""))
    if key == "broker":
        return (getattr(settings, "CELERY_BROKER_URL", "") or "").startswith(("redis://", "rediss://"))
    if key == "hollihop":
        if not getattr(settings, "HOLLIHOP_ENABLED", False):
            return False
        from apps.integrations.models import HollihopSyncState

        return HollihopSyncState.objects.filter(provider="hollihop", initial_sync_completed=True).exists()
    return True


def _hollihop_last_good():
    from apps.integrations.models import HollihopSyncState

    state = HollihopSyncState.objects.filter(provider="hollihop").first()
    if not state:
        return None, {}
    times = [t for t in (state.last_successful_sync, state.last_incremental_sync) if t]
    detail = {"status": state.get_last_status_display(), "error": state.last_error_safe}
    return (max(times) if times else None), detail


def _threshold(key: str) -> timedelta:
    return _hollihop_threshold() if key == "hollihop" else COMPONENTS[key].threshold


@dataclass
class Status:
    key: str
    label: str
    state: str  # ok | down | waiting | off
    last_seen: object = None
    quiet_minutes: int | None = None
    detail: dict = field(default_factory=dict)
    impact: str = ""
    hint: str = ""
    alert_open: bool = False

    @property
    def is_ok(self) -> bool:
        return self.state == "ok"


def evaluate(key: str, now=None, rows=None) -> Status:
    from apps.base.models import SystemHeartbeat

    now = now or timezone.now()
    spec = COMPONENTS[key]
    status = Status(key, spec.label, "off", impact=spec.impact, hint=spec.hint)
    if not _enabled(key):
        return status
    row = (rows or {}).get(key) if rows is not None else SystemHeartbeat.objects.filter(component=key).first()
    status.alert_open = bool(row and row.alert_open)
    if key == "hollihop":
        last_seen, status.detail = _hollihop_last_good()
    else:
        last_seen = row.last_seen if row else None
        status.detail = dict(row.detail or {}) if row else {}
    status.last_seen = last_seen
    reference = last_seen or (row.created_at if row else None)
    if reference is None:
        status.state = "waiting"
        return status
    quiet = now - reference
    status.quiet_minutes = max(0, int(quiet.total_seconds() // 60))
    if last_seen and quiet <= _threshold(key):
        status.state = "ok"
    elif last_seen is None and quiet <= _threshold(key):
        status.state = "waiting"
    else:
        status.state = "down"
    return status


def collect_status() -> list[Status]:
    """Live status of every part, for the admin page. Also refreshes the broker heartbeat."""
    from apps.base.models import SystemHeartbeat

    broker = check_broker()
    now = timezone.now()
    rows = {row.component: row for row in SystemHeartbeat.objects.all()}
    statuses = [evaluate(key, now, rows) for key in ("web", "broker", "celery", "telegram_bot", "hollihop")]
    by_key = {s.key: s for s in statuses}
    web = by_key["web"]
    if web.state != "off":
        # The page itself is proof that the site answers.
        web.state, web.quiet_minutes = "ok", 0
    if broker["configured"]:
        by_key["broker"].detail = {**by_key["broker"].detail, "queued": broker["queued"], "error": broker["error"]}
        if broker["ok"]:
            by_key["broker"].state, by_key["broker"].quiet_minutes = "ok", 0
        else:
            # A live PING just failed: no need to wait for the heartbeat to go stale.
            by_key["broker"].state = "down"
    celery = by_key["celery"]
    if celery.state == "down" and broker["ok"]:
        celery.detail = {
            **celery.detail,
            "diagnosis": (
                f"{broker['queued']} jobs are waiting in the queue: the worker is not taking them."
                if broker["queued"] else
                "The queue is empty: Celery Beat is probably not scheduling jobs, or the worker is stopped."
            ),
        }
    return statuses


# --------------------------------------------------------------------------- alerts

def _split(raw: str) -> list[str]:
    seen = []
    for item in (raw or "").replace(";", ",").split(","):
        item = item.strip()
        if item and item not in seen:
            seen.append(item)
    return seen


def alert_recipients() -> dict:
    """Telegram chats and e-mail addresses that receive alerts."""
    from django.contrib.auth.models import User

    chats = _split(getattr(settings, "MONITORING_TELEGRAM_CHAT_ID", ""))
    chat_source = "MONITORING_TELEGRAM_CHAT_ID"
    if not chats:
        try:
            from apps.telegram_bot.models import TelegramAdmin

            chats = [str(i) for i in TelegramAdmin.objects.filter(is_active=True, is_admin=True).values_list("telegram_id", flat=True)]
        except Exception:  # noqa: BLE001
            chats = []
        chat_source = "Telegram admins of the bot"
    emails = _split(getattr(settings, "MONITORING_ALERT_EMAILS", ""))
    email_source = "MONITORING_ALERT_EMAILS"
    if not emails:
        emails = sorted({e for e in User.objects.filter(is_active=True, is_superuser=True).exclude(email="").values_list("email", flat=True)})
        email_source = "superusers"
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        chats, chat_source = [], "no TELEGRAM_BOT_TOKEN"
    return {"telegram": chats, "telegram_source": chat_source, "emails": emails, "email_source": email_source}


def _send_telegram(chat_id: str, text: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    body = json.dumps({"chat_id": chat_id, "text": text, "disable_web_page_preview": True}).encode()
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=body, headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - fixed Telegram API host
        if response.status != 200:
            raise RuntimeError(f"Telegram answered {response.status}")


def send_alert(text: str, subject: str = "MakonBook system alert") -> dict:
    """Send ``text`` to every recipient. Returns how many deliveries worked."""
    from django.core.mail import send_mail

    recipients = alert_recipients()
    report = {"telegram_sent": 0, "email_sent": 0, "failed": 0}
    for chat in recipients["telegram"]:
        try:
            _send_telegram(chat, text)
            report["telegram_sent"] += 1
        except Exception as exc:  # noqa: BLE001
            report["failed"] += 1
            logger.warning("System alert to Telegram chat failed: %s", exc.__class__.__name__)
    if recipients["emails"]:
        try:
            send_mail(subject, text, None, recipients["emails"], fail_silently=False)
            report["email_sent"] = len(recipients["emails"])
        except Exception as exc:  # noqa: BLE001
            report["failed"] += 1
            logger.warning("System alert e-mail failed: %s", exc.__class__.__name__)
    report["delivered"] = report["telegram_sent"] + report["email_sent"]
    return report


def _page_link() -> str:
    try:
        from django.urls import reverse

        return f"{settings.SITE_URL}{reverse('admin_system_health')}"
    except Exception:  # noqa: BLE001
        return ""


def _duration(delta: timedelta) -> str:
    minutes = max(1, int(delta.total_seconds() // 60))
    if minutes < 120:
        return f"{minutes} min"
    hours = minutes / 60
    return f"{hours:.0f} h" if hours < 48 else f"{hours / 24:.0f} days"


def _down_text(status: Status, *, reminder: bool, since) -> str:
    head = "Still down" if reminder else "Not working"
    quiet = f" for {_duration(timezone.now() - since)}" if since else ""
    lines = [f"🔴 MakonBook · {head}: {status.label}{quiet}.", status.impact]
    if status.detail.get("diagnosis"):
        lines.append(status.detail["diagnosis"])
    if status.key == "hollihop" and status.detail.get("error"):
        lines.append(f"Last error: {status.detail['error']}")
    lines.append(status.hint)
    link = _page_link()
    if link:
        lines.append(link)
    return "\n".join(line for line in lines if line)


def run_watch(source: str, watched=None, now=None) -> list[str]:
    """Record ``source``'s own heartbeat, judge ``watched`` parts and send alerts.

    The website checks Redis itself; the bot fetches /healthz/ for the ``web`` row.
    Returns the messages this call sent (for tests and logs).
    """
    from apps.base.models import SystemHeartbeat

    beat(source)
    if source == "web":
        check_broker()
    elif source == "telegram_bot":
        check_site()
    now = now or timezone.now()
    watched = tuple(watched or (WEB_WATCHED if source == "web" else BOT_WATCHED))
    for key in watched:
        if _enabled(key):
            SystemHeartbeat.objects.get_or_create(component=key)
    keys = {*watched, "broker", "celery"}
    rows = {row.component: row for row in SystemHeartbeat.objects.filter(component__in=keys)}
    states = {key: evaluate(key, now, rows) for key in keys}
    sent = []
    for key in watched:
        status = states[key]
        parent = COMPONENTS[key].depends_on
        parent_down = bool(parent and states[parent].state == "down")
        row_qs = SystemHeartbeat.objects.filter(component=key)
        if status.state == "down" and not parent_down:
            if row_qs.filter(alert_open=False).update(alert_open=True, down_since=status.last_seen or now, alerted_at=now):
                text = _down_text(status, reminder=False, since=status.last_seen)
                if send_alert(text, subject=f"MakonBook: {status.label} is not working")["delivered"]:
                    sent.append(text)
                else:
                    # Nobody got it: let the next check try again.
                    row_qs.update(alert_open=False, alerted_at=None)
            elif row_qs.filter(alert_open=True, alerted_at__lt=now - REMINDER_EVERY).update(alerted_at=now):
                row = row_qs.first()
                text = _down_text(status, reminder=True, since=row.down_since if row else None)
                send_alert(text, subject=f"MakonBook: {status.label} is still not working")
                sent.append(text)
        elif status.state == "ok":
            row = row_qs.filter(alert_open=True).first()
            if row and row_qs.filter(alert_open=True).update(alert_open=False, alerted_at=now):
                was = f" (was down {_duration(now - row.down_since)})" if row.down_since else ""
                text = f"🟢 MakonBook · Working again: {status.label}{was}."
                send_alert(text, subject=f"MakonBook: {status.label} works again")
                sent.append(text)
        elif status.state == "off":
            row_qs.update(alert_open=False)
    return sent


def any_alert_open() -> bool:
    from apps.base.models import SystemHeartbeat

    try:
        return SystemHeartbeat.objects.filter(alert_open=True).exists()
    except Exception:  # noqa: BLE001
        return False
