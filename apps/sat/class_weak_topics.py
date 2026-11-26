"""V114: weak topics of a class — where the class makes the most mistakes, by official SAT
domain and skill (V98 tagging), the questions most of the class got wrong, and a plan for
the next lesson built from them.

* Practice tests only (the same attempts the Mistakes page uses): no mock events,
  placement or makeup tests.
* Each student's latest scored attempt of each test counts once, so retakes do not
  inflate a topic.
* A skipped question counts as a mistake, like on the Mistakes page.
* Only students currently in the class; any practice test they took counts, not only
  tests opened from this class.
"""
from collections import Counter, defaultdict
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Count, Max
from django.utils import timezone

from .mistakes import MODULE_NAMES, _module_answers, answer_is_correct, correct_answer_text, question_model
from .models import ClassroomMembership, Test, TestModule, TestReview

PERIODS = {"30": 30, "90": 90, "all": None}
DEFAULT_PERIOD = "90"
SECTIONS = {"english": "Reading and Writing", "math": "Math"}

MIN_ANSWERS = 8        # a skill needs this many answers before it is ranked
MIN_STUDENTS = 2       # ...from at least this many students
QUESTION_MIN_STUDENTS = 3
TOP_QUESTIONS = 5
PLAN_SKILLS = 3
STRUGGLING_RATE = 0.5  # a student "struggles" with a skill at 50% wrong or more...
STRUGGLING_MIN = 3     # ...over at least 3 answers
CACHE_SECONDS = 15 * 60


def class_students(classroom):
    return list(
        ClassroomMembership.objects.filter(
            classroom=classroom, role="student", status="approved", user__is_active=True,
        ).select_related("user").order_by("user__first_name", "user__last_name", "user__username")
    )


def _reviews(student_ids, since):
    qs = (
        TestReview.objects.filter(
            user_id__in=student_ids, score__isnull=False, test__isnull=False, test__test_type=Test.TYPE_REGULAR,
        )
        .exclude(test_type__in=["makeup", "event", "placement"])
    )
    if since is not None:
        qs = qs.filter(created_at__gte=since)
    latest = {}
    for review in qs.only("pk", "user_id", "test_id", "attempt_id", "created_at").order_by("created_at", "pk"):
        latest[(review.user_id, review.test_id)] = review  # later attempts replace earlier ones
    return list(latest.values())


def _empty_bucket(section, domain, skill):
    return {
        "section": section, "section_label": SECTIONS.get(section, section), "domain": domain, "skill": skill,
        "answered": 0, "wrong": 0, "students": defaultdict(lambda: [0, 0]),  # user_id -> [answered, wrong]
    }


