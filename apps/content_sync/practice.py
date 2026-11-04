"""Mirror makonbook-api's published practice tests into this app's tests.

Each published test (e.g. DAY12) becomes a regular Test of the same name with
its English_Question / Math_Question rows. The text is stored exactly as the
API has it (content_format="makon"), except that ``![...](r2:<key>)`` figure
links point at this site's copy of the image; apps.sat.rich_text renders it
when a page shows it.

A test is written again only when the API publishes a new version of it.
Questions are updated in place by module and number, so links to them (the
World question pool, attempts in progress) survive a new version.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from apps.sat.models import (
    ClassroomMembership,
    ClassroomPracticeTestAccessPolicy,
    English_Question,
    Math_Question,
    QuestionDomain,
    QuestionType,
    Test,
)
from apps.sat.rich_text import FORMAT_MAKON

from .source import PublishedTest

PRACTICE_IMAGE_PREFIX = "p/img/"
_FIGURE_LINK = re.compile(r"(!\[[^\]]*\]\()r2:([^)\s]*)(\))")


@dataclass
class PracticeSummary:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)  # a test of the same name not from the API
    withdrawn: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    questions_written: int = 0

    @property
    def changed(self) -> bool:
        return bool(self.created or self.updated or self.withdrawn)

    def as_dict(self) -> dict:
        return {
            "created": self.created,
            "updated": self.updated,
            "unchanged": len(self.unchanged),
            "conflicts": self.conflicts,
            "withdrawn": self.withdrawn,
            "failed": self.failed,
            "questions_written": self.questions_written,
        }


def link_figures(text, figure_urls: dict[str, str]):
    """Point ``![alt](r2:key)`` at this site's copy; unknown keys stay as they are."""
    if not text:
        return text

    def replace(match):
        url = figure_urls.get(match.group(2))
        return f"{match.group(1)}{url}{match.group(3)}" if url else match.group(0)

    return _FIGURE_LINK.sub(replace, text)


class _Taxonomy:
    def __init__(self):
        self.domains: dict[str, QuestionDomain] = {}
        self.types: dict[tuple[str, str], QuestionType] = {}

    def domain(self, name: str):
        name = (name or "").strip()[:100]
        if not name:
            return None
        if name not in self.domains:
            row = QuestionDomain.objects.filter(name=name).order_by("id").first()
            self.domains[name] = row or QuestionDomain.objects.create(name=name)
        return self.domains[name]

    def type(self, domain, name: str):
        name = (name or "").strip()[:100]
        if not name or domain is None:
            return None
        key = (domain.name, name)
        if key not in self.types:
            row = QuestionType.objects.filter(name=name, domain=domain).order_by("id").first()
            self.types[key] = row or QuestionType.objects.create(name=name, domain=domain)
        return self.types[key]


def _figure_urls(package: dict, mirror) -> dict[str, str]:
    urls = {}
    for key, image in (package.get("images") or {}).items():
        file = (image or {}).get("file")
        if file:
            urls[key] = mirror.url(PRACTICE_IMAGE_PREFIX + file)
    return urls


def _question_fields(subject: str, q: dict, figure_urls: dict[str, str], taxonomy: _Taxonomy) -> dict:
    choices = q.get("choices") or {}
    accepted = [str(a) for a in (q.get("accepted") or [])]
    domain = taxonomy.domain(q.get("domain"))
    fields = {
        "passage": link_figures(q.get("passage") or "", figure_urls) or None,
        "question": link_figures(q.get("stem") or "", figure_urls),
        "a": link_figures(choices.get("A") or "", figure_urls),
        "b": link_figures(choices.get("B") or "", figure_urls),
        "c": link_figures(choices.get("C") or "", figure_urls),
        "d": link_figures(choices.get("D") or "", figure_urls),
        "explained": link_figures(q.get("explanation") or "", figure_urls),
        "domain": domain,
        "type": taxonomy.type(domain, q.get("skill")),
        "graph": False,
        "image": None,
        "content_format": FORMAT_MAKON,
        "source_question_id": str(q.get("id") or "")[:36],
        "source_difficulty": str(q.get("difficulty") or "")[:10],
    }
    grid_in = q.get("type") == "grid_in"
    if subject == "math":
        fields["written"] = grid_in
        # The runner's checker takes alternatives separated by ";" (numeric_answer_matching).
        fields["answer"] = ("; ".join(accepted) if grid_in else (q.get("correct") or ""))[:400]
        fields["choice_graph"] = False
        fields["img_explain"] = None
        for letter in "abcd":
            fields[f"image_{letter}"] = None
    else:
        fields["response_type"] = "open_text" if grid_in else "multiple_choice"
        fields["answer"] = ((accepted[0] if accepted else "") if grid_in else (q.get("correct") or ""))[:400]
        fields["accepted_answers"] = "\n".join(accepted) if grid_in else ""
        fields["answer_patterns"] = ""
    return fields


