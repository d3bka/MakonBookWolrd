"""V79: the student's "Mistakes" log, built from scored practice-test attempts.

* Only practice tests (regular tests): no mock events, placement tests or makeup tests.
* A wrong or skipped answer opens a mistake. One correct answer later (in a mistakes
  drill or a new attempt of a test with that question) marks it fixed.
* A fixed mistake answered wrong again is reopened.
Attempts are scanned once (StudentMistakeScan), lazily when the student opens Mistakes.
"""
import json

from django.db import transaction
from django.utils import timezone

from .answer_matching import check_english_answer, reference_answer
from .models import (
    English_Question, Math_Question, StudentMistake, StudentMistakeScan, Test, TestModule, TestReview,
)
from .numeric_answer_matching import check_written_answer

MODULE_NAMES = {"m1": "module_1", "m2": "module_2", "module_1": "module_1", "module_2": "module_2"}
QUESTION_MODELS = {"english": English_Question, "math": Math_Question}


def question_model(section):
    return QUESTION_MODELS.get(str(section or "").lower())


def answer_is_correct(section, question, response):
    """Same rules as the test runner and the topic drill."""
    if response is None or str(response).strip() == "":
        return False
    if section == "english":
        return bool(check_english_answer(question, response))
    if getattr(question, "written", False):
        return bool(check_written_answer(response, question.answer))
    return str(response).strip().upper() == str(question.answer or "").strip().upper()


def correct_answer_text(section, question):
    return reference_answer(question) if section == "english" else (question.answer or "")


def _module_answers(module_row):
    try:
        payload = json.loads(module_row.answers or '{"answers": []}')
    except (TypeError, ValueError):
        return {}
    answers = {}
    for item in (payload.get("answers") or []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        qid = item.get("questionID") or item.get("question_id") or item.get("id")
        if qid is None:
            continue
        answers[str(qid)] = item.get("answer")
    return answers


def _record(user, section, question, *, correct, response, review=None, when=None):
    """Apply one answer to the mistake log. Returns the StudentMistake row or None."""
    when = when or timezone.now()
    row = StudentMistake.objects.filter(user=user, section=section, question_id=question.pk).first()
    if correct:
        if row and row.status == StudentMistake.STATUS_OPEN:
            row.status = StudentMistake.STATUS_FIXED
            row.fixed_at = when
            row.save(update_fields=["status", "fixed_at"])
        return row
    answer_text = "" if response is None else str(response)[:255]
    if row is None:
        return StudentMistake.objects.create(
            user=user, section=section, question_id=question.pk, test_id=question.test_id,
            review=review, last_answer=answer_text, last_wrong_at=when,
        )
    row.status = StudentMistake.STATUS_OPEN
    row.fixed_at = None
    row.wrong_count += 1
    row.last_answer = answer_text
    row.last_wrong_at = when
    if review is not None:
        row.review = review
    row.save(update_fields=["status", "fixed_at", "wrong_count", "last_answer", "last_wrong_at", "review"])
    return row


def _scan_review(user, review):
    modules = TestModule.objects.filter(user=user, test=review.test, attempt_id=review.attempt_id)
    for module_row in modules:
        section = str(module_row.section or "").lower()
        model = question_model(section)
        module_name = MODULE_NAMES.get(str(module_row.module or "").lower())
        if model is None or module_name is None:
            continue
        answers = _module_answers(module_row)
        for question in model.objects.filter(test=review.test, module=module_name).order_by("number", "id"):
            response = answers.get(str(question.pk))
            _record(user, section, question, correct=answer_is_correct(section, question, response),
                    response=response, review=review, when=review.created_at)


def sync_student_mistakes(user):
    """Turn every scored practice-test attempt not seen yet into mistake rows (oldest first)."""
    if not getattr(user, "is_authenticated", False):
        return 0
    scanned = StudentMistakeScan.objects.filter(user=user).values_list("review_id", flat=True)
    reviews = (
        TestReview.objects.filter(user=user, score__isnull=False, test__isnull=False,
                                  test__test_type=Test.TYPE_REGULAR)
        .exclude(test_type__in=["makeup", "event", "placement"])
        .exclude(pk__in=scanned)
        .select_related("test")
        .order_by("created_at", "id")
    )
    count = 0
    for review in reviews:
        with transaction.atomic():
            _scan_review(user, review)
            StudentMistakeScan.objects.get_or_create(user=user, review=review)
        count += 1
    return count


def record_drill_answer(user, section, question, response):
    """A retry from the Mistakes drill. Returns (correct, row)."""
    correct = answer_is_correct(section, question, response)
    row = _record(user, section, question, correct=correct, response=response)
    return correct, row


def open_mistake_count(user):
    if not getattr(user, "is_authenticated", False):
        return 0
    return StudentMistake.objects.filter(user=user, status=StudentMistake.STATUS_OPEN).count()


def load_questions(rows):
    """Attach .question to each StudentMistake row (two queries); drop rows whose question is gone."""
    by_section = {"english": set(), "math": set()}
    for row in rows:
        by_section.setdefault(row.section, set()).add(row.question_id)
    found = {}
    for section, ids in by_section.items():
        model = question_model(section)
        if model is None or not ids:
            continue
        for question in model.objects.filter(pk__in=ids).select_related("test", "type", "domain"):
            found[(section, question.pk)] = question
    kept = []
    for row in rows:
        row.question = found.get((row.section, row.question_id))
        if row.question is not None:
            kept.append(row)
    return kept
