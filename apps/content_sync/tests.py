import json
from datetime import datetime, timezone as dt_timezone
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.content_sync.images import ImageMirror, ImageMirrorUnavailable
from apps.content_sync.legacy import remove_legacy_tests
from apps.content_sync.models import ContentSyncState, SyncedImage
from apps.content_sync.practice import link_figures, sync_practice
from apps.content_sync.service import run_sync
from apps.content_sync.source import PublishedTest, VocabList, VocabWord
from apps.content_sync.vocabulary import sync_vocabulary
from apps.sat.models import (
    Classroom,
    ClassroomMembership,
    ClassroomPracticeTestAccessPolicy,
    ClassroomSectionAccessPolicy,
    English_Question,
    GlobalEvent,
    Math_Question,
    StudentPracticeTestAccess,
    Test,
    TestReview,
    TestStage,
    VocabularyDeck,
    VocabularyDeckWord,
    VocabularyUnit,
    VocabularyWord,
)
from apps.sat.rich_text import runner_question_fields
from apps.world.models import GameQuestionPool


class FakeStorage:
    def __init__(self):
        self.files = {}

    def exists(self, name):
        return name in self.files

    def save(self, name, content):
        self.files[name] = content.read()
        return name

    def url(self, name):
        return f"https://cdn.test/media/{name}"


def fake_mirror():
    fetched = []

    def fetch(key):
        fetched.append(key)
        return b"PNG" + key.encode()

    mirror = ImageMirror(fetch=fetch, storage=FakeStorage())
    mirror.fetched = fetched
    return mirror


def mcq(position, stem="What is \\(x\\)?", correct="B", **extra):
    q = {
        "id": f"00000000-0000-0000-0000-{position:012d}",
        "version": 1,
        "position": position,
        "type": "mcq",
        "passage": None,
        "stem": stem,
        "choices": {"A": "1", "B": "2", "C": "3", "D": "4"},
        "figures": [],
        "correct": correct,
        "accepted": None,
        "explanation": "Because **2**.",
        "domain": "Algebra",
        "skill": "Linear functions",
        "difficulty": "hard",
    }
    q.update(extra)
    return q


def package(code="DAY12", version=1, math=None, english=None, images=None):
    math = math if math is not None else [
        mcq(1, stem="![A line](r2:sat/fig1.png)\n\nWhat is the slope?"),
        {**mcq(2), "type": "grid_in", "choices": None, "correct": None, "accepted": ["7/2", "3.5"]},
    ]
    english = english if english is not None else [
        mcq(1, stem="Which choice completes the text?", correct="C", domain="Craft and Structure", skill="Words in Context"),
    ]
    return PublishedTest(
        code=code,
        title=code,
        version=version,
        published_at=datetime(2026, 10, 1, tzinfo=dt_timezone.utc),
        package={
            "format": 1,
            "code": code,
            "version": version,
            "sections": [
                {"subject": "english", "modules": [{"module": 1, "minutes": 32, "questions": english}], "scale": []},
                {"subject": "math", "modules": [{"module": 1, "minutes": 35, "questions": math}], "scale": []},
            ],
            "images": images if images is not None else {"sat/fig1.png": {"file": "abc123.png", "bytes": 3, "width": 1, "height": 1}},
        },
    )


class LinkFiguresTests(TestCase):
    def test_known_keys_point_at_the_copy_unknown_keys_stay(self):
        text = "![a](r2:k1) and ![b](r2:k2)"
        self.assertEqual(link_figures(text, {"k1": "https://x/1.png"}), "![a](https://x/1.png) and ![b](r2:k2)")


