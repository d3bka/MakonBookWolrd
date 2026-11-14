"""V50.6 MakonRoom: a cosmetic study room that grows with learning progress.

Every item is purely cosmetic and unlocks from progress the student already
has (XP, level, streak, mastered words, completed quests) — nothing here can
touch SAT/AP scoring. Achievements become trophies on the shelf. The layout a
student chooses is stored in ``RoomLayout``; the server only accepts items the
student has actually unlocked.
"""
from dataclasses import dataclass

from .models import RoomLayout, UserAchievement
from .services import ACHIEVEMENTS, _achievement_state, ensure_gamification_profile, evaluate_achievements

SLOTS = (
    ("wallpaper", "Wallpaper", "bi-palette"),
    ("art", "Wall art", "bi-image"),
    ("rug", "Rug", "bi-grid-3x3"),
    ("desk", "Furniture", "bi-lamp"),
    ("corner", "Light", "bi-lightbulb"),
    ("plant", "Plant", "bi-flower2"),
)
SLOT_KEYS = tuple(key for key, _, _ in SLOTS)
# The part of the 960x600 room scene that each slot's thumbnails show.
THUMB_VIEWBOX = {
    "wallpaper": "0 0 300 200",
    "art": "368 62 224 196",
    "rug": "230 462 480 136",
    "desk": "592 300 352 226",
    "corner": "268 0 140 440",
    "plant": "34 252 160 230",
}

REQUIREMENT_LABELS = {
    "xp_total": "Earn {target:,} XP",
    "level": "Reach level {target}",
    "best_streak": "Keep a {target}-day streak",
    "mastered_words": "Master {target} words",
    "completed_quests": "Complete {target} quests",
}


@dataclass(frozen=True)
class RoomItem:
    code: str
    slot: str
    name: str
    blurb: str
    requirement: tuple = None  # (progress_key, target); None = available from day one

    @property
    def is_default(self):
        return self.requirement is None


ITEMS = (
    RoomItem("wp_lavender", "wallpaper", "Lavender wall", "Calm and quiet — a good start."),
    RoomItem("wp_ikat", "wallpaper", "Atlas ikat", "The flowing silk pattern of Margilan atlas.", ("level", 3)),
    RoomItem("wp_girih", "wallpaper", "Girih tiles", "Eight-point stars from Samarkand's madrasas.", ("best_streak", 7)),
    RoomItem("wp_night", "wallpaper", "Starry night", "For night-owl study sessions.", ("level", 8)),

    RoomItem("art_cork", "art", "Study board", "Notes, plans and a photo or two."),
    RoomItem("art_suzani", "art", "Suzani", "Hand-embroidered suns from Bukhara.", ("mastered_words", 10)),
    RoomItem("art_registan", "art", "Registan print", "Three madrasas under a blue sky.", ("level", 5)),
    RoomItem("art_map", "art", "World map", "Pick where you'll study next.", ("xp_total", 1000)),

    RoomItem("rug_mat", "rug", "Round mat", "Soft, simple, comfy."),
    RoomItem("rug_bukhara", "rug", "Bukhara gilam", "A deep red carpet with gul medallions.", ("best_streak", 3)),
    RoomItem("rug_atlas", "rug", "Atlas runner", "Ikat colours under your feet.", ("completed_quests", 5)),

    RoomItem("desk_study", "desk", "Study desk", "Laptop, books and a warm mug."),
    RoomItem("desk_tapchan", "desk", "Tapchan & choynak", "Tea, cushions and long conversations.", ("completed_quests", 15)),
    RoomItem("desk_scholar", "desk", "Scholar's desk", "Big desk, open book, serious plans.", ("level", 10)),

    RoomItem("corner_lamp", "corner", "Floor lamp", "Warm light for evening practice."),
    RoomItem("corner_chiroq", "corner", "Chiroq lantern", "Pierced metal and coloured glass.", ("completed_quests", 25)),
    RoomItem("corner_globe", "corner", "Globe", "The world is waiting.", ("mastered_words", 50)),

    RoomItem("plant_cactus", "plant", "Cactus", "Low maintenance, high spirit."),
    RoomItem("plant_tulips", "plant", "Tulips", "Lola — the first flowers of spring.", ("mastered_words", 25)),
    RoomItem("plant_anor", "plant", "Pomegranate tree", "Anor: a sign of plenty and patience.", ("level", 12)),
)
ITEMS_BY_CODE = {item.code: item for item in ITEMS}
DEFAULTS = {item.slot: item.code for item in ITEMS if item.is_default}

