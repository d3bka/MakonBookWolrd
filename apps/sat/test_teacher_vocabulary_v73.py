"""V73 A-to-Z: teacher vocabulary management (units, words, questions, bulk import)."""
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from apps.sat.models import VocabularyQuestion, VocabularyUnit, VocabularyWord


class TeacherVocabularyTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("tv_teacher", password="x")
        self.teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        self.unit = VocabularyUnit.objects.create(title="Core 1", order=1)
        self.client.force_login(self.teacher)

    def test_pages_open_for_teachers_only(self):
        pages = [reverse("teacher_vocabulary_units"), reverse("create_vocabulary_unit"),
                 reverse("teacher_vocabulary_unit_detail", args=[self.unit.pk]),
                 reverse("create_vocabulary_word", args=[self.unit.pk]),
                 reverse("create_vocabulary_question", args=[self.unit.pk]), reverse("bulk_import_vocabulary_words")]
        for url in pages:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.client.force_login(User.objects.create_user("tv_kid", password="x"))
        for url in pages:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.client.post(reverse("create_vocabulary_word", args=[self.unit.pk]), {"word": "x", "meaning": "y"})
        self.assertFalse(VocabularyWord.objects.exists())

    def test_create_unit_validates_title_and_order(self):
        url = reverse("create_vocabulary_unit")
        self.client.post(url, {"title": "", "order": "5"})
        self.client.post(url, {"title": "Dup order", "order": "1"})
        self.client.post(url, {"title": "Bad order", "order": "first"})
        self.assertEqual(VocabularyUnit.objects.count(), 1)
        response = self.client.post(url, {"title": "Core 2", "order": "2", "description": "next"})
        unit = VocabularyUnit.objects.get(title="Core 2")
        self.assertRedirects(response, reverse("teacher_vocabulary_unit_detail", args=[unit.pk]), fetch_redirect_response=False)

    def test_add_word_and_question(self):
        self.client.post(reverse("create_vocabulary_word", args=[self.unit.pk]), {"word": "", "meaning": "m"})
        self.client.post(reverse("create_vocabulary_word", args=[self.unit.pk]), {"word": "w", "meaning": ""})
        self.client.post(reverse("create_vocabulary_word", args=[self.unit.pk]), {"word": "lucid", "meaning": "clear"})
        self.assertEqual(list(VocabularyWord.objects.values_list("word", flat=True)), ["lucid"])
        url = reverse("create_vocabulary_question", args=[self.unit.pk])
        full = {"question_rich": "Lucid means?", "option_a_rich": "clear", "option_b_rich": "dark",
                "option_c_rich": "loud", "option_d_rich": "slow"}
        self.client.post(url, {**full, "correct_answer": "E"})
        self.client.post(url, {**full, "option_d_rich": "", "correct_answer": "A"})
        self.assertFalse(VocabularyQuestion.objects.exists())
        self.client.post(url, {**full, "correct_answer": "a"})
        question = VocabularyQuestion.objects.get()
        self.assertEqual((question.correct_answer, question.choice_b), ("A", "dark"))
        detail = self.client.get(reverse("teacher_vocabulary_unit_detail", args=[self.unit.pk]))
        self.assertContains(detail, "B. dark")

    def test_bulk_import_parses_skips_duplicates_and_fills_units(self):
        VocabularyWord.objects.create(unit=self.unit, word="Abate", meaning="lessen")
        raw = "1. abate — to lessen\n2. candid - frank\nand honest\n3. no separator here\n4. candid — again"
        self.client.post(reverse("bulk_import_vocabulary_words"), {"raw_text": raw})
        self.assertTrue(VocabularyWord.objects.filter(word="candid", meaning="frank and honest").exists())
        self.assertEqual(VocabularyWord.objects.filter(word__iexact="abate").count(), 1)
        self.assertEqual(VocabularyWord.objects.filter(word="candid").count(), 1)
        page = self.client.get(reverse("bulk_import_vocabulary_words"))
        self.assertIn("3. no separator here", page.context["bad_lines"])

    def test_bulk_import_survives_a_unit_title_that_is_already_taken(self):
        # "Unit 3" exists but sits at order 7: creating the missing order-3 unit must not crash
        VocabularyUnit.objects.create(title="Unit 3", order=7)
        response = self.client.post(reverse("bulk_import_vocabulary_words"), {"raw_text": "1. zeal — energy"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(VocabularyWord.objects.filter(word="zeal").exists())
        self.assertEqual(VocabularyUnit.objects.filter(order=3).count(), 1)
