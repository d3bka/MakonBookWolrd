"""V73 A-to-Z: the developer panel and the remaining small pages (errors, software, guest logout)."""
from django.contrib.auth.models import Group, User
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.sat.models import English_Question, Math_Question, SecretCode, Test, TestReview


class DevPanelTests(TestCase):
    def setUp(self):
        self.dev = User.objects.create_user("dv_dev", password="x")
        self.dev.groups.add(Group.objects.get_or_create(name="dev")[0])
        self.test = Test.objects.create(name="DV-DAY1")
        self.math = Math_Question.objects.create(test=self.test, module="1", number=1, question="2+2", a="4", b="5",
                                                 c="6", d="7", answer="A", written=False)
        Math_Question.objects.create(test=self.test, module="1", number=2, question="3+3", a="6", b="5", c="4", d="3",
                                     answer="A", written=False)
        self.english = English_Question.objects.create(test=self.test, module="1", number=1, question="Pick one", a="x",
                                                       b="y", c="z", d="w", answer="A", response_type="multiple_choice")
        self.client.force_login(self.dev)

    def test_pages_open_for_dev_only(self):
        pages = [reverse("dev_dashboard"), reverse("dev_search_questions") + "?query=2%2B2&section=math",
                 reverse("dev_manage_groups"), reverse("dev_create_bulk_users"), reverse("dev_assign_test"),
                 reverse("dev_test_statistics"), reverse("dev_question_detail", args=["math", self.math.pk]),
                 reverse("dev_question_detail", args=["english", self.english.pk])]
        for url in pages:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(self.client.get(reverse("dev_question_detail", args=["physics", 1])).status_code, 404)
        admin = User.objects.create_user("dv_admin", password="x")
        admin.groups.add(Group.objects.get_or_create(name="Admin")[0])
        for who in (User.objects.create_user("dv_kid", password="x"), admin):
            self.client.force_login(who)
            for url in pages:
                self.assertNotEqual(self.client.get(url).status_code, 200, (who.username, url))

    def test_question_detail_has_prev_next(self):
        response = self.client.get(reverse("dev_question_detail", args=["math", self.math.pk]))
        self.assertIsNone(response.context["prev_pk"])
        self.assertIsNotNone(response.context["next_pk"])

    def test_bulk_users_never_go_into_a_role_group(self):
        admin_group = Group.objects.get_or_create(name="Admin")[0]
        response = self.client.post(reverse("dev_create_bulk_users"), {
            "group": admin_group.pk, "username_prefix": "evil", "count": 2, "password_length": 10,
        })
        self.assertFalse(User.objects.filter(username__startswith="evil").exists())
        self.assertEqual(response.status_code, 200)  # form error, no credentials file
        cohort = Group.objects.create(name="Cohort A")
        response = self.client.post(reverse("dev_create_bulk_users"), {
            "group": cohort.pk, "username_prefix": "kid", "count": 2, "password_length": 10,
        })
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(cohort.user_set.count(), 2)

    def test_assign_test_with_secret_code_and_statistics(self):
        cohort = Group.objects.create(name="Cohort B")
        self.client.post(reverse("dev_assign_test"), {"group": cohort.pk, "test": self.test.pk, "create_secret_code": "on"})
        self.assertIn(cohort, self.test.groups.all())
        self.assertTrue(SecretCode.objects.filter(group=cohort, test=self.test).exists())
        for i, score in enumerate((1200, 1350, 1500)):
            TestReview.objects.create(user=User.objects.create_user(f"dv_s{i}", password="x"), test=self.test,
                                      key=f"dv-{i}", score=score)
        response = self.client.post(reverse("dev_test_statistics"), {"test": self.test.pk})
        self.assertEqual(response.status_code, 200)
        self.client.post(reverse("dev_manage_groups"), {"name": "Cohort C"})
        self.assertTrue(Group.objects.filter(name="Cohort C").exists())


class SmallPagesTests(TestCase):
    def test_software_page_and_old_public_rating_link(self):
        self.assertIn(self.client.get(reverse("software")).status_code, (200, 302))
        self.assertEqual(self.client.get(reverse("rating_public_student", args=[1])).status_code, 302)

    def test_guest_logout(self):
        session = self.client.session
        session["guest_mode"] = True
        session["guest_id"] = "abc"
        session.save()
        self.client.get(reverse("guest_logout"))
        self.assertNotIn("guest_id", self.client.session)
        user = User.objects.create_user("dv_guest_user", password="x")
        self.client.force_login(user)
        session = self.client.session
        session["guest_id"] = "abc"
        session.save()
        self.assertRedirects(self.client.get(reverse("guest_logout")), reverse("events"), fetch_redirect_response=False)
        self.assertNotIn("guest_id", self.client.session)
        self.assertIn("_auth_user_id", self.client.session)  # still signed in

    def test_error_handlers_render(self):
        from apps.base import error_views

        factory = RequestFactory()
        request = factory.get("/broken/")
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()
        self.assertEqual(error_views.bad_request(request, Exception("bad")).status_code, 400)
        self.assertEqual(error_views.server_error(request).status_code, 500)

    @override_settings(DEBUG=False)
    def test_unknown_url_is_a_friendly_404(self):
        response = self.client.get("/definitely/not/a/page/")
        self.assertEqual(response.status_code, 404)


class LegacyEndpointsTests(TestCase):
    def test_clear_page_escapes_its_url_parts(self):
        response = self.client.get('/sat/clear/DAY1/english/m1%22%3Balert(1)%3B%22/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'm1";alert(1);"', response.content)  # escapejs keeps it inside the JS string

    def test_punishment_is_recorded_by_post_only(self):
        from apps.sat.models import Punishment

        user = User.objects.create_user("dv_cheat", password="x")
        self.client.force_login(user)
        self.assertEqual(self.client.get("/sat/punishment/DAY1").status_code, 405)
        self.assertEqual(self.client.post("/sat/punishment/DAY1").status_code, 200)
        self.assertEqual(Punishment.objects.get().user, user)
