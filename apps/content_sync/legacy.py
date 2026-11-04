"""Remove every test that did not come from makonbook-api, with its results.

MakonBook's tests now come from makonbook-api only (apps.content_sync). The
tests made in this app before — regular, placement, event and makeup tests —
are removed together with their questions and everything recorded about them:
attempts, scores, reviews, drafts, integrity reports, homework that assigned
them, and events built on them. Run it once, before the first sync.

Vocabulary is not touched here: the vocabulary sync switches the old units off.
"""

from __future__ import annotations

from collections import Counter

from django.db import transaction
from django.db.models import Q

from apps.sat.models import (
    English_Question,
    ExamIntegrityViolation,
    MakeupTest,
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
        legacy = Test.objects.exclude(source=Test.SOURCE_MAKONBOOK_API)
        legacy_names = list(legacy.values_list("pk", flat=True))
        old_results = Q(test_id__in=legacy_names) | Q(makeup_test__isnull=False) | Q(test__isnull=True, makeup_test__isnull=True)
        for model in (TestModule, TestReview, TestStage):
            count(model.objects.filter(old_results).delete())
        count(ExamIntegrityViolation.objects.filter(test_id__in=legacy_names).delete())
        count(MakeupTest.objects.all().delete())
        for model in (English_Question, Math_Question):
            count(model.objects.filter(Q(test_id__in=legacy_names) | Q(test__isnull=True)).delete())
        count(Test.objects.filter(pk__in=legacy_names).delete())
        if not confirm:
            transaction.set_rollback(True)
    return {
        "tests": legacy_names,
        "deleted": dict(sorted((k, v) for k, v in deleted.items() if v)),
        "confirmed": confirm,
    }