class PracticeSyncTests(TestCase):
    def test_creates_a_regular_test_with_questions_in_the_api_format(self):
        mirror = fake_mirror()
        summary = sync_practice([package()], mirror)

        self.assertEqual(summary.created, ["DAY12"])
        test = Test.objects.get(name="DAY12")
        self.assertEqual(test.source, Test.SOURCE_MAKONBOOK_API)
        self.assertEqual(test.source_version, 1)
        self.assertEqual(test.test_type, Test.TYPE_REGULAR)
        self.assertTrue(test.is_available)

        q1 = Math_Question.objects.get(test=test, module="module_1", number=1)
        self.assertEqual(q1.content_format, "makon")
        self.assertIn("![A line](https://cdn.test/media/makonbook-api/p/img/abc123.png)", q1.question)
        self.assertEqual(q1.answer, "B")
        self.assertFalse(q1.written)
        self.assertEqual(q1.explained, "Because **2**.")
        self.assertEqual(q1.domain.name, "Algebra")
        self.assertEqual(q1.type.name, "Linear functions")
        self.assertEqual(q1.source_difficulty, "hard")

        grid = Math_Question.objects.get(test=test, number=2)
        self.assertTrue(grid.written)
        self.assertEqual(grid.answer, "7/2; 3.5")

        english = English_Question.objects.get(test=test)
        self.assertEqual(english.answer, "C")
        self.assertEqual(english.response_type, "multiple_choice")
        self.assertEqual(mirror.fetched, ["p/img/abc123.png"])
        self.assertTrue(SyncedImage.objects.filter(source_key="p/img/abc123.png").exists())

    def test_grid_in_answers_are_graded_by_the_existing_checker(self):
        from apps.sat.numeric_answer_matching import check_written_answer

        sync_practice([package()], fake_mirror())
        grid = Math_Question.objects.get(test__name="DAY12", number=2)
        self.assertTrue(check_written_answer("3.5", grid.answer))
        self.assertTrue(check_written_answer("7/2", grid.answer))
        self.assertFalse(check_written_answer("3", grid.answer))

    def test_same_version_is_not_written_again_and_a_new_one_updates_in_place(self):
        mirror = fake_mirror()
        sync_practice([package()], mirror)
        first = Math_Question.objects.get(test__name="DAY12", number=1)

        again = sync_practice([package()], mirror)
        self.assertEqual(again.unchanged, ["DAY12"])

        changed = package(version=2, math=[mcq(1, stem="Fixed stem", correct="D")])
        summary = sync_practice([changed], mirror)
        self.assertEqual(summary.updated, ["DAY12"])
        updated = Math_Question.objects.get(test__name="DAY12", number=1)
        self.assertEqual(updated.pk, first.pk)
        self.assertEqual(updated.question, "Fixed stem")
        self.assertEqual(updated.answer, "D")
        self.assertFalse(Math_Question.objects.filter(test__name="DAY12", number=2).exists())
        self.assertEqual(Test.objects.get(name="DAY12").source_version, 2)
        self.assertEqual(mirror.fetched, ["p/img/abc123.png"])  # copied once

    def test_never_overwrites_a_test_made_in_this_app(self):
        Test.objects.create(name="DAY12")
        summary = sync_practice([package()], fake_mirror())
        self.assertEqual(summary.conflicts, ["DAY12"])
        self.assertEqual(Test.objects.get(name="DAY12").source, "")

    def test_a_test_the_api_no_longer_has_is_hidden(self):
        sync_practice([package()], fake_mirror())
        summary = sync_practice([], fake_mirror())
        self.assertEqual(summary.withdrawn, ["DAY12"])
        self.assertFalse(Test.objects.get(name="DAY12").is_available)

    def test_dry_run_writes_nothing(self):
        summary = sync_practice([package()], fake_mirror(), dry_run=True)
        self.assertEqual(summary.created, ["DAY12"])
        self.assertFalse(Test.objects.exists())

    def test_a_test_whose_images_cannot_be_read_is_reported_and_skipped(self):
        def fetch(key):
            raise ImageMirrorUnavailable("no token")

        summary = sync_practice([package()], ImageMirror(fetch=fetch, storage=FakeStorage()))
        self.assertIn("DAY12", summary.failed)
        self.assertFalse(Test.objects.exists())

    def test_questions_feed_the_world_pool_with_their_difficulty(self):
        sync_practice([package()], fake_mirror())
        pool = GameQuestionPool.objects.get(math_question__number=1, math_question__test__name="DAY12")
        self.assertTrue(pool.game_enabled)
        self.assertEqual(pool.difficulty, "hard")

    def test_classrooms_open_to_all_tests_get_new_tests(self):
        teacher = User.objects.create_user("teacher", password="x")
        student = User.objects.create_user("student", password="x")
        classroom = Classroom.objects.create(name="SAT A", teacher=teacher)
        ClassroomSectionAccessPolicy.objects.update_or_create(
            classroom=classroom, section="practice_tests", defaults={"has_access": True}
        )
        ClassroomPracticeTestAccessPolicy.objects.update_or_create(
            classroom=classroom, defaults={"access_mode": ClassroomPracticeTestAccessPolicy.ACCESS_MODE_ALL}
        )
        membership = ClassroomMembership.objects.create(classroom=classroom, user=student, role="student", status="approved")

        sync_practice([package()], fake_mirror())

        self.assertTrue(
            StudentPracticeTestAccess.objects.filter(membership=membership, test__name="DAY12", has_access=True).exists()
        )


