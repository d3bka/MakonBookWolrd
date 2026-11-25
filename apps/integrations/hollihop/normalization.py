from __future__ import annotations

import re


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value: str | None) -> str:
    return (value or "").strip().lower()


def email_is_valid(value: str | None) -> bool:
    email = normalize_email(value)
    return bool(email and _EMAIL_RE.match(email))


def normalize_phone(value: str | None) -> str:
    """Normalize to a conservative E.164-like representation.

    Uzbek 9-digit local numbers are converted to +998XXXXXXXXX. Existing
    international numbers keep their country code. Invalid/too-short values
    become an empty string rather than being guessed.
    """
    raw = (value or "").strip()
    if not raw:
        return ""
    had_plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("00"):
        digits = digits[2:]
        had_plus = True
    if len(digits) == 9:
        digits = "998" + digits
        had_plus = True
    elif len(digits) == 10 and digits[0] in "80" and not had_plus:
        # V111: old domestic forms "8 90 123 45 67" / "0 90 123 45 67" are Uzbek mobiles.
        digits = "998" + digits[1:]
        had_plus = True
    elif len(digits) == 10 and digits[0] == "8" and had_plus:
        # Stored by earlier versions as "+8XXXXXXXXX" from "8 9X XXX XX XX".
        digits = "998" + digits[1:]
    elif digits.startswith("998") and len(digits) == 12:
        had_plus = True
    elif len(digits) >= 10:
        had_plus = True
    if not had_plus or not 8 <= len(digits) <= 15:
        return ""
    return "+" + digits


def phone_is_valid(value: str | None) -> bool:
    return bool(normalize_phone(value))


def safe_text(value, max_length: int = 500) -> str:
    text = str(value or "").strip()
    return text[:max_length]