def _write_questions(test: Test, package: dict, figure_urls: dict[str, str], taxonomy: _Taxonomy) -> int:
    written = 0
    for section in package.get("sections") or []:
        subject = section.get("subject")
        if subject not in {"english", "math"}:
            continue
        model = Math_Question if subject == "math" else English_Question
        existing = {(row.module, row.number): row for row in model.objects.filter(test=test)}
        seen = set()
        for module in section.get("modules") or []:
            module_name = f"module_{int(module.get('module'))}"
            for q in module.get("questions") or []:
                number = int(q.get("position"))
                fields = _question_fields(subject, q, figure_urls, taxonomy)
                row = existing.get((module_name, number))
                if row is None:
                    row = model(test=test, module=module_name, number=number)
                for name, value in fields.items():
                    setattr(row, name, value)
                row.save()
                seen.add(row.pk)
                written += 1
        # Places the new version no longer has (a test can only shrink by an edit).
        model.objects.filter(test=test).exclude(pk__in=seen).delete()
    return written


def _grant_to_all_access_classrooms():
    """Classrooms set to "All practice tests" grant access when a student joins;
    apply it again so students already in them get the new tests too."""
    from apps.sat.classroom_access_policy import apply_classroom_access_policy_to_membership

    classroom_ids = ClassroomPracticeTestAccessPolicy.objects.filter(
        access_mode=ClassroomPracticeTestAccessPolicy.ACCESS_MODE_ALL
    ).values_list("classroom_id", flat=True)
    memberships = ClassroomMembership.objects.filter(
        classroom_id__in=list(classroom_ids), role="student", status="approved"
    ).select_related("classroom")
    for membership in memberships:
        apply_classroom_access_policy_to_membership(membership)


def sync_practice(tests: list[PublishedTest], mirror, *, dry_run: bool = False, force: bool = False) -> PracticeSummary:
    summary = PracticeSummary()
    taxonomy = _Taxonomy()
    names = set()
    for published in tests:
        name = published.code.strip()[:400]
        names.add(name)
        current = Test.objects.filter(name=name).first()
        if current is not None and current.source != Test.SOURCE_MAKONBOOK_API:
            # A test made in this app has that name. remove_legacy_tests deals
            # with those; the sync never overwrites one.
            summary.conflicts.append(name)
            continue
        if current is not None and current.source_version == published.version and not force:
            summary.unchanged.append(name)
            continue
        if dry_run:
            (summary.created if current is None else summary.updated).append(name)
            continue
        try:
            figure_urls = _figure_urls(published.package, mirror)
            with transaction.atomic():
                test = current or Test(name=name)
                test.test_type = Test.TYPE_REGULAR
                test.is_available = True
                test.source = Test.SOURCE_MAKONBOOK_API
                test.source_version = published.version
                test.source_synced_at = timezone.now()
                if test.published_at is None:
                    test.published_at = published.published_at
                test.save()
                summary.questions_written += _write_questions(test, published.package, figure_urls, taxonomy)
        except Exception as exc:  # noqa: BLE001 - one bad test must not stop the others
            summary.failed[name] = f"{type(exc).__name__}: {exc}"
            continue
        (summary.created if current is None else summary.updated).append(name)

    # A synced test the API no longer has: hide it (results stay).
    gone = Test.objects.filter(source=Test.SOURCE_MAKONBOOK_API, is_available=True).exclude(name__in=names)
    for test in gone:
        summary.withdrawn.append(test.name)
        if not dry_run:
            test.is_available = False
            test.save(update_fields=["is_available"])

    if not dry_run and summary.created:
        _grant_to_all_access_classrooms()
    if not dry_run and summary.changed:
        from apps.world.services import sync_question_pool

        sync_question_pool()
    return summary