class RunnerFieldsTests(TestCase):
    def test_makon_questions_reach_the_runner_rendered(self):
        sync_practice([package()], fake_mirror())
        q = Math_Question.objects.get(test__name="DAY12", number=1)
        fields = runner_question_fields(q)
        self.assertEqual(fields["format"], "makon")
        self.assertIn('<img class="mk-figure" src="https://cdn.test/media/makonbook-api/p/img/abc123.png"', fields["question"])
        self.assertEqual(fields["b"], "2")

    def test_legacy_questions_reach_the_runner_as_stored(self):
        test = Test.objects.create(name="Old")
        q = Math_Question.objects.create(test=test, module="module_1", number=1, question="<b>x</b>", a="1", answer="A")
        fields = runner_question_fields(q)
        self.assertEqual(fields["format"], "legacy")
        self.assertEqual(fields["question"], "<b>x</b>")


def vocab_source(version="v1", words=None):
    lists = [VocabList(slug="sat-unit-1", title="SAT Words: Unit 1", position=0)]
    words = words if words is not None else [
        VocabWord(id="w1", list_slug="sat-unit-1", position=1, word="banal", part_of_speech="adjective",
                  definition="unoriginal", example="A banal line.", image="banal.png"),
        VocabWord(id="w2", list_slug="sat-unit-1", position=2, word="candid", part_of_speech="adjective",
                  definition="frank", example="A candid talk.", image=""),
    ]
    return version, lists, words


class VocabularySyncTests(TestCase):
    def test_lists_replace_the_old_units(self):
        old = VocabularyUnit.objects.create(title="SAT Words: Unit 1")
        VocabularyWord.objects.create(unit=old, word="banal", meaning="old")
        other = VocabularyUnit.objects.create(title="My old unit")

        version, lists, words = vocab_source()
        summary = sync_vocabulary(version, lists, words, fake_mirror())

        self.assertEqual(summary.words_created, 2)
        self.assertEqual(summary.legacy_units_retired, 2)
        unit = VocabularyUnit.objects.get(source_slug="sat-unit-1")
        self.assertEqual(unit.title, "SAT Words: Unit 1")
        self.assertTrue(unit.is_active)
        old.refresh_from_db()
        other.refresh_from_db()
        self.assertFalse(old.is_active)
        self.assertFalse(other.is_active)
        self.assertTrue(old.title.startswith("SAT Words: Unit 1 (old"))
        self.assertFalse(VocabularyWord.objects.filter(unit=old, is_active=True).exists())

        banal = VocabularyWord.objects.get(unit=unit, word="banal")
        self.assertEqual(banal.meaning, "unoriginal")
        self.assertEqual(banal.part_of_speech, "adjective")
        self.assertEqual(banal.image_url, "https://cdn.test/media/makonbook-api/v/img/banal.png")
        self.assertEqual(VocabularyWord.objects.get(unit=unit, word="candid").image_url, "")

    def test_unchanged_deck_version_does_nothing(self):
        version, lists, words = vocab_source()
        summary = sync_vocabulary(version, lists, words, fake_mirror(), last_version="v1")
        self.assertEqual(summary.skipped, "unchanged")
        self.assertFalse(VocabularyUnit.objects.exists())

    def test_an_empty_read_never_retires_the_old_units(self):
        old = VocabularyUnit.objects.create(title="Keep me")
        summary = sync_vocabulary("v2", [], [], fake_mirror())
        self.assertTrue(summary.skipped)
        old.refresh_from_db()
        self.assertTrue(old.is_active)

    def test_removed_words_are_switched_off_and_student_decks_follow_changes(self):
        version, lists, words = vocab_source()
        sync_vocabulary(version, lists, words, fake_mirror())
        unit = VocabularyUnit.objects.get(source_slug="sat-unit-1")
        owner = User.objects.create_user("s", password="x")
        deck = VocabularyDeck.objects.create(owner=owner, title=unit.title, source_unit=unit)
        VocabularyDeckWord.objects.create(deck=deck, word="banal", meaning="unoriginal", order=1)

        changed = [VocabWord(id="w1", list_slug="sat-unit-1", position=1, word="banal", part_of_speech="adjective",
                             definition="boringly ordinary", example="New example.", image="banal.png")]
        summary = sync_vocabulary("v2", lists, changed, fake_mirror(), last_version="v1")

        self.assertEqual(summary.words_retired, 1)
        self.assertFalse(VocabularyWord.objects.get(word="candid").is_active)
        deck_word = VocabularyDeckWord.objects.get(deck=deck)
        self.assertEqual(deck_word.meaning, "boringly ordinary")
        self.assertEqual(deck_word.image_url, "https://cdn.test/media/makonbook-api/v/img/banal.png")


