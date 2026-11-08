"""Read practice tests and vocabulary from makonbook-api's database.

Read only, by construction: the ``makonbook_api`` connection is opened with
``default_transaction_read_only=on`` (satmakon/settings.py), and this module
only runs SELECTs. Nothing here writes to makonbook-api's database, ever.

What is read:
- the latest *published* version of every practice test
  (``practice_test_versions.package``): only tests whose every question was
  approved, frozen as an immutable package (makonbook-api spec 9.5);
- the vocabulary lists and words that aren't removed, and the deck version
  (``vocab_deck``) that changes whenever they do (spec 11).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from django.conf import settings
from django.db import connections

from .routers import ALIAS


class SourceUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class PublishedTest:
    code: str
    title: str
    version: int
    published_at: datetime
    package: dict


@dataclass(frozen=True)
class VocabList:
    slug: str
    title: str
    position: int


@dataclass(frozen=True)
class VocabWord:
    id: str
    list_slug: str
    position: int
    word: str
    part_of_speech: str
    definition: str
    example: str
    image: str  # a file name under v/img/ in makonbook-api's bucket, or ""


def _json(value):
    if isinstance(value, (bytes, bytearray, memoryview)):
        value = bytes(value).decode("utf-8")
    if isinstance(value, str):
        return json.loads(value)
    return value


class ApiSource:
    def __init__(self, alias: str = ALIAS):
        self.alias = alias

    def available(self) -> bool:
        return self.alias in settings.DATABASES

    def _rows(self, sql: str, params=()):
        if not self.available():
            raise SourceUnavailable(f"No '{self.alias}' database is configured.")
        with connections[self.alias].cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()

    def published_tests(self) -> list[PublishedTest]:
        rows = self._rows(
            """
            SELECT t.code, t.title, v.version, v.published_at, v.package
            FROM practice_tests t
            JOIN LATERAL (
                SELECT version, published_at, package
                FROM practice_test_versions
                WHERE test_id = t.id
                ORDER BY version DESC
                LIMIT 1
            ) v ON true
            ORDER BY t.code
            """
        )
        return [
            PublishedTest(code=code, title=title, version=int(version), published_at=published_at, package=_json(package))
            for code, title, version, published_at, package in rows
        ]

    def vocab_deck_version(self) -> str | None:
        rows = self._rows("SELECT version FROM vocab_deck LIMIT 1")
        return rows[0][0] if rows else None

    def vocab_lists(self) -> list[VocabList]:
        rows = self._rows(
            "SELECT slug, title, position FROM vocab_lists WHERE removed_at IS NULL ORDER BY position, slug"
        )
        return [VocabList(slug=slug, title=title, position=int(position)) for slug, title, position in rows]

    def vocab_words(self) -> list[VocabWord]:
        rows = self._rows(
            """
            SELECT w.id::text, l.slug, w.position, w.word, coalesce(w.part_of_speech, ''),
                   w.definition, w.example, coalesce(w.image, '')
            FROM vocab_words w
            JOIN vocab_lists l ON l.id = w.list_id
            WHERE w.removed_at IS NULL AND l.removed_at IS NULL
            ORDER BY l.position, w.position
            """
        )
        return [
            VocabWord(
                id=row[0], list_slug=row[1], position=int(row[2]), word=row[3], part_of_speech=row[4],
                definition=row[5], example=row[6], image=row[7],
            )
            for row in rows
        ]
