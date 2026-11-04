"""Remove the regular practice tests made in this app, with their results.

Regular practice tests now come from makonbook-api only (apps.content_sync).
The regular tests made in this app before are removed with their questions
and what was recorded about them: attempts, scores, reviews, drafts,
integrity reports and homework that assigned them. Run it once, before the
first sync, so the synced tests can take their names (DAY1, DAY2, …).

Kept, untouched:
- placement, event and makeup tests and their results;
- questions a makeup test uses, even when they came from a removed test
  (they lose their test, the makeup test keeps working);
- a regular test that an event runs on: deleting it would delete the event,
  so it is skipped and reported instead.

Vocabulary is not touched here: the vocabulary sync switches the old units off.
"""

from __future__ import annotations

from collections import Counter

from django.db import transaction

from apps.sat.models import (
    English_Question,
    ExamIntegrityViolation,
    GlobalEvent,
    MakeupTestEnglishQuestion,
    MakeupTestMathQuestion,
    Math_Question,
    Test,
    TestModule,
    TestReview,
    TestStage,
)


def remove_legacy_tests(*, confirm: bool = False) -> dict:
    """Delete them and return what was deleted per model. Without ``confirm``
    the same deletion runs and is rolled back, so the counts are exact."""
    deleted: Counter = Counter()

    def count(result):
        for label, n in result[1].items():
            deleted[label] += n

    with transaction.atomic():
        regular = Test.objects.filter(test_type=Test.TYPE_REGULAR).exclude(source=Test.SOURCE_MAKONBOOK_API)
        used_by_events = {}
        for event in GlobalEvent.objects.filter(test__in=regular).order_by("title"):
            used_by_events.setdefault(event.test_id, []).append(event.title)
        names = [name for name in regular.values_list("pk", flat=True) if name not in used_by_events]

        for model in (TestModule, TestReview, TestStage):
            count(model.objects.filter(test_id__in=names).delete())
        count(ExamIntegrityViolation.objects.filter(test_id__in=names).delete())

        in_makeup_english = MakeupTestEnglishQuestion.objects.values("english_question_id")
        in_makeup_math = MakeupTestMathQuestion.objects.values("math_question_id")
        count(English_Question.objects.filter(test_id__in=names).exclude(pk__in=in_makeup_english).delete())
        count(Math_Question.objects.filter(test_id__in=names).exclude(pk__in=in_makeup_math).delete())
        # Questions kept for makeup tests lose their test here (SET_NULL).
        count(Test.objects.filter(pk__in=names).delete())
        if not confirm:
            transaction.set_rollback(True)
    return {
        "tests": names,
        "kept_for_events": used_by_events,
        "deleted": dict(sorted((k, v) for k, v in deleted.items() if v)),
        "confirmed": confirm,
    }