class FakeSource:
    def __init__(self, tests=(), vocab=None):
        self.tests = list(tests)
        self.vocab = vocab or vocab_source()

    def available(self):
        return True

    def published_tests(self):
        return self.tests

    def vocab_deck_version(self):
        return self.vocab[0]

    def vocab_lists(self):
        return self.vocab[1]

    def vocab_words(self):
        return self.vocab[2]


class RunSyncTests(TestCase):
    def test_records_state_and_skips_an_unchanged_deck_next_time(self):
        source = FakeSource([package()])
        result = run_sync(source=source, mirror=fake_mirror())
        self.assertEqual(result["practice"]["created"], ["DAY12"])
        self.assertEqual(result["vocabulary"]["words_created"], 2)
        self.assertEqual(ContentSyncState.objects.get(key="vocabulary").value, "v1")
        self.assertIsNotNone(ContentSyncState.objects.get(key="practice").last_success_at)

        source.vocab_lists = mock.Mock(side_effect=AssertionError("must not be read"))
        again = run_sync(source=source, mirror=fake_mirror())
        self.assertEqual(again["vocabulary"]["skipped"], "unchanged")

    def test_a_failing_part_is_reported_and_the_other_still_runs(self):
        source = FakeSource([package()])
        source.published_tests = mock.Mock(side_effect=RuntimeError("db down"))
        with self.assertLogs("apps.content_sync.service", level="ERROR"):
            result = run_sync(source=source, mirror=fake_mirror())
        self.assertIn("db down", result["practice"]["error"])
        self.assertEqual(result["vocabulary"]["words_created"], 2)
        self.assertIn("db down", ContentSyncState.objects.get(key="practice").last_error)

    def test_without_the_database_it_does_nothing(self):
        result = run_sync()  # the test settings have no makonbook_api alias
        self.assertIn("skipped", result)


class RemoveLegacyTestsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u", password="x")
        self.old = Test.objects.create(name="DAY1")
        self.placement = Test.objects.create(name="Placement", test_type=Test.TYPE_PLACEMENT)
        English_Question.objects.create(test=self.old, module="module_1", number=1, question="q", answer="A")
        Math_Question.objects.create(test=None, module="module_1", number=1, question="orphan", answer="A")
        TestStage.objects.create(user=self.user, test=self.old, stage=1)
        TestReview.objects.create(user=self.user, test=self.old, key="r1", score=1000)
        GlobalEvent.objects.create(
            title="Mock", slug="mock", test=self.placement, start_at=timezone.now(), end_at=timezone.now()
        )
        sync_practice([package()], fake_mirror())

    def test_without_confirm_nothing_is_deleted(self):
        result = remove_legacy_tests()
        self.assertFalse(result["confirmed"])
        self.assertEqual(sorted(result["tests"]), ["DAY1", "Placement"])
        self.assertEqual(result["deleted"]["sat.Test"], 2)
        self.assertEqual(Test.objects.count(), 3)
        self.assertTrue(TestStage.objects.exists())

    def test_confirm_deletes_old_tests_questions_and_results_but_keeps_synced_ones(self):
        remove_legacy_tests(confirm=True)
        self.assertEqual(list(Test.objects.values_list("name", flat=True)), ["DAY12"])
        self.assertFalse(English_Question.objects.exclude(content_format="makon").exists())
        self.assertFalse(Math_Question.objects.exclude(content_format="makon").exists())
        self.assertFalse(TestStage.objects.exists())
        self.assertFalse(TestReview.objects.exists())
        self.assertFalse(GlobalEvent.objects.exists())
        self.assertEqual(Math_Question.objects.filter(test__name="DAY12").count(), 2)

    def test_command(self):
        from io import StringIO

        out = StringIO()
        call_command("remove_legacy_tests", stdout=out)
        self.assertIn("Would delete 2 test(s)", out.getvalue())
        self.assertEqual(Test.objects.count(), 3)
        call_command("remove_legacy_tests", "--confirm", stdout=out)
        self.assertEqual(Test.objects.count(), 1)
