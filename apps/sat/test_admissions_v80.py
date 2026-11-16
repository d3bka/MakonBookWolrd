"""V80: the Universities catalogue (all students) and the Admissions course
(full for current SATMakon students, the first 3 lessons for everyone else)."""
import uuid
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.sat.admissions_course import LESSONS
from apps.sat.models import (
    AdmissionsLesson, AdmissionsLessonProgress, AdmissionsResource, AdmissionsStep, Test, TestReview, University,
)
from apps.sat.university_data import UNIVERSITIES, load_universities
from apps.sat.views_admissions import university_fit


class SeedDataTests(TestCase):
    def test_the_migration_loads_the_catalogue_and_the_course(self):
        self.assertGreaterEqual(University.objects.count(), 150)
        self.assertEqual(University.objects.count(), len(UNIVERSITIES))
        self.assertEqual(set(University.objects.values_list("region", flat=True)),
                         {"north_america", "europe", "asia", "middle_east", "oceania"})
        self.assertEqual(AdmissionsLesson.objects.count(), len(LESSONS))
        self.assertFalse(AdmissionsLesson.objects.exclude(youtube_url="").exists())  # videos come from SATMakon
        self.assertTrue(AdmissionsStep.objects.exists())
        self.assertFalse(AdmissionsResource.objects.exclude(url__startswith="https://").exists())

    def test_every_seed_row_is_well_formed(self):
        regions = {key for key, _ in University.REGION_CHOICES}
        for row in UNIVERSITIES:
            name, *_ = row
            self.assertEqual(len(row), 19, name)
            self.assertIn(row[3], regions, name)
            low, high = row[7], row[8]
            if low and high:
                self.assertLessEqual(low, high, name)
                self.assertTrue(400 <= low <= 1600 and 400 <= high <= 1600, name)
            self.assertTrue(row[17].startswith("https://"), name)
        self.assertEqual(len({row[0] for row in UNIVERSITIES}), len(UNIVERSITIES))
        self.assertEqual(University.objects.filter(slug="").count(), 0)

    def test_reloading_keeps_admin_edits_unless_asked(self):
        mit = University.objects.get(name__startswith="Massachusetts Institute")
        mit.tuition_usd = 1
        mit.save()
        self.assertEqual(load_universities(University, update=False), (0, 0))
        mit.refresh_from_db()
        self.assertEqual(mit.tuition_usd, 1)

    def test_the_course_is_written_for_an_11_year_school(self):
        """Schools in Uzbekistan end after grade 11: no grade 12 anywhere in the course."""
        text = " ".join(
            " ".join([lesson["title"], lesson["summary"], *[f"{t} {b}" for t, b in lesson["steps"]]])
            for lesson in LESSONS
        ).lower()
        for wrong in ("grade 12", "9–12", "9-12", "11 or 12", "high school"):
            self.assertNotIn(wrong, text)
        self.assertIn("grade 11: submit", text)
        self.assertIn("ends after grade 11", text)


class FitTests(TestCase):
    def uni(self, **kw):
        values = dict(name="X", country="USA", region="north_america", sat_low=1300, sat_high=1450,
                      sat_kind="middle50", acceptance_rate=Decimal("40"))
        values.update(kw)
        return University(**values)

    def test_reach_match_safety(self):
        self.assertEqual(university_fit(1200, self.uni()), "reach")
        self.assertEqual(university_fit(1350, self.uni()), "match")
        self.assertEqual(university_fit(1500, self.uni()), "safety")

    def test_very_selective_schools_are_always_a_reach(self):
        self.assertEqual(university_fit(1600, self.uni(acceptance_rate=Decimal("4"), sat_low=1500, sat_high=1570)), "reach")
        self.assertEqual(university_fit(1600, self.uni(acceptance_rate=Decimal("15"))), "match")

    def test_no_score_or_no_sat_data(self):
        self.assertEqual(university_fit(None, self.uni()), "")
        self.assertEqual(university_fit(1400, self.uni(sat_kind="none", sat_low=None, sat_high=None)), "")
        self.assertEqual(university_fit(1400, self.uni(sat_kind="none", sat_low=None, acceptance_rate=Decimal("12"))), "reach")


