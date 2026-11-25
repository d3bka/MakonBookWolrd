"""V93: SAT practice-test attempt limits and extra attempts from teachers."""
import uuid
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.sat import attempt_limits
from apps.sat.attempt_limit_models import SatAttemptRequest, SatAttemptUse
from apps.sat.models import (
    Classroom, ClassroomMembership, English_Question, MakonNotification, Test, TestReview, TestStage,
)


@override_settings(SAT_ATTEMPTS_SATMAKON_STUDENT=5, SAT_ATTEMPTS_PUBLIC=3)
@patch("apps.sat.views.user_has_test_access", lambda user, test: True)
class AttemptLimitTests(TestCase):
    def setUp(self):
        self.test = Test.objects.create(name="DAY93", is_available=True)
        English_Question.objects.create(test=self.test, module="module_1", number=1, question="Q", answer="A")
        teachers = Group.objects.get_or_create(name="Teacher")[0]
        self.teacher = User.objects.create_user("v93_teacher", first_name="Malika", password="x")
        self.teacher.groups.add(teachers)
        self.other_teacher = User.objects.create_user("v93_other", password="x")
        self.other_teacher.groups.add(teachers)
        self.public = User.objects.create_user("v93_public", password="x")
        self.student = User.objects.create_user("v93_student", first_name="Aziz", password="x")
        self.student.profile.hollihop_client_id = 777          # V113: a current student = "Занимается" in Hollihop
        self.student.profile.hollihop_status = "Занимается"
        self.student.profile.save()
        self.classroom = Classroom.objects.create(name="SAT 93", teacher=self.teacher, hollihop_managed=True)
        ClassroomMembership.objects.create(classroom=self.classroom, user=self.student, role="student", status="approved")

    # helpers -------------------------------------------------------------
    def use_up(self, user, count):
        for _ in range(count):
            SatAttemptUse.objects.create(user=user, test=self.test, attempt_id=uuid.uuid4())

    def finish_open_attempts(self, user):
        for stage in TestStage.objects.filter(user=user, test=self.test):
            stage.stage = 5
            stage.save(update_fields=["stage"])
            TestReview.objects.get_or_create(user=user, test=self.test, test_type="regular", attempt_id=stage.attempt_id,
                                             defaults={"score": 400, "key": f"r-{stage.attempt_id}"})

    def retake(self, user):
        self.client.force_login(user)
        return self.client.post(reverse("practice_test_restart_root", args=[self.test.name]), {"confirm_start": "1"})

    # limits by role ------------------------------------------------------
    def test_limits_by_role(self):
        self.assertIsNone(attempt_limits.base_limit(self.teacher))
        self.assertEqual(attempt_limits.base_limit(self.student), 5)
        self.assertEqual(attempt_limits.base_limit(self.public), 3)
        manager = User.objects.create_user("v93_manager", password="x")
        manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.assertIsNone(attempt_limits.base_limit(manager))

    def test_public_student_gets_three_full_retakes_then_the_limit_page(self):
        limit_url = reverse("practice_test_attempts_root", args=[self.test.name])
        for _ in range(3):
            response = self.retake(self.public)
            self.assertNotEqual(response.url, limit_url)
            self.finish_open_attempts(self.public)
        self.assertEqual(SatAttemptUse.objects.filter(user=self.public).count(), 3)
        stages = TestStage.objects.filter(user=self.public).count()
        response = self.retake(self.public)
        self.assertRedirects(response, limit_url, fetch_redirect_response=False)
        self.assertEqual(TestStage.objects.filter(user=self.public).count(), stages)

    def test_first_start_counts_and_an_exhausted_start_goes_to_the_limit_page(self):
        self.client.force_login(self.public)
        self.client.get(reverse("practice_test_module_root", args=[self.test.name]))
        use = SatAttemptUse.objects.get(user=self.public)
        self.assertEqual(use.source, SatAttemptUse.SOURCE_START)
        self.finish_open_attempts(self.public)
        self.use_up(self.public, 2)
        response = self.client.get(reverse("practice_test_module_root", args=[self.test.name]))
        self.assertRedirects(response, reverse("practice_test_attempts_root", args=[self.test.name]),
                             fetch_redirect_response=False)

    def test_section_retake_counts(self):
        self.client.force_login(self.public)
        self.client.get(reverse("practice_test_module_root", args=[self.test.name]))
        self.finish_open_attempts(self.public)
        self.client.post(reverse("practice_test_restart_section_root", args=[self.test.name, "english"]),
                         {"confirm_start": "1"})
        self.assertEqual(SatAttemptUse.objects.filter(user=self.public, source=SatAttemptUse.SOURCE_SECTION).count(), 1)

    def test_an_abandoned_attempt_without_answers_is_given_back(self):
        from apps.sat.views import _discard_abandoned_stage

        self.client.force_login(self.public)
        self.client.get(reverse("practice_test_module_root", args=[self.test.name]))
        stage = TestStage.objects.get(user=self.public)
        request = self.client.get("/").wsgi_request
        _discard_abandoned_stage(request, stage)
        self.assertFalse(SatAttemptUse.objects.filter(user=self.public).exists())

    def test_teachers_are_unlimited_and_not_counted(self):
        for _ in range(6):
            self.retake(self.teacher)
            self.finish_open_attempts(self.teacher)
        self.assertEqual(TestStage.objects.filter(user=self.teacher).count(), 6)
        self.assertFalse(SatAttemptUse.objects.filter(user=self.teacher).exists())

    def test_overview_shows_attempts_left_and_sends_an_exhausted_student_to_the_limit_page(self):
        self.client.force_login(self.public)
        self.use_up(self.public, 2)
        page = self.client.get(reverse("practice_test_start_root", args=[self.test.name]) + "?retake=full")
        self.assertContains(page, "1 of 3")
        self.assertContains(page, "this is your last one")
        self.use_up(self.public, 1)
        page = self.client.get(reverse("practice_test_start_root", args=[self.test.name]) + "?retake=full")
        self.assertRedirects(page, reverse("practice_test_attempts_root", args=[self.test.name]),
                             fetch_redirect_response=False)

    # the limit page -------------------------------------------------------
    def test_public_student_is_invited_to_satmakon_and_cannot_ask(self):
        self.use_up(self.public, 3)
        self.client.force_login(self.public)
        page = self.client.get(reverse("practice_test_attempts_root", args=[self.test.name]))
        self.assertContains(page, "You have used all 3 attempts")
        self.assertContains(page, "SATMakon students get 5 attempts")
        self.assertNotContains(page, "Ask for more attempts")
        self.client.post(reverse("practice_test_attempts_root", args=[self.test.name]), {"message": "please"})
        self.assertFalse(SatAttemptRequest.objects.exists())

    def test_limit_page_redirects_while_attempts_remain(self):
        self.client.force_login(self.student)
        page = self.client.get(reverse("practice_test_attempts_root", args=[self.test.name]))
        self.assertRedirects(page, reverse("practice_test_start_root", args=[self.test.name]),
                             fetch_redirect_response=False)

    def ask(self, message="Internet died"):
        self.use_up(self.student, 5)
        self.client.force_login(self.student)
        return self.client.post(reverse("practice_test_attempts_root", args=[self.test.name]), {"message": message},
                                follow=True)

    def test_satmakon_student_asks_and_the_teacher_is_notified(self):
        response = self.ask()
        self.assertContains(response, "Waiting for your teacher")
        row = SatAttemptRequest.objects.get()
        self.assertEqual((row.user, row.status, row.message), (self.student, "pending", "Internet died"))
        note = MakonNotification.objects.get(user=self.teacher)
        self.assertEqual(note.type, MakonNotification.TYPE_ATTEMPTS)
        self.assertIn("DAY93", note.title)
        self.assertIn("Internet died", note.message)
        self.assertFalse(MakonNotification.objects.filter(user=self.other_teacher).exists())
        # Only one waiting request at a time.
        self.client.post(reverse("practice_test_attempts_root", args=[self.test.name]), {"message": "again"})
        self.assertEqual(SatAttemptRequest.objects.count(), 1)

    def test_teacher_gives_two_more_attempts(self):
        self.ask()
        self.client.force_login(self.teacher)
        page = self.client.get(reverse("teacher_attempt_requests_root"))
        self.assertContains(page, "Aziz")
        self.assertContains(page, "5 of 5 used")
        self.assertEqual(page.context["attempt_requests_waiting"](), 1)
        self.client.post(reverse("teacher_attempt_requests_root"),
                         {"request_id": SatAttemptRequest.objects.get().pk, "decision": "approve", "granted": "2",
                          "note": "Good luck"})
        row = SatAttemptRequest.objects.get()
        self.assertEqual((row.status, row.granted, row.decided_by), ("approved", 2, self.teacher))
        info = attempt_limits.state(self.student, self.test)
        self.assertEqual((info["total"], info["remaining"], info["exhausted"]), (7, 2, False))
        note = MakonNotification.objects.get(user=self.student)
        self.assertIn("+2 attempts", note.title)
        self.assertEqual(note.message, "Good luck")
        self.assertTrue(attempt_limits.can_start(self.student, self.test))

    def test_grant_is_capped_at_three(self):
        self.ask()
        row = attempt_limits.decide(self.teacher, SatAttemptRequest.objects.get(), approve=True, granted=50)
        self.assertEqual(row.granted, 3)

    def test_rejection_notifies_and_keeps_the_limit(self):
        self.ask()
        attempt_limits.decide(self.teacher, SatAttemptRequest.objects.get(), approve=False, note="Study first")
        self.assertIn("rejected", MakonNotification.objects.get(user=self.student).title)
        self.assertFalse(attempt_limits.can_start(self.student, self.test))
        self.client.force_login(self.student)
        page = self.client.get(reverse("practice_test_attempts_root", args=[self.test.name]))
        self.assertContains(page, "Study first")
        self.assertContains(page, "Ask for more attempts")  # may ask again

    def test_other_teachers_and_students_cannot_decide(self):
        self.ask()
        row = SatAttemptRequest.objects.get()
        with self.assertRaises(attempt_limits.LimitError):
            attempt_limits.decide(self.other_teacher, row, approve=True)
        self.client.force_login(self.other_teacher)
        self.assertNotContains(self.client.get(reverse("teacher_attempt_requests_root")), "Aziz")
        self.client.force_login(self.public)
        self.assertEqual(self.client.get(reverse("teacher_attempt_requests_root")).status_code, 403)
        row.refresh_from_db()
        self.assertEqual(row.status, "pending")

    def test_student_can_withdraw(self):
        self.ask()
        row = SatAttemptRequest.objects.get()
        self.client.post(reverse("practice_test_attempt_request_withdraw_root", args=[row.pk]))
        row.refresh_from_db()
        self.assertEqual(row.status, "withdrawn")

    def test_student_without_a_class_teacher_is_told_so(self):
        ClassroomMembership.objects.filter(user=self.student).delete()
        self.student.profile.hollihop_client_id = 777
        self.student.profile.hollihop_status = "Active"
        self.student.profile.save()
        self.use_up(self.student, 5)
        self.client.force_login(self.student)
        page = self.client.get(reverse("practice_test_attempts_root", args=[self.test.name]))
        self.assertContains(page, "not in a class with a teacher yet")
