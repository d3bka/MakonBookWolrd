"""V83: scoring for the ONLINE SATMakon placement test.

Online and offline SATMakon use different placement tests:
* "Placement Test Offline" (placement_offline_grading.py) keeps the Level 1-5 scale.
* Every other placement test whose name starts with "Placement Test" is the online one.
  It is scored with SATMakon's official tables ("Answers Placement Test" PDF):
  27 Reading & Writing questions and 38 Math questions. The tables top out at 700 and
  750, so each subject's table score is stretched to the SAT 200-800 range (rounded to
  10): a perfect subject is 800. Only the two subject scores are shown, no level names.
"""
from django.conf import settings

# Correct answers -> section score, exactly as in the official SATMakon answer file.
EBRW_SCORES = {
    27: 700, 26: 690, 25: 680, 24: 670, 23: 660, 22: 640, 21: 630, 20: 620, 19: 610, 18: 600,
    17: 590, 16: 580, 15: 570, 14: 560, 13: 540, 12: 530, 11: 520, 10: 500, 9: 470, 8: 440,
    7: 410, 6: 380, 5: 350, 4: 320, 3: 290, 2: 260, 1: 230, 0: 200,
}
MATH_SCORES = {
    38: 750, 37: 740, 36: 730, 35: 710, 34: 700, 33: 690, 32: 680, 31: 660, 30: 650, 29: 640,
    28: 630, 27: 610, 26: 600, 25: 590, 24: 580, 23: 580, 22: 570, 21: 560, 20: 550, 19: 540,
    18: 539,  # as printed in the official table
    17: 520, 16: 520, 15: 510, 14: 500, 13: 490, 12: 460, 11: 440, 10: 410, 9: 390, 8: 370,
    7: 350, 6: 330, 5: 310, 4: 290, 3: 260, 2: 240, 1: 220, 0: 200,
}
TABLES = {"english": EBRW_SCORES, "math": MATH_SCORES}
LABELS = {"english": "Reading and Writing", "math": "Math"}
SHORT = {"english": "EBRW", "math": "Math"}
SCALE_MIN, SCALE_MAX = 200, 800


def to_sat_scale(table_score, table_top):
    """Stretch a table score (200..table_top) to 200..800, rounded to 10."""
    ratio = (table_score - SCALE_MIN) / max(1, table_top - SCALE_MIN)
    scaled = SCALE_MIN + ratio * (SCALE_MAX - SCALE_MIN)
    return int(min(SCALE_MAX, max(SCALE_MIN, round(scaled / 10) * 10)))


def is_online_placement(event):
    """Placement events whose test is named "Placement Test ..." but not the offline one."""
    if getattr(event, "event_type", None) != "placement":
        return False
    name = str(getattr(getattr(event, "test", None), "name", "") or "").strip().casefold()
    offline_name = str(getattr(settings, "MAKONBOOK_OFFLINE_PLACEMENT_TEST_NAME", "Placement Test Offline")).casefold()
    return name.startswith("placement test") and "offline" not in name and name != offline_name


def section_result(section, raw, total_questions):
    """Score (200-800) for one subject. A test with a different question count than the
    official table is scaled to the table's length first."""
    table = TABLES[section]
    top = max(table)
    raw = max(0, int(raw or 0))
    total_questions = int(total_questions or 0)
    if total_questions and total_questions != top:
        raw = round(raw * top / total_questions)
    raw = min(raw, top)
    score = to_sat_scale(table[raw], table[top])
    return {
        "section": section, "label": LABELS[section], "short": SHORT[section],
        "correct": None, "total": total_questions or top,
        "score": score, "max_score": SCALE_MAX,
        "percent": round(100 * (score - SCALE_MIN) / (SCALE_MAX - SCALE_MIN)),
    }


def online_breakdown(sections, raw_by_section, totals):
    """sections: the subjects in this attempt ("english", "math").
    raw_by_section: correct answers per subject. totals: questions per subject."""
    results = []
    for section in ("english", "math"):
        if section not in sections:
            continue
        result = section_result(section, raw_by_section.get(section, 0), totals.get(section, 0))
        result["correct"] = int(raw_by_section.get(section, 0) or 0)
        results.append(result)
    label = " · ".join(f"{item['short']} {item['score']}" for item in results)
    return {
        "sections": results,
        "total_score": sum(item["score"] for item in results),
        "max_total": sum(item["max_score"] for item in results),
        "label": label,
    }
