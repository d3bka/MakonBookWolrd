"""Privacy-preserving descriptions for Hollihop synchronization diagnostics.

Never store raw API exceptions, response bodies, headers, credentials or
provider records in the manager-facing audit log.
"""
from __future__ import annotations

import re

_KINDS = {
    "IntegrityError": "Database constraint conflict (for example, a duplicate mapping). Check the affected object and existing links.",
    "OperationalError": "Database operation failed. Check the database connection and server logs.",
    "DataError": "A value does not fit a database field. Check the affected object's data format.",
    "ValidationError": "An imported record failed field validation. Check the affected object.",
    "KeyError": "A required field was missing from a provider record.",
    "ValueError": "A field contains an unexpected value or format.",
    "TypeError": "Hollihop returned an unexpected data structure or field type.",
    "TimeoutError": "A network/API operation timed out. Retry after checking Hollihop availability.",
    "ConnectTimeout": "The Hollihop connection timed out.",
    "ReadTimeout": "Hollihop did not respond within the read timeout.",
    "ConnectionError": "Could not connect to Hollihop. Check the network and endpoint.",
    "URLError": "Could not reach Hollihop. Check the network, DNS or endpoint.",
    "HTTPError": "Hollihop API returned an HTTP error. Check API permissions or provider availability.",
    "HollihopError": "Hollihop API reported an error. Check API access and provider availability.",
    "PermissionDenied": "Permission denied for the requested operation.",
    "DoesNotExist": "A related MakonBook record was not found.",
    "MultipleObjectsReturned": "Several local records matched a value that must be unique.",
    "InterfaceError": "A database connection or driver operation failed.",
    "DatabaseError": "A database operation failed. Check server logs for a protected traceback.",
    "JSONDecodeError": "Hollihop API returned a response that is not valid JSON.",
    "UnicodeDecodeError": "Hollihop API returned data in an unexpected encoding.",
    "AttributeError": "An expected field or object was unavailable during synchronization.",
    "AssertionError": "A synchronization consistency check failed.",
}
_TYPE_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]{0,79})(?:\b|:)")

def safe_sync_error_details(details):
    """Convert legacy or new error payloads into bounded, secret-free metadata."""
    details = details if isinstance(details, dict) else {}
    raw = str(details.get("error") or "").strip()
    match = _TYPE_RE.match(raw)
    error_type = match.group(1) if match else "UnknownError"
    # Avoid reflecting arbitrary raw legacy text, bearer tokens, URLs,
    # phone numbers, private identifiers or exception messages.
    if error_type not in _KINDS:
        reason = "An unexpected synchronization error occurred. Check protected server logs for details."
    else:
        reason = _KINDS[error_type]
    return {"error": error_type, "reason": reason}

def safe_sync_error_from_exception(exc):
    """Classify the exception without serializing str(exc) to the audit log."""
    result = safe_sync_error_details({"error": type(exc).__name__})
    # Only the numeric HTTP status is safe to surface; never a response body.
    status = getattr(exc, "code", None)
    if not isinstance(status, bool) and isinstance(status, int) and 400 <= status <= 599:
        result["http_status"] = status
        if status == 429:
            result["reason"] = "Hollihop API rate limit reached (HTTP 429). Retry with backoff."
        elif status in (401, 403):
            result["reason"] = "Hollihop API rejected authentication/permissions (HTTP %s)." % status
        elif status >= 500:
            result["reason"] = "Hollihop API server is temporarily unavailable (HTTP %s)." % status
        else:
            result["reason"] = "Hollihop API returned HTTP %s." % status
    return result
