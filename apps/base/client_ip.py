"""The one place that decides a request's client IP.

Our nginx overwrites ``X-Real-IP`` with ``$remote_addr`` on every proxied
request, so that header is trustworthy behind it. ``X-Forwarded-For`` is NOT:
nginx *appends* to whatever the client sent, so its leftmost entry is
attacker-chosen. Never use it for rate limits or audit fields.
"""


def client_ip(request, default="unknown"):
    meta = getattr(request, "META", {}) or {}
    value = (meta.get("HTTP_X_REAL_IP") or meta.get("REMOTE_ADDR") or "").strip()
    return value[:128] or default