def _compute(classroom, period):
    days = PERIODS.get(period, PERIODS[DEFAULT_PERIOD])
    since = timezone.now() - timedelta(days=days) if days else None
    memberships = class_students(classroom)
    names = {m.user_id: (m.user.get_full_name() or m.user.username) for m in memberships}
    reviews = _reviews(list(names), since)

    wanted = {(r.user_id, r.test_id, str(r.attempt_id)) for r in reviews}
    test_ids = {r.test_id for r in reviews}
    modules = [
        row for row in TestModule.objects.filter(user_id__in=list(names), test_id__in=test_ids).only(
            "pk", "user_id", "test_id", "attempt_id", "section", "module", "answers",
        )
        if (row.user_id, row.test_id, str(row.attempt_id)) in wanted
    ]

    questions = {}  # (section, test_id, module) -> [question]
    for section in SECTIONS:
        model = question_model(section)
        for question in model.objects.filter(test_id__in=test_ids).select_related("type", "type__domain", "domain").order_by("number", "pk"):
            if getattr(question, "response_type", "") == "ai_written":
                continue  # graded later by AI; not a clean right/wrong here
            questions.setdefault((section, question.test_id, question.module), []).append(question)

    skills = {}
    per_question = {}
    untagged = 0
    students_with_answers = set()
    counted_modules = set()
    for row in modules:
        section = str(row.section or "").lower()
        module_name = MODULE_NAMES.get(str(row.module or "").lower())
        key = (row.user_id, row.test_id, str(row.attempt_id), section, module_name)
        if section not in SECTIONS or module_name is None or key in counted_modules:
            continue
        counted_modules.add(key)
        answers = _module_answers(row)
        for question in questions.get((section, row.test_id, module_name), []):
            response = answers.get(str(question.pk))
            correct = answer_is_correct(section, question, response)
            students_with_answers.add(row.user_id)

            stat = per_question.setdefault((section, question.pk), {
                "section": section, "question_id": question.pk, "answered": 0, "wrong": 0,
                "wrong_answers": Counter(), "students_wrong": [],
            })
            stat["answered"] += 1
            if not correct:
                stat["wrong"] += 1
                stat["wrong_answers"][str(response).strip()[:40] if response not in (None, "") else ""] += 1
                stat["students_wrong"].append(row.user_id)

            type_obj, domain_obj = question.type, question.domain
            if type_obj is None and domain_obj is None:
                untagged += 1
                continue
            domain = domain_obj.name if domain_obj else (type_obj.domain.name if type_obj and type_obj.domain_id else "")
            skill = type_obj.name if type_obj else domain
            bucket = skills.setdefault((section, skill), _empty_bucket(section, domain, skill))
            bucket["answered"] += 1
            bucket["students"][row.user_id][0] += 1
            if not correct:
                bucket["wrong"] += 1
                bucket["students"][row.user_id][1] += 1

    ranked, too_few = [], []
    domains = {}
    for bucket in skills.values():
        rate = bucket["wrong"] / bucket["answered"] if bucket["answered"] else 0
        struggling = sorted(
            (names[uid] for uid, (answered, wrong) in bucket["students"].items()
             if answered >= STRUGGLING_MIN and wrong / answered >= STRUGGLING_RATE and uid in names),
            key=str.casefold,
        )
        item = {
            "section": bucket["section"], "section_label": bucket["section_label"], "domain": bucket["domain"],
            "skill": bucket["skill"], "answered": bucket["answered"], "wrong": bucket["wrong"],
            "rate": round(rate * 100), "students": len(bucket["students"]), "struggling": struggling,
        }
        domain = domains.setdefault((bucket["section"], bucket["domain"]), {
            "section": bucket["section"], "section_label": bucket["section_label"], "domain": bucket["domain"],
            "answered": 0, "wrong": 0,
        })
        domain["answered"] += bucket["answered"]
        domain["wrong"] += bucket["wrong"]
        if bucket["answered"] >= MIN_ANSWERS and item["students"] >= MIN_STUDENTS:
            ranked.append(item)
        else:
            too_few.append(item)
    ranked.sort(key=lambda i: (-i["rate"], -i["wrong"], i["skill"].casefold()))
    too_few.sort(key=lambda i: (-i["answered"], i["skill"].casefold()))
    for domain in domains.values():
        domain["rate"] = round(domain["wrong"] * 100 / domain["answered"]) if domain["answered"] else 0
    domain_list = sorted(domains.values(), key=lambda d: (d["section"], -d["rate"], d["domain"].casefold()))

    top = [
        stat for stat in per_question.values()
        if stat["wrong"] and stat["answered"] >= QUESTION_MIN_STUDENTS
    ]
    top.sort(key=lambda s: (-s["wrong"] / s["answered"], -s["wrong"], s["question_id"]))
    top_questions = []
    for stat in top[:TOP_QUESTIONS]:
        common = [(answer, n) for answer, n in stat["wrong_answers"].most_common(3)]
        top_questions.append({
            "section": stat["section"], "question_id": stat["question_id"], "answered": stat["answered"],
            "wrong": stat["wrong"], "rate": round(stat["wrong"] * 100 / stat["answered"]),
            "common_wrong": common,
            "students_wrong": sorted({names[uid] for uid in stat["students_wrong"] if uid in names}, key=str.casefold),
        })

    total_answered = sum(s["answered"] for s in per_question.values())
    total_wrong = sum(s["wrong"] for s in per_question.values())
    return {
        "period": period if period in PERIODS else DEFAULT_PERIOD,
        "students_total": len(names),
        "students_with_answers": len(students_with_answers & set(names)),
        "attempts": len(reviews),
        "answered": total_answered,
        "wrong": total_wrong,
        "rate": round(total_wrong * 100 / total_answered) if total_answered else 0,
        "untagged": untagged,
        "skills": ranked,
        "skills_few_answers": too_few,
        "domains": domain_list,
        "top_questions": top_questions,
    }


