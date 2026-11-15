"""V73 A-to-Z: the student's Vocabulary workspace end to end (decks, library, study, arena, quiz)."""
import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.sat.models import (
    VocabularyDeck, VocabularyDeckWord, VocabularyDeckWordProgress, VocabularyQuizAttempt, VocabularyUnit,
    VocabularyWord, VocabularyWordProgress,
)

WORDS = [("abate", "to lessen"), ("candid", "frank, honest"), ("diligent", "hard-working"),
         ("eloquent", "fluent in speech"), ("frugal", "careful with money")]


class VocabularyJourneyTests(TestCase):
    def setUp(self):
        self.kid = User.objects.create_user("voc_kid", password="x")
        self.other = User.objects.create_user("voc_other", password="x")
        self.unit = VocabularyUnit.objects.create(title="Unit 1 — SAT core", order=1)
        for word, meaning in WORDS:
            VocabularyWord.objects.create(unit=self.unit, word=word, meaning=meaning, example=f"{word} example")
        VocabularyWord.objects.create(unit=self.unit, word="hidden", meaning="inactive word", is_active=False)
        self.client.force_login(self.kid)

    # ---------------------------------------------------------------- pages
    def test_every_vocabulary_page_opens(self):
        for name in ("vocabulary_root", "vocabulary_decks_root", "vocabulary_deck_library_root",
                     "vocabulary_practice_quiz_root"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        for slug in ("word_lists", "flashcards", "practice-quiz"):
            response = self.client.get(reverse("vocabulary_section_root", args=[slug]))
            self.assertIn(response.status_code, (200, 302), slug)

    # ---------------------------------------------------------------- personal decks
    def test_create_deck_add_and_remove_words(self):
        response = self.client.post(reverse("vocabulary_deck_create_root"), {"title": "My words", "new_cards_per_day": "9999"})
        deck = VocabularyDeck.objects.get(owner=self.kid)
        self.assertRedirects(response, reverse("vocabulary_deck_detail_root", args=[deck.id]), fetch_redirect_response=False)
        self.assertEqual(deck.new_cards_per_day, 200)  # clamped
        detail = reverse("vocabulary_deck_detail_root", args=[deck.id])
        self.client.post(detail, {"word": "zeal", "meaning": "great energy"})
        self.client.post(detail, {"word": "ZEAL", "meaning": "duplicate"})  # case-insensitive duplicate
        self.client.post(detail, {"word": "", "meaning": "no word"})
        self.assertEqual(list(deck.words.values_list("word", flat=True)), ["zeal"])
        word = deck.words.get()
        self.client.post(detail, {"action": "delete_word", "word_id": word.id})
        self.assertFalse(deck.words.exists())
        self.assertEqual(self.client.get(detail).status_code, 200)

    def test_deck_needs_a_name(self):
        self.client.post(reverse("vocabulary_deck_create_root"), {"title": "  "})
        self.assertFalse(VocabularyDeck.objects.exists())

    def test_decks_are_private(self):
        deck = VocabularyDeck.objects.create(owner=self.other, title="Not yours")
        word = VocabularyDeckWord.objects.create(deck=deck, word="secret", meaning="hidden")
        for name in ("vocabulary_deck_detail_root", "vocabulary_deck_study_root"):
            self.assertEqual(self.client.get(reverse(name, args=[deck.id])).status_code, 404, name)
        self.client.post(reverse("vocabulary_deck_detail_root", args=[deck.id]), {"action": "delete_deck"})
        self.assertTrue(VocabularyDeck.objects.filter(pk=deck.pk).exists())
        response = self.client.post(reverse("vocabulary_deck_mark_root", args=[deck.id]),
                                    json.dumps({"word_id": word.id, "outcome": "known"}), content_type="application/json")
        self.assertEqual(response.status_code, 404)

    def test_bad_ids_are_404_not_500(self):
        deck = VocabularyDeck.objects.create(owner=self.kid, title="Mine")
        detail = reverse("vocabulary_deck_detail_root", args=[deck.id])
        self.assertEqual(self.client.post(detail, {"action": "delete_word", "word_id": "abc"}).status_code, 404)
        mark = reverse("vocabulary_deck_mark_root", args=[deck.id])
        for body in ({"word_id": "abc", "outcome": "known"}, ["not", "an", "object"]):
            response = self.client.post(mark, json.dumps(body), content_type="application/json")
            self.assertIn(response.status_code, (400, 404), body)
        flash = reverse("vocabulary_flashcard_mark_root")
        for body in ({"word_id": "abc", "outcome": "known"}, ["x"]):
            response = self.client.post(flash, json.dumps(body), content_type="application/json")
            self.assertIn(response.status_code, (400, 404), body)

    # ---------------------------------------------------------------- library -> study -> mastery
    def test_add_library_unit_once_and_master_a_word(self):
        url = reverse("vocabulary_deck_clone_unit_root", args=[self.unit.id])
        first = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["word_count"], 5)  # inactive word is not copied
        again = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertTrue(again.json()["already_added"])
        deck = VocabularyDeck.objects.get(owner=self.kid)

        study = self.client.get(reverse("vocabulary_deck_study_root", args=[deck.id]))
        self.assertEqual(len(study.context["cards"]), 5)
        for mode in ("animated-immersion", "word-bounce", "meaning-match"):
            self.assertEqual(self.client.get(reverse("vocabulary_deck_arena_root", args=[deck.id, mode])).status_code, 200, mode)
        self.assertEqual(self.client.get(reverse("vocabulary_deck_arena_root", args=[deck.id, "nope"])).status_code, 404)

        word = deck.words.get(word="abate")
        mark = reverse("vocabulary_deck_mark_root", args=[deck.id])

        def review(outcome, seen):
            return self.client.post(mark, json.dumps({"word_id": word.id, "outcome": outcome, "expected_times_seen": seen}),
                                    content_type="application/json").json()

        self.assertEqual(review("known", 0)["status"], VocabularyDeckWordProgress.STATUS_LEARNING)
        self.assertTrue(review("known", 0)["duplicate"])  # a network retry is not counted twice
        self.assertEqual(review("known", 1)["status"], VocabularyDeckWordProgress.STATUS_MASTERED)
        self.assertEqual(review("again", 2)["status"], VocabularyDeckWordProgress.STATUS_LEARNING)
        bad = self.client.post(mark, json.dumps({"word_id": word.id, "outcome": "maybe"}), content_type="application/json")
        self.assertEqual(bad.status_code, 400)

    def test_empty_library_unit_cannot_be_added(self):
        empty = VocabularyUnit.objects.create(title="Empty unit", order=9)
        response = self.client.post(reverse("vocabulary_deck_clone_unit_root", args=[empty.id]), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(VocabularyDeck.objects.exists())

    # ---------------------------------------------------------------- official flashcards
    def test_flashcard_reviews_are_tracked(self):
        word = VocabularyWord.objects.get(word="candid")
        url = reverse("vocabulary_flashcard_mark_root")
        response = self.client.post(url, json.dumps({"word_id": word.id, "outcome": "known"}), content_type="application/json")
        self.assertTrue(response.json()["ok"])
        self.assertEqual(VocabularyWordProgress.objects.get(user=self.kid, word=word).correct_count, 1)
        hidden = VocabularyWord.objects.get(word="hidden")
        response = self.client.post(url, json.dumps({"word_id": hidden.id, "outcome": "known"}), content_type="application/json")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get(url).status_code, 405)

    # ---------------------------------------------------------------- practice quiz
    def test_practice_quiz_start_answer_and_score(self):
        start = self.client.post(reverse("vocabulary_practice_quiz_start_root"),
                                 {"units": [self.unit.id], "question_count": 4, "quiz_mode": "word_to_meaning"})
        self.assertEqual(start.status_code, 200)
        questions = self.client.session["vocab_quiz_questions"]
        self.assertEqual(len(questions), 4)
        answers = {f"question_{i}": q["answer"] for i, q in enumerate(questions)}
        answers["question_3"] = "definitely wrong"
        result = self.client.post(reverse("vocabulary_practice_quiz_result_root"), answers)
        self.assertEqual(result.status_code, 200)
        attempt = VocabularyQuizAttempt.objects.get(user=self.kid)
        self.assertEqual((attempt.score, attempt.total_questions, float(attempt.percentage)), (3, 4, 75.0))
        # submitting the same quiz twice (back button) does not create a second attempt
        self.client.post(reverse("vocabulary_practice_quiz_result_root"), answers)
        self.assertEqual(VocabularyQuizAttempt.objects.filter(user=self.kid).count(), 1)

    def test_quiz_rejects_bad_requests(self):
        url = reverse("vocabulary_practice_quiz_start_root")
        self.client.post(url, {"question_count": 4})                                  # no unit
        self.client.post(url, {"units": [self.unit.id], "question_count": 0})         # no questions
        self.client.post(url, {"units": [self.unit.id], "question_count": 50})        # more than words
        self.client.post(url, {"units": ["abc"], "question_count": "x"})              # junk
        self.assertNotIn("vocab_quiz_questions", self.client.session)
        self.assertFalse(VocabularyQuizAttempt.objects.exists())
