"""Mirror makonbook-api's vocabulary lists into this app's vocabulary units.

Each API list (e.g. sat-unit-1) becomes a VocabularyUnit (``source_slug``) and
its words VocabularyWords (``source_id``), with the part of speech and the
picture. The API's lists replace the units made in this app: those are
switched off (is_active=False), not deleted, so nothing that points at them
breaks. Students' own decks copied from a synced unit get the new
definitions, examples and pictures of the words they share.

Runs only when the API's deck version changed, so a quiet day costs one query.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.db import transaction

from apps.sat.models import VocabularyDeckWord, VocabularyUnit, VocabularyWord

from .source import VocabList, VocabWord

VOCAB_IMAGE_PREFIX = "v/img/"


@dataclass
class VocabularySummary:
    version: str = ""
    skipped: str = ""
    lists: int = 0
    words_created: int = 0
    words_updated: int = 0
    words_retired: int = 0
    units_retired: int = 0
    legacy_units_retired: int = 0
    deck_words_updated: int = 0
    images: int = 0

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def _unit_for(item: VocabList, by_slug: dict[str, VocabularyUnit]) -> VocabularyUnit:
    title = item.title.strip()[:200] or item.slug
    unit = by_slug.get(item.slug)
    # Unit titles are unique: move an old unit of the same name out of the way.
    clash = VocabularyUnit.objects.filter(title=title).exclude(source_slug=item.slug).first()
    if clash is not None:
        clash.title = f"{title} (old {clash.pk})"[:200]
        clash.save(update_fields=["title"])
    if unit is None:
        unit = VocabularyUnit(source_slug=item.slug)
    unit.title = title
    unit.order = item.position + 1
    unit.is_active = True
    unit.save()
    return unit


def sync_vocabulary(
    version: str | None,
    lists: list[VocabList] | None,
    words: list[VocabWord] | None,
    mirror,
    *,
    last_version: str = "",
    dry_run: bool = False,
    force: bool = False,
) -> VocabularySummary:
    summary = VocabularySummary(version=version or "")
    if not version:
        summary.skipped = "makonbook-api has no vocabulary deck yet"
        return summary
    if version == last_version and not force:
        summary.skipped = "unchanged"
        return summary
    if not lists or not words:
        # Never switch the old units off because of an empty read.
        summary.skipped = "makonbook-api returned no lists or no words"
        return summary
    summary.lists = len(lists)
    if dry_run:
        known = set(VocabularyWord.objects.exclude(source_id="").values_list("source_id", flat=True))
        summary.words_created = sum(1 for w in words if w.id not in known)
        summary.words_updated = len(words) - summary.words_created
        summary.legacy_units_retired = VocabularyUnit.objects.filter(source_slug__isnull=True, is_active=True).count()
        return summary

    image_urls = {}
    for word in words:
        if word.image and word.image not in image_urls:
            image_urls[word.image] = mirror.url(VOCAB_IMAGE_PREFIX + word.image)
    summary.images = len(image_urls)

    with transaction.atomic():
        by_slug = {u.source_slug: u for u in VocabularyUnit.objects.filter(source_slug__isnull=False)}
        units = {item.slug: _unit_for(item, by_slug) for item in lists}

        existing = {w.source_id: w for w in VocabularyWord.objects.exclude(source_id="")}
        kept = set()
        for item in words:
            unit = units.get(item.list_slug)
            if unit is None:
                continue
            text = item.word.strip()[:255]
            row = existing.get(item.id)
            if row is None:
                # A word typed into this unit before, or one that moved lists.
                row = VocabularyWord.objects.filter(unit=unit, word=text).first() or VocabularyWord(unit=unit)
                created = row.pk is None
            else:
                created = False
            if row.unit_id != unit.id:
                # Moved to another list: free the name in the new unit first.
                VocabularyWord.objects.filter(unit=unit, word=text).exclude(pk=row.pk).delete()
                row.unit = unit
            row.word = text
            row.meaning = item.definition
            row.example = item.example
            row.part_of_speech = (item.part_of_speech or "")[:40]
            row.image_url = image_urls.get(item.image, "") if item.image else ""
            row.source_id = item.id
            row.is_active = True
            row.save()
            kept.add(row.pk)
            if created:
                summary.words_created += 1
            else:
                summary.words_updated += 1

        synced_unit_ids = [u.pk for u in units.values()]
        summary.words_retired = (
            VocabularyWord.objects.filter(unit_id__in=synced_unit_ids, is_active=True).exclude(pk__in=kept).update(is_active=False)
        )
        retired_synced = VocabularyUnit.objects.filter(source_slug__isnull=False, is_active=True).exclude(
            pk__in=synced_unit_ids
        )
        retired_legacy = VocabularyUnit.objects.filter(source_slug__isnull=True, is_active=True)
        retired_ids = list(retired_synced.values_list("pk", flat=True)) + list(retired_legacy.values_list("pk", flat=True))
        summary.units_retired = retired_synced.update(is_active=False)
        summary.legacy_units_retired = retired_legacy.update(is_active=False)
        VocabularyWord.objects.filter(unit_id__in=retired_ids, is_active=True).update(is_active=False)

        # Students' decks copied from a synced unit: refresh the words they share.
        fresh = {}
        for word in VocabularyWord.objects.filter(pk__in=kept):
            fresh[(word.unit_id, word.word.lower())] = word
        deck_words = VocabularyDeckWord.objects.filter(deck__source_unit_id__in=synced_unit_ids).select_related("deck")
        for deck_word in deck_words:
            source = fresh.get((deck_word.deck.source_unit_id, deck_word.word.lower()))
            if source is None:
                continue
            values = {
                "meaning": source.meaning,
                "example": source.example or "",
                "part_of_speech": source.part_of_speech,
                "image_url": source.image_url,
            }
            if any(getattr(deck_word, k) != v for k, v in values.items()):
                for k, v in values.items():
                    setattr(deck_word, k, v)
                deck_word.save(update_fields=list(values))
                summary.deck_words_updated += 1
    return summary