def _cache_key(classroom, period):
    members = ClassroomMembership.objects.filter(classroom=classroom, role="student", status="approved")
    member_ids = list(members.values_list("user_id", flat=True))
    stamp = TestReview.objects.filter(user_id__in=member_ids, score__isnull=False).aggregate(
        last=Max("pk"), n=Count("pk"),
    )
    return f"sat:weak-topics:v1:{classroom.pk}:{period}:{len(member_ids)}:{hash(tuple(sorted(member_ids)))}:{stamp['last']}:{stamp['n']}"


def _attach_questions(top_questions):
    by_section = defaultdict(list)
    for item in top_questions:
        by_section[item["section"]].append(item["question_id"])
    found = {}
    for section, ids in by_section.items():
        for question in question_model(section).objects.filter(pk__in=ids).select_related("test", "type", "domain"):
            found[(section, question.pk)] = question
    kept = []
    for item in top_questions:
        question = found.get((item["section"], item["question_id"]))
        if question is None:
            continue
        item = dict(item, question=question, section_label=SECTIONS[item["section"]],
                    correct_answer=correct_answer_text(item["section"], question))
        kept.append(item)
    return kept


def lesson_plan(result):
    """A short plan for the next lesson: the weakest skills, the questions to go through, who needs help."""
    steps = []
    for item in result["skills"][:PLAN_SKILLS]:
        questions = [q for q in result["top_questions"]
                     if q["section"] == item["section"]
                     and getattr(q["question"].type, "name", None) == item["skill"]]
        steps.append({"skill": item, "questions": questions})
    planned = {q["question_id"] for step in steps for q in step["questions"]}
    extra = [q for q in result["top_questions"] if q["question_id"] not in planned]
    return {"steps": steps, "extra_questions": extra}


def plan_text(classroom, result, plan):
    lines = [f"Lesson plan — {classroom.name}", ""]
    for n, step in enumerate(plan["steps"], 1):
        skill = step["skill"]
        lines.append(f"{n}. Re-teach: {skill['skill']} ({skill['section_label']}, {skill['domain']}) — "
                     f"{skill['rate']}% wrong, {skill['wrong']} of {skill['answered']} answers")
        for q in step["questions"]:
            lines.append(f"   • Go through {q['question'].test.name if q['question'].test else 'test'} Q{q['question'].number} "
                         f"({q['rate']}% of the class got it wrong)")
        if skill["struggling"]:
            lines.append(f"   • Check on: {', '.join(skill['struggling'])}")
    if plan["extra_questions"]:
        lines.append("")
        lines.append("Also go through:")
        for q in plan["extra_questions"]:
            skill = getattr(q["question"].type, "name", "") or q["section_label"]
            lines.append(f"   • {q['question'].test.name if q['question'].test else 'test'} Q{q['question'].number} — {skill} "
                         f"({q['rate']}% wrong)")
    return "\n".join(lines).strip()


def class_weak_topics(classroom, period=DEFAULT_PERIOD, *, use_cache=True):
    period = period if period in PERIODS else DEFAULT_PERIOD
    key = _cache_key(classroom, period)
    result = cache.get(key) if use_cache else None
    if result is None:
        result = _compute(classroom, period)
        cache.set(key, result, CACHE_SECONDS)
    result = dict(result, top_questions=_attach_questions(result["top_questions"]))
    plan = lesson_plan(result)
    result["plan"] = plan
    result["plan_text"] = plan_text(classroom, result, plan)
    return result
