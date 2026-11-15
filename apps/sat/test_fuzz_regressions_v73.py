"""V73 A-to-Z fuzz: junk ids, JSON lists and odd `next` values must never be a 500."""
import json
import uuid
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import (
    Classroom, SupportLessonBooking, SupportLessonTitle, SupportLessonTopic, SupportTeacherProfile, VocabularyUnit,
)


def member_of(user, *names):
    for name in names:
        user.groups.add(Group.objects.get_or_create(name=name)[0])
    return user


class JsonBodyMustBeAnObjectTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user("fz_kid", password="x"))

    def post_json(self, url, body):
        return self.client.post(url, json.dumps(body), content_type="application/json")

    def test_answer_endpoints_reject_a_json_list(self):
        for url in (
            reverse("save_test_module_draft"),
            reverse("student_topic_check_root"),
            reverse("save_global_event_answer_root", args=[uuid.uuid4()]),
        ):
            for body in ([], ["section", "math"], "just a string"):
                response = self.post_json(url, body)
                self.assertEqual(response.status_code, 400, (url, body))


class JunkIdsAre404Tests(TestCase):
    def setUp(self):
        self.teacher = member_of(User.objects.create_user("fz_teacher", password="x"), "Teacher")
        self.classroom = Classroom.objects.create(teacher=self.teacher, name="FZ class")
        self.admin = member_of(User.objects.create_user("fz_admin", password="x"), "Admin")

    def test_teacher_homework_with_a_junk_assignment_id(self):
        self.client.force_login(self.teacher)
        url = reverse("teacher_classroom_homework_root", args=[self.classroom.pk])
        for action in ("delete", "edit"):
            self.assertEqual(self.client.post(url, {"action": action, "assignment_id": "zz-nope"}).status_code, 404, action)

    def test_support_admin_screens_with_a_junk_teacher_id(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("support_teacher_planner_root"), {"teacher": "zz-nope"}).status_code, 404)
        response = self.client.post(reverse("schedule_support_topic_session_root"), {"teacher_id": "zz-nope"})
        self.assertEqual(response.status_code, 404)

    def test_manager_schedule_with_junk_ids(self):
        manager = member_of(User.objects.create_user("fz_manager", password="x"), "Manager")
        self.client.force_login(manager)
        response = self.client.post(reverse("manager_save_assessment_schedule"), {"classroom_id": "zz", "teacher_id": "-1"})
        self.assertEqual(response.status_code, 404)

    def test_vocabulary_unit_order_must_fit_the_column(self):
        self.client.force_login(self.teacher)
        for order in ("-1", "99999999999"):
            response = self.client.post(reverse("teacher_vocabulary_create_unit_root"), {"title": f"Unit {order}", "order": order})
            self.assertEqual(response.status_code, 302, order)
        self.assertFalse(VocabularyUnit.objects.exists())


class RedirectTargetsTests(TestCase):
    def test_rating_save_with_a_junk_next_student(self):
        from apps.ratings.models import AssessmentSchedule, RatingAssessment
        from apps.sat.models import ClassroomMembership

        teacher = member_of(User.objects.create_user("fz_rt", password="x"), "Teacher")
        classroom = Classroom.objects.create(teacher=teacher, name="FZ rating")
        kid = User.objects.create_user("fz_rk", password="x")
        ClassroomMembership.objects.create(classroom=classroom, user=kid, role="student", status="approved",
                                           approved_at=timezone.now())
        AssessmentSchedule.objects.create(classroom=classroom, teacher=teacher,
                                          weekdays=[timezone.localdate().isoweekday()])
        self.client.force_login(teacher)
        scores = {"homework": 8, "progress": 7, "activity": 9, "attendance": 10, "behavior": 9, "comment": "ok"}
        response = self.client.post(reverse("rating_assess_student", args=[classroom.pk, kid.pk]),
                                    {**scores, "next_student_id": "zz-nope"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("rating_teacher_classroom", args=[classroom.pk]))
        self.assertTrue(RatingAssessment.objects.filter(student=kid).exists())

    def test_goal_modal_next_must_be_a_site_path(self):
        from django.test import RequestFactory

        from apps.sat.views import _student_goal_redirect_url

        factory = RequestFactory()
        for junk in ("zz-nope", "//evil.example.com/", "https://evil.example.com/"):
            self.assertEqual(_student_goal_redirect_url(factory.post("/goals/", {"next": junk})),
                             reverse("student_dashboard_root"), junk)
        self.assertEqual(_student_goal_redirect_url(factory.post("/goals/", {"next": "/tests/"})), "/tests/")


class SupportNextUrlTests(TestCase):
    def test_a_bare_word_next_falls_back_to_the_planner(self):
        mentor = member_of(User.objects.create_user("fz_mentor", password="x"), "Support Teacher")
        profile = SupportTeacherProfile.objects.create(user=mentor, display_name="M", is_active=True)
        title = SupportLessonTitle.objects.create(name="FZ", is_active=True)
        topic = SupportLessonTopic.objects.create(title=title, name="FZ topic", is_active=True)
        start = timezone.now() - timedelta(hours=1)
        booking = SupportLessonBooking.objects.create(
            teacher=profile, student=User.objects.create_user("fz_kid2", password="x"), lesson_title=title,
            lesson_topic=topic, start_at=start, end_at=start + timedelta(minutes=45),
            status=SupportLessonBooking.STATUS_SCHEDULED,
        )
        self.client.force_login(mentor)
        url = reverse("manage_support_lesson_root", args=[booking.pk])
        for junk in ("zz-nope", "//evil.example.com/x", "https://evil.example.com/"):
            response = self.client.post(url, {"action": "close", "next": junk})
            self.assertEqual(response.status_code, 302, junk)
            self.assertEqual(response["Location"], reverse("support_teacher_planner"), junk)
        response = self.client.post(url, {"action": "close", "next": "/support-teacher/dashboard/"})
        self.assertEqual(response["Location"], "/support-teacher/dashboard/")