class UniversitiesPageTests(TestCase):
    def setUp(self):
        self.kid = User.objects.create_user("v80_kid", password="x")
        self.client.force_login(self.kid)

    def test_any_student_sees_the_catalogue_with_data_for_the_search(self):
        page = self.client.get(reverse("universities_root"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'id="mk80-uni-data"')
        self.assertContains(page, "data-uni-search")
        self.assertContains(page, 'data-nav-key="universities"')
        rows = page.context["uni_rows"]
        self.assertEqual(len(rows), University.objects.filter(is_active=True).count())
        self.assertIn("Harvard University", {row["n"] for row in rows})

    def test_hidden_universities_are_left_out(self):
        University.objects.filter(name="Harvard University").update(is_active=False)
        names = {row["n"] for row in self.client.get(reverse("universities_root")).context["uni_rows"]}
        self.assertNotIn("Harvard University", names)
        harvard = University.objects.get(name="Harvard University")
        self.assertEqual(self.client.get(reverse("university_detail_root", args=[harvard.slug])).status_code, 404)

    def test_detail_page_uses_the_best_practice_score(self):
        test = Test.objects.create(name="DAY1", is_available=True)
        TestReview.objects.create(test=test, user=self.kid, key="v80-a", attempt_id=uuid.uuid4(), score=1380)
        TestReview.objects.create(test=test, user=self.kid, key="v80-b", attempt_id=uuid.uuid4(), score=1450)
        uni = University.objects.get(name="Purdue University")
        page = self.client.get(reverse("university_detail_root", args=[uni.slug]))
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.context["uni_score"], 1450)
        self.assertEqual(page.context["uni_fit"], "safety")
        self.assertContains(page, uni.website)
        self.assertContains(page, "You · 1450")

    def test_staff_go_to_their_own_dashboard(self):
        teacher = User.objects.create_user("v80_teacher", password="x")
        teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        self.client.force_login(teacher)
        self.assertEqual(self.client.get(reverse("universities_root")).status_code, 302)

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("universities_root")).status_code, 302)


