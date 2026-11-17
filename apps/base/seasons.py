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


# V85: greetings for every holiday theme, in the three site languages.
HOLIDAY_GREETINGS = {
    "new-year": {"uz": "Yangi yil muborak!", "ru": "С Новым годом!", "en": "Happy New Year!"},
    "navruz": {"uz": "Navro'z muborak!", "ru": "С праздником Навруз!", "en": "Happy Navruz!"},
    "ramazon-hayit": {"uz": "Ramazon hayiti muborak!", "ru": "С праздником Рамазан Хайит!", "en": "Eid Mubarak!"},
    "qurbon-hayit": {"uz": "Qurbon hayiti muborak!", "ru": "С праздником Курбан Хайит!", "en": "Eid al-Adha Mubarak!"},
    "womens-day": {"uz": "8-mart bayramingiz muborak!", "ru": "С 8 Марта!", "en": "Happy Women's Day!"},
    "independence": {"uz": "Mustaqillik kuni muborak!", "ru": "С Днём независимости!", "en": "Happy Independence Day!"},
    "teachers-day": {"uz": "O'qituvchilar kuni muborak!", "ru": "С Днём учителя!", "en": "Happy Teachers' Day!"},
    "constitution": {"uz": "Konstitutsiya kuni muborak!", "ru": "С Днём Конституции!", "en": "Happy Constitution Day!"},
}
HOLIDAY_CACHE_SECONDS = 600
HOLIDAY_GENERATION_KEY = "makon:holiday:v85:generation"


def clear_holiday_cache():
    """Called when a manager edits the holiday calendar: every cached day is dropped."""
    try:
        cache.incr(HOLIDAY_GENERATION_KEY)
    except ValueError:
        cache.set(HOLIDAY_GENERATION_KEY, 1, None)


def _holiday(key):
    greetings = HOLIDAY_GREETINGS.get(key, {})
    return {"key": key, "label": greetings.get("uz", ""), "greetings": greetings}


def _holiday_from_calendar(day: date):
    """The admin-managed calendar (base.HolidayTheme). None = no row covers the day;
    raises LookupError when the calendar is empty, so the built-in list is used."""
    generation = cache.get(HOLIDAY_GENERATION_KEY, 0)
    cache_key = f"makon:holiday:v85:{generation}:{day.isoformat()}"
    cached = cache.get(cache_key)
    if cached is None:
        from apps.base.models import HolidayTheme

        if not HolidayTheme.objects.exists():
            raise LookupError("empty holiday calendar")
        rows = list(HolidayTheme.objects.filter(is_active=True, start_date__lte=day, end_date__gte=day))
        rows.sort(key=lambda row: (row.end_date - row.start_date, row.pk))  # the most specific wins
        cached = rows[0].key if rows else ""
        cache.set(cache_key, cached, HOLIDAY_CACHE_SECONDS)
    return _holiday(cached) if cached else None


def holiday_for_date(day: date):
    try:
        return _holiday_from_calendar(day)
    except Exception:  # noqa: BLE001 - empty table, not migrated yet, DB hiccup: fall back
        pass
    md = (day.month, day.day)
    for holiday in HOLIDAYS:
        if holiday["start"] <= md <= holiday["end"]:
            return _holiday(holiday["key"])
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
