from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.ratings.models import RatingProfile


class ParentPortalV5595Tests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username="parent_portal_student",
            first_name="Student",
            last_name="Example",
            password="x",
        )
        self.student.profile.hollihop_client_id = 3908
        self.student.profile.phone_number = "+998901234567"
        self.student.profile.save(update_fields=["hollihop_client_id", "phone_number"])
        RatingProfile.objects.get_or_create(user=self.student)
        self.url = reverse("rating_parent_lookup")

    def test_registered_phone_opens_student_and_is_remembered(self):
        response = self.client.post(
            self.url,
            {"action": "lookup", "phone_number": "+998 90 123 45 67", "lang": "en"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get("rating_parent_student_user_id"), self.student.pk)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Student Example")
        self.assertContains(response, "+998901234567")
        self.assertNotContains(response, "parent_access_code")

    def test_local_phone_format_is_accepted(self):
        response = self.client.post(
            self.url,
            {"action": "lookup", "phone_number": "90 123 45 67"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get("rating_parent_student_user_id"), self.student.pk)

    def test_switch_student_clears_remembered_session(self):
        session = self.client.session
        session["rating_parent_student_user_id"] = self.student.pk
        session.save()
        response = self.client.post(self.url, {"action": "switch", "lang": "en"})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("rating_parent_student_user_id", self.client.session)

    def test_unknown_phone_does_not_open_profile(self):
        response = self.client.post(
            self.url,
            {"action": "lookup", "phone_number": "+998 90 999 99 99"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("rating_parent_student_user_id", self.client.session)
        self.assertContains(response, "Phone number not found")


    def test_shared_phone_shows_student_chooser_and_allows_selection(self):
        sibling = User.objects.create_user(
            username="parent_portal_sibling",
            first_name="Sibling",
            last_name="Example",
            password="x",
        )
        sibling.profile.phone_number = "+998901234567"
        sibling.profile.save(update_fields=["phone_number"])
        RatingProfile.objects.get_or_create(user=sibling)

        response = self.client.post(
            self.url,
            {"action": "lookup", "phone_number": "+998 90 123 45 67", "lang": "en"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("rating_parent_student_user_id", self.client.session)
        self.assertContains(response, "Choose a student")
        self.assertContains(response, "Student Example")
        self.assertContains(response, "Sibling Example")

        response = self.client.post(
            self.url,
            {"action": "select", "student_user_id": sibling.pk, "lang": "en"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get("rating_parent_student_user_id"), sibling.pk)

    def test_switch_from_shared_phone_returns_to_sibling_chooser(self):
        sibling = User.objects.create_user(username="family_sibling", first_name="Second", password="x")
        sibling.profile.phone_number = "+998901234567"
        sibling.profile.save(update_fields=["phone_number"])
        RatingProfile.objects.get_or_create(user=sibling)

        self.client.post(self.url, {"action": "lookup", "phone_number": "+998901234567"})
        self.client.post(self.url, {"action": "select", "student_user_id": self.student.pk})
        response = self.client.post(self.url, {"action": "switch", "lang": "en"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose a student")
        self.assertContains(response, "Second")

    def test_lookup_is_rate_limited(self):
        for _ in range(10):
            response = self.client.post(self.url, {"action": "lookup", "phone_number": "+998 90 999 99 99"})
            self.assertEqual(response.status_code, 200)
        response = self.client.post(self.url, {"action": "lookup", "phone_number": "+998 90 999 99 99"})
        self.assertEqual(response.status_code, 429)
