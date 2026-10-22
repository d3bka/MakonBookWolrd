from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import RatingProfile


class ParentLanguageV334Tests(TestCase):
    def setUp(self):
        self.url = reverse("rating_parent_lookup")

    def test_russian_language_can_be_selected_and_persists(self):
        response = self.client.get(self.url, {"lang": "ru"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Доступ для родителей")
        self.assertContains(response, "Зарегистрированный номер телефона")
        self.assertEqual(self.client.session["rating_parent_language"], "ru")

        response = self.client.get(self.url)
        self.assertContains(response, "Открыть статистику")

    def test_uzbek_language_can_be_selected(self):
        response = self.client.get(self.url, {"lang": "uz"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ota-onalar uchun kirish")
        self.assertContains(response, "Ro‘yxatdan o‘tgan telefon raqami")
        self.assertContains(response, "Statistikani ochish")
        self.assertContains(response, "O‘quvchining ro‘yxatdan o‘tgan telefon raqamidan foydalaning")
        self.assertContains(response, "Yordam: ")
        self.assertNotContains(response, "Use the student's registered phone number")

    def test_browser_language_is_used_on_first_visit(self):
        response = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE="ru-RU,ru;q=0.9,en;q=0.8")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Доступ для родителей")

    def test_invalid_phone_message_is_localized(self):
        response = self.client.post(
            self.url,
            {"lang": "ru", "action": "lookup", "phone_number": "+998 90 999 99 99"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Номер телефона не найден")

    def test_valid_phone_keeps_translated_result_labels(self):
        user = User.objects.create_user(username="student_lang_test", password="x")
        user.profile.hollihop_client_id = 334
        user.profile.phone_number = "+998901112233"
        user.profile.save(update_fields=["hollihop_client_id", "phone_number"])
        RatingProfile.objects.get_or_create(user=user)

        response = self.client.post(
            self.url,
            {"lang": "uz", "action": "lookup", "phone_number": "+998901112233"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "student_lang_test")
        self.assertContains(response, "Baholashlar")
        self.assertContains(response, "Sinflar")