class AdmissionsCourseTests(TestCase):
    def setUp(self):
        self.kid = User.objects.create_user("v80_adm", password="x")
        self.client.force_login(self.kid)
        self.lessons = list(AdmissionsLesson.objects.order_by("order", "id"))

    def make_current_student(self):
        self.kid.profile.hollihop_client_id = 880001
        self.kid.profile.hollihop_status = "Занимается"
        self.kid.profile.save()

    def lesson_url(self, lesson):
        return reverse("admissions_section_root", args=[lesson.slug])

    def test_others_get_the_first_three_lessons(self):
        page = self.client.get(reverse("admissions_root"))
        self.assertEqual(page.status_code, 200)
        self.assertFalse(page.context["adm_full_access"])
        self.assertEqual(page.context["adm_locked_count"], len(self.lessons) - 3)
        self.assertContains(page, "available only to current SATMakon students")
        for lesson in self.lessons[:3]:
            response = self.client.get(self.lesson_url(lesson))
            self.assertFalse(response.context["lesson"].is_locked)
            self.assertTrue(response.context["lesson_steps"])
        locked = self.client.get(self.lesson_url(self.lessons[3]))
        self.assertEqual(locked.status_code, 200)
        self.assertTrue(locked.context["lesson"].is_locked)
        self.assertEqual(locked.context["lesson_steps"], [])
        self.assertEqual(locked.context["lesson_resources"], [])
        self.assertContains(locked, "Available only to current SATMakon students")
        self.assertNotContains(locked, self.lessons[3].steps.first().title)

    def test_current_satmakon_students_get_everything(self):
        self.make_current_student()
        page = self.client.get(reverse("admissions_root"))
        self.assertTrue(page.context["adm_full_access"])
        self.assertEqual(page.context["adm_locked_count"], 0)
        last = self.client.get(self.lesson_url(self.lessons[-1]))
        self.assertFalse(last.context["lesson"].is_locked)
        self.assertTrue(last.context["lesson_resources"])

    def test_a_student_who_left_loses_the_full_course(self):
        self.kid.profile.hollihop_client_id = 880001
        self.kid.profile.hollihop_status = "Закончил обучение"
        self.kid.profile.save()
        self.assertFalse(self.client.get(reverse("admissions_root")).context["adm_full_access"])

    @override_settings(MAKONBOOK_FREE_ADMISSIONS_LESSONS=5)
    def test_the_free_lesson_count_is_a_setting(self):
        self.assertEqual(self.client.get(reverse("admissions_root")).context["adm_locked_count"], len(self.lessons) - 5)

    def test_mark_complete_and_undo(self):
        lesson = self.lessons[0]
        url = reverse("admissions_lesson_complete_root", args=[lesson.slug])
        self.assertRedirects(self.client.post(url, {"done": "1"}), self.lesson_url(lesson))
        self.assertTrue(AdmissionsLessonProgress.objects.filter(user=self.kid, lesson=lesson).exists())
        home = self.client.get(reverse("admissions_root"))
        self.assertEqual(home.context["adm_done"], 1)
        self.assertEqual(home.context["adm_next"], self.lessons[1])
        data = self.client.post(url, {"done": "0"}, HTTP_ACCEPT="application/json").json()
        self.assertEqual((data["ok"], data["done"], data["completed"]), (True, False, 0))
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_a_locked_lesson_cannot_be_completed(self):
        url = reverse("admissions_lesson_complete_root", args=[self.lessons[5].slug])
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertFalse(AdmissionsLessonProgress.objects.filter(user=self.kid).exists())

    def test_youtube_links_become_privacy_embeds(self):
        lesson = self.lessons[0]
        for link in ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10", "https://youtu.be/dQw4w9WgXcQ",
                     "https://www.youtube.com/shorts/dQw4w9WgXcQ"):
            lesson.youtube_url = link
            self.assertEqual(lesson.youtube_embed_url, "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ")
        lesson.youtube_url = "https://example.com/video"
        self.assertEqual(lesson.youtube_embed_url, "")
        lesson.youtube_url = "https://youtu.be/dQw4w9WgXcQ"
        lesson.save()
        page = self.client.get(self.lesson_url(lesson))
        self.assertContains(page, "youtube-nocookie.com/embed/dQw4w9WgXcQ")
        self.assertNotContains(self.client.get(self.lesson_url(self.lessons[1])), "<iframe")

    def test_old_section_links_and_unknown_lessons(self):
        self.assertRedirects(self.client.get("/admissions/university_guide/"), reverse("admissions_root"),
                             fetch_redirect_response=False)
        self.assertEqual(self.client.get("/admissions/no-such-lesson/").status_code, 404)
        AdmissionsLesson.objects.filter(pk=self.lessons[0].pk).update(is_published=False)
        self.assertEqual(self.client.get(self.lesson_url(self.lessons[0])).status_code, 404)

    def test_admissions_is_visible_in_the_sidebar(self):
        page = self.client.get(reverse("admissions_root"))
        self.assertRegex(page.content.decode(), r'<a(?=[^>]*data-nav-key="admissions")(?![^>]*\shidden)[^>]*>')

    def test_staff_go_to_their_own_dashboard(self):
        teacher = User.objects.create_user("v80_adm_teacher", password="x")
        teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        self.client.force_login(teacher)
        self.assertEqual(self.client.get(reverse("admissions_root")).status_code, 302)
        url = reverse("admissions_lesson_complete_root", args=[self.lessons[0].slug])
        self.assertEqual(self.client.post(url).status_code, 403)
