"""V70 seasonal themes: which season the platform wears today.

The season is platform-wide. By default it follows the calendar in Tashkent
(Dec-Feb winter, Mar-May spring, Jun-Aug summer, Sep-Nov autumn); an Admin or
Manager can pin one season instead. Holidays are short windows inside a
season that the mascot and decor can celebrate.
"""
from dataclasses import dataclass
from datetime import date

from django.core.cache import cache
from django.utils import timezone

CACHE_KEY = "makon:seasonal-theme:v70"
CACHE_SECONDS = 300

SEASON_KEYS = ("winter", "spring", "summer", "autumn")

SEASONS = {
    "winter": {
        "key": "winter",
        "label": "Winter",
        "uz": "Qish",
        "months": "December – February",
        "motif": "Snow over blue domes, a warm tandir and fresh non",
        "particles": "snowflakes",
    },
    "spring": {
        "key": "spring",
        "label": "Spring",
        "uz": "Bahor",
        "months": "March – May",
        "motif": "Navro'z: sumalak in the kazan, peach blossom and tulips",
        "particles": "peach petals",
    },
    "summer": {
        "key": "summer",
        "label": "Summer",
        "uz": "Yoz",
        "months": "June – August",
        "motif": "Turquoise tiles, melons and a paxta-pattern choynak",
        "particles": "pollen and fireflies",
    },
    "autumn": {
        "key": "autumn",
        "label": "Autumn",
        "uz": "Kuz",
        "months": "September – November",
        "motif": "Golden chinar leaves, pomegranates and cotton",
        "particles": "chinar leaves",
    },
}

# (month, day) windows, inclusive. Year-crossing windows are split in two.
HOLIDAYS = (
    {"key": "new-year", "label": "Yangi yil muborak!", "start": (12, 25), "end": (12, 31)},
    {"key": "new-year", "label": "Yangi yil muborak!", "start": (1, 1), "end": (1, 3)},
    {"key": "navruz", "label": "Navro'z muborak!", "start": (3, 14), "end": (3, 28)},
    {"key": "independence", "label": "Mustaqillik kuni muborak!", "start": (8, 30), "end": (9, 2)},
    {"key": "teachers-day", "label": "O'qituvchilar kuni muborak!", "start": (10, 1), "end": (10, 1)},
)


def season_for_date(day: date) -> str:
    month = day.month
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


def holiday_for_date(day: date):
    md = (day.month, day.day)
    for holiday in HOLIDAYS:
        if holiday["start"] <= md <= holiday["end"]:
            return {"key": holiday["key"], "label": holiday["label"]}
    return None


@dataclass(frozen=True)
class SeasonState:
    key: str
    mode: str
    holiday: dict = None

    @property
    def is_auto(self):
        return self.mode == "auto"

    @property
    def meta(self):
        return SEASONS[self.key]


def _stored_mode() -> str:
    mode = cache.get(CACHE_KEY)
    if mode is None:
        from apps.base.models import SeasonalTheme

        row = SeasonalTheme.objects.filter(pk=1).only("mode").first()
        mode = row.mode if row else SeasonalTheme.MODE_AUTO
        cache.set(CACHE_KEY, mode, CACHE_SECONDS)
    return mode


def current_season(today: date = None) -> SeasonState:
    today = today or timezone.localdate()
    try:
        mode = _stored_mode()
    except Exception:  # noqa: BLE001 - decor must never break a page (e.g. table not migrated yet)
        mode = "auto"
    key = mode if mode in SEASON_KEYS else season_for_date(today)
    return SeasonState(key=key, mode=mode if mode in SEASON_KEYS else "auto", holiday=holiday_for_date(today))


def set_season_mode(mode: str, user=None):
    from apps.base.models import SeasonalTheme

    if mode != SeasonalTheme.MODE_AUTO and mode not in SEASON_KEYS:
        raise ValueError(f"Unknown season mode: {mode}")
    row, _ = SeasonalTheme.objects.get_or_create(pk=1)
    row.mode = mode
    row.updated_by = user if getattr(user, "is_authenticated", False) else None
    row.save()
    cache.delete(CACHE_KEY)
    return row


def can_change_season(user) -> bool:
    """Only Admins (superuser/staff/Admin group) and Managers may switch themes."""
    from apps.sat.roles import is_manager, is_platform_admin

    return is_platform_admin(user) or is_manager(user)
