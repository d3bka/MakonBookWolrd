"""V97: build a test import from a JSON file (Admin → Tests → Import from JSON).

Used for tests that do not come as MakonBook Structured PDFs, such as the English
Placement & Diagnostic Test with written answers, tiers and skills. The file
becomes a staging import, exactly like an uploaded Structured PDF: the AI solves
every question and compares its answers with the key, a person approves it, and
a manager publishes it (as Placement when test_type is "placement").

Format (text uses the MakonBook format: blank line = paragraph, pipe tables):

{
  "name": "English Placement Diagnostic",
  "test_type": "placement",                  # regular | placement | event
  "english": [
    {"module": 1, "number": 1, "passage": "...", "question": "...",
     "response_type": "ai_written",           # multiple_choice | open_text | ai_written
     "answer": "model answer or A-D", "accepted_answers": ["..."],
     "grading_criteria": "...", "choices": {"A": "...", "B": "...", "C": "...", "D": "..."},
     "tier": "foundation", "domain": "Standard English Conventions", "skill": "Past perfect", "explanation": "..."}
  ],
  "math": [{"module": 1, "number": 1, "question": "...", "choices": {...}, "answer": "B", "written": false,
            "domain": "Algebra", "skill": "Linear functions"}]

"domain" is one of the official SAT domains (apps.sat.sat_taxonomy). When it is
missing, the AI suggests one during the answer check.
}
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .models import Test, TestImportJob, TestImportQuestion
from .sat_taxonomy import canonical_domain, canonical_skill

MAX_QUESTIONS = 200
RESPONSE_TYPES = {"multiple_choice", "open_text", "ai_written"}
TIERS = {"", "foundation", "pre_sat", "sat"}
TEST_TYPES = {"regular", "placement", "event"}


class JsonImportError(ValueError):
    pass


def _text(row, key, limit=20000):
    value = row.get(key)
    if value is None:
        return ""
    if not isinstance(value, (str, int, float)):
        raise JsonImportError(f"'{key}' must be text.")
    return str(value).strip()[:limit]


def _module(row, where):
    value = row.get("module", 1)
    if value in (1, "1", "module_1", "m1"):
        return "module_1"
    if value in (2, "2", "module_2", "m2"):
        return "module_2"
    raise JsonImportError(f"{where}: module must be 1 or 2.")


def _choices(row):
    choices = row.get("choices") or {}
    if not isinstance(choices, dict):
        raise JsonImportError("'choices' must be an object like {\"A\": \"...\"}.")
    return {letter: str(choices.get(letter.upper()) or choices.get(letter) or "").strip() for letter in "abcd"}


def _category(row, section, where):
    declared = _text(row, "domain", 100)
    domain = canonical_domain(declared, section)
    if declared and not domain:
        raise JsonImportError(f"{where}: unknown domain '{declared}'. Use one of the official SAT domains.")
    return domain, canonical_skill(domain, _text(row, "skill", 120))[:120]


def _number(row, index, where):
    number = row.get("number", index + 1)
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        raise JsonImportError(f"{where}: number must be a positive whole number.")
    return number


def _english(job, row, index):
    where = f"English question {index + 1}"
    if not isinstance(row, dict):
        raise JsonImportError(f"{where} must be an object.")
    response_type = _text(row, "response_type") or "multiple_choice"
    if response_type not in RESPONSE_TYPES:
        raise JsonImportError(f"{where}: response_type must be one of {', '.join(sorted(RESPONSE_TYPES))}.")
    tier = _text(row, "tier")
    if tier not in TIERS:
        raise JsonImportError(f"{where}: tier must be foundation, pre_sat or sat.")
    answer = _text(row, "answer", 400)
    choices = _choices(row)
    if response_type == "multiple_choice":
        answer = answer.upper()
        if answer not in {"A", "B", "C", "D"}:
            raise JsonImportError(f"{where}: a multiple-choice answer must be A, B, C or D.")
        if not all(choices.values()):
            raise JsonImportError(f"{where}: multiple-choice questions need choices A, B, C and D.")
    elif not answer:
        raise JsonImportError(f"{where}: written answers need a model answer.")
    domain, skill = _category(row, "english", where)
    accepted = row.get("accepted_answers") or []
    if isinstance(accepted, str):
        accepted = [accepted]
    if not isinstance(accepted, list):
        raise JsonImportError(f"{where}: accepted_answers must be a list.")
    return TestImportQuestion(
        job=job, section="english", module=_module(row, where), number=_number(row, index, where),
        passage=_text(row, "passage"), question=_text(row, "question"),
        a=choices["a"], b=choices["b"], c=choices["c"], d=choices["d"],
        response_type=response_type, answer=answer,
        accepted_answers="\n".join(str(item).strip() for item in accepted if str(item).strip()),
        grading_criteria=_text(row, "grading_criteria", 2000),
        explanation=_text(row, "explanation"),
        placement_tier=tier, skill=skill, domain_name=domain,
        content_format="makon", ai_confidence=1.0, raw_payload={"format": "makonbook_json"},
    )


def _math(job, row, index):
    where = f"Math question {index + 1}"
    if not isinstance(row, dict):
        raise JsonImportError(f"{where} must be an object.")
    written = bool(row.get("written"))
    answer = _text(row, "answer", 400)
    choices = _choices(row)
    if not written:
        answer = answer.upper()
        if answer not in {"A", "B", "C", "D"} or not all(choices.values()):
            raise JsonImportError(f"{where}: multiple-choice questions need choices A-D and an answer A-D.")
    elif not answer:
        raise JsonImportError(f"{where}: written questions need an answer.")
    domain, skill = _category(row, "math", where)
    return TestImportQuestion(
        job=job, section="math", module=_module(row, where), number=_number(row, index, where),
        passage=_text(row, "passage"), question=_text(row, "question"),
        a=choices["a"], b=choices["b"], c=choices["c"], d=choices["d"],
        response_type="open_text" if written else "multiple_choice",
        written=written, answer=answer, explanation=_text(row, "explanation"),
        domain_name=domain, skill=skill, content_format="makon", ai_confidence=1.0, raw_payload={"format": "makonbook_json"},
    )


MAX_FILE_BYTES = 2 * 1024 * 1024


def import_uploaded_json(upload, *, created_by=None):
    """Read an uploaded file and build the staging import. Raises JsonImportError."""
    import json

    if not upload:
        raise JsonImportError("Choose a JSON file to import.")
    if upload.size > MAX_FILE_BYTES:
        raise JsonImportError("The JSON file must be smaller than 2 MB.")
    try:
        data = json.loads(upload.read().decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise JsonImportError("The file is not valid JSON.") from exc
    return import_test_json(data, created_by=created_by)


def import_test_json(data, *, created_by=None):
    """Validate everything first, then create the staging import in one transaction."""
    from .test_import_service import assign_reviewers, validate_job

    if not isinstance(data, dict):
        raise JsonImportError("The file must contain one JSON object.")
    name = _text(data, "name", 400)
    if not name:
        raise JsonImportError("'name' is required.")
    if Test.objects.filter(name__iexact=name).exists():
        raise JsonImportError(f"A test named '{name}' already exists.")
    test_type = _text(data, "test_type") or "regular"
    if test_type not in TEST_TYPES:
        raise JsonImportError("test_type must be regular, placement or event.")
    english = data.get("english") or []
    math = data.get("math") or []
    if not isinstance(english, list) or not isinstance(math, list):
        raise JsonImportError("'english' and 'math' must be lists of questions.")
    if not english and not math:
        raise JsonImportError("Add at least one question.")
    if len(english) + len(math) > MAX_QUESTIONS:
        raise JsonImportError(f"At most {MAX_QUESTIONS} questions per file.")

    with transaction.atomic():
        job = TestImportJob(
            name=name, created_by=created_by, target_test_type=test_type,
            status=TestImportJob.STATUS_REVIEW_REQUIRED, ai_model="makonbook_json",
            processed_at=timezone.now(), progress_percent=100, progress_stage="complete",
            progress_message="JSON import ready for review.",
        )
        if english and math:
            job.detected_test_type = TestImportJob.TYPE_FULL
        else:
            job.detected_test_type = TestImportJob.TYPE_ENGLISH if english else TestImportJob.TYPE_MATH
        job.structure_data = {"format": "makonbook_json", "test_type": test_type}
        job.save()
        rows = [_english(job, row, i) for i, row in enumerate(english)]
        rows += [_math(job, row, i) for i, row in enumerate(math)]
        seen = set()
        for question in rows:
            key = (question.section, question.module, question.number)
            if key in seen:
                label = "English" if question.section == "english" else "Math"
                raise JsonImportError(f"{label}: question {question.number} appears twice in the same module.")
            seen.add(key)
        TestImportQuestion.objects.bulk_create(rows)
        validate_job(job)
        assign_reviewers(job)
        job.refresh_review_status()
    return job
