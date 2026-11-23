"""V97: tier-based placement (English Placement & Diagnostic Test).

Every question of a diagnostic placement test carries a tier (Foundation, Pre-SAT,
SAT) and a skill. The recommended course follows the test's rubric:

* SAT Course       total >= 80%, Pre-SAT tier >= 75%, SAT tier >= 70%
* Pre-SAT Course   total >= 40%, Foundation tier >= 60%, Pre-SAT tier >= 58%
* Foundation       everything else

For the 30-question test that is exactly 24/30 with 9/12 and 5/7, and 12/30 with
7/11 and 7/12. Percent thresholds keep the rule right for tests of other lengths.
A student is placed in the highest course whose checkpoints they all clear, so a
high total with a weak lower tier does not jump a level.

Borderline rule (the rubric's note for totals near a cut-off): a student close to
the SAT cut-off (from 22/30, 73%) who scores about 60% on every tier (7/11, 7/12,
5/7) is placed in the SAT Course. It applies to every total from 22 up, so more
points never give a lower course. Near the Pre-SAT cut-off the note changes
nothing: the Pre-SAT checkpoints already are the 60% tiers.
"""
from __future__ import annotations

TIER_ORDER = ("foundation", "pre_sat", "sat")
TIER_LABELS = {"foundation": "Foundation", "pre_sat": "Pre-SAT", "sat": "SAT"}

COURSES = {
    "foundation": {
        "label": "Foundation Course",
        "summary": "Basic sentence structure, verb forms and literal reading are in place. "
                   "Written grammar accuracy still needs work before SAT-level material.",
    },
    "pre_sat": {
        "label": "Pre-SAT Course",
        "summary": "Solid foundational grammar and reliable control of core SAT grammar and analytical reading. "
                   "Rhetoric, transitions and inference are not yet consistent.",
    },
    "sat": {
        "label": "SAT Course (Advanced)",
        "summary": "Strong accuracy across conventions, transitions, synthesis, inference, data and vocabulary. "
                   "Ready for full SAT preparation.",
    },
}

# (course, rule, minimum total %, {tier: minimum %}), checked in order.
RULES = (
    ("sat", "main", 80, {"pre_sat": 75, "sat": 70}),
    ("sat", "borderline", 73, {"foundation": 60, "pre_sat": 58, "sat": 70}),
    ("pre_sat", "main", 40, {"foundation": 60, "pre_sat": 58}),
)


def is_tiered(questions):
    return any(getattr(q, "placement_tier", "") for q in questions)


def _meets(correct, total, percent):
    """correct/total >= percent%, in integers (no float rounding at the cut-offs)."""
    return total == 0 or correct * 100 >= percent * total


def placement_rule(total_correct, total, tiers):
    """(course, "main" | "borderline") for a result."""
    for course, rule, total_percent, tier_percents in RULES:
        if not _meets(total_correct, total, total_percent):
            continue
        if all(_meets(tiers.get(t, {}).get("correct", 0), tiers.get(t, {}).get("total", 0), p)
               for t, p in tier_percents.items()):
            return course, rule
    return "foundation", "main"


def recommend_course(total_correct, total, tiers):
    return placement_rule(total_correct, total, tiers)[0]


def diagnostic(rows):
    """rows: [(question, is_correct, answered)] for every question of the attempt.

    Returns the course, tier and skill breakdown shown on the result page.
    """
    tiers = {key: {"key": key, "label": TIER_LABELS[key], "correct": 0, "total": 0} for key in TIER_ORDER}
    skills = {}
    total = correct = answered_count = 0
    for question, is_correct, answered in rows:
        total += 1
        correct += 1 if is_correct else 0
        answered_count += 1 if answered else 0
        tier = getattr(question, "placement_tier", "") or ""
        if tier in tiers:
            tiers[tier]["total"] += 1
            tiers[tier]["correct"] += 1 if is_correct else 0
        name = (getattr(question, "skill", "") or "").strip() or "Other"
        skill = skills.setdefault(name, {"skill": name, "tier": TIER_LABELS.get(tier, ""), "correct": 0, "total": 0, "numbers": []})
        skill["total"] += 1
        skill["correct"] += 1 if is_correct else 0
        skill["numbers"].append({"number": question.number, "correct": bool(is_correct), "answered": bool(answered)})

    course, rule = placement_rule(correct, total, tiers)
    tier_rows = []
    for key in TIER_ORDER:
        row = tiers[key]
        if not row["total"]:
            continue
        row["percent"] = round(row["correct"] * 100 / row["total"])
        tier_rows.append(row)
    skill_rows = sorted(skills.values(), key=lambda s: s["numbers"][0]["number"] or 0)
    for row in skill_rows:
        row["percent"] = round(row["correct"] * 100 / row["total"]) if row["total"] else 0
    return {
        "course_key": course,
        "borderline": rule == "borderline",
        "course": COURSES[course]["label"],
        "summary": COURSES[course]["summary"],
        "correct": correct,
        "total": total,
        "answered": answered_count,
        "percent": round(correct * 100 / total) if total else 0,
        "tiers": tier_rows,
        "skills": skill_rows,
    }