# Which trophy shape an achievement becomes on the shelf.
TROPHY_SHAPES = {
    "xp_total": "cup",
    "level": "cup",
    "best_streak": "medal",
    "mastered_words": "book",
    "completed_quests": "star",
}


def _requirement_label(item):
    key, target = item.requirement
    return REQUIREMENT_LABELS.get(key, "{target}").format(target=target)


def progress_state(user):
    profile = ensure_gamification_profile(user)
    return _achievement_state(user, profile)


def is_unlocked(item, state):
    if item.is_default:
        return True
    key, target = item.requirement
    return int(state.get(key, 0) or 0) >= target


def layout_for(user):
    layout, _ = RoomLayout.objects.get_or_create(user=user)
    return layout


def equipped(layout, state):
    """Slot -> item code, falling back to the default for anything invalid or no longer unlocked."""
    chosen = layout.slots if isinstance(layout.slots, dict) else {}
    result = {}
    for slot in SLOT_KEYS:
        item = ITEMS_BY_CODE.get(chosen.get(slot))
        result[slot] = item.code if item and item.slot == slot and is_unlocked(item, state) else DEFAULTS[slot]
    return result


def equip(user, slot, code):
    """Place an unlocked item. Raises ValueError (bad input) or PermissionError (locked)."""
    item = ITEMS_BY_CODE.get(code)
    if slot not in SLOT_KEYS or item is None or item.slot != slot:
        raise ValueError("Unknown room item.")
    state = progress_state(user)
    if not is_unlocked(item, state):
        raise PermissionError(_requirement_label(item))
    layout = layout_for(user)
    slots = dict(layout.slots or {})
    slots[slot] = code
    layout.slots = slots
    layout.save(update_fields=["slots", "updated_at"])
    return equipped(layout, state)


def room_context(user, *, mark_seen=True):
    state = progress_state(user)
    # Same as Home: catch achievements that became eligible through older data.
    evaluate_achievements(user)
    layout = layout_for(user)
    current = equipped(layout, state)
    seen = set(layout.seen or [])
    slots = []
    unlocked_codes = []
    for slot, label, icon in SLOTS:
        items = []
        for item in (i for i in ITEMS if i.slot == slot):
            unlocked = is_unlocked(item, state)
            row = {
                "code": item.code, "name": item.name, "blurb": item.blurb,
                "unlocked": unlocked, "equipped": current[slot] == item.code,
                "is_new": unlocked and not item.is_default and item.code not in seen,
            }
            if not item.is_default:
                key, target = item.requirement
                have = min(target, int(state.get(key, 0) or 0))
                row.update({"requirement": _requirement_label(item), "progress": have, "target": target,
                            "percent": round(have / target * 100)})
            if unlocked:
                unlocked_codes.append(item.code)
            items.append(row)
        slots.append({"key": slot, "label": label, "icon": icon, "items": items, "viewbox": THUMB_VIEWBOX[slot],
                      "unlocked": sum(1 for row in items if row["unlocked"])})

    earned = {row.code: row for row in UserAchievement.objects.filter(user=user)}
    per_row = 7
    trophies = [{
        "code": a["code"], "title": a["title"], "description": a["description"],
        "shape": TROPHY_SHAPES.get(a["progress_key"], "cup"),
        "earned": a["code"] in earned,
        "earned_at": getattr(earned.get(a["code"]), "unlocked_at", None),
        # position on the two shelves of the room scene
        "x": 668 + (index % per_row) * 38, "y": 168 + (index // per_row) * 100,
    } for index, a in enumerate(ACHIEVEMENTS)]

    new_items = [row for slot in slots for row in slot["items"] if row["is_new"]]
    if mark_seen and new_items:
        layout.seen = sorted(seen | set(unlocked_codes))
        layout.save(update_fields=["seen", "updated_at"])

    return {
        "room_slots": slots,
        "room_slot_map": {slot["key"]: slot for slot in slots},
        "room_equipped": current,
        "room_trophies": trophies,
        "room_trophies_earned": sum(1 for t in trophies if t["earned"]),
        "room_items_unlocked": len(unlocked_codes),
        "room_items_total": len(ITEMS),
        "room_new_items": new_items,
        "room_level": state.get("level", 1),
    }
