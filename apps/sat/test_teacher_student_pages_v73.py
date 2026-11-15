"""V73 A-to-Z: a teacher's per-student pages (progress, review, integrity) and who may open them."""
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import Classroom, ClassroomMembership, Test, TestReview, TestStage


def teacher(name):
    user = User.objects.create_user(name, password="x")
    user.groups.add(Group.objects.get_or_create(name="Teacher")[0])
    return user


class TeacherStudentPagesTests(TestCase):
    def setUp(self):
        self.teacher = teacher("tsp_teacher")
        self.other = teacher("tsp_other")
        self.classroom = Classroom.objects.create(teacher=self.teacher, name="TSP class")
        self.kid = User.objects.create_user("tsp_kid", password="x")
        self.outsider = User.objects.create_user("tsp_outsider", password="x")
        ClassroomMembership.objects.create(classroom=self.classroom, user=self.kid, role="student", status="approved",
                                           approved_at=timezone.now())
        self.test = Test.objects.create(name="TSP-DAY1", is_available=True)

    def urls(self, student):
        c, s, t = self.classroom.pk, student.pk, self.test.name
        return [
            reverse("teacher_student_practice_progress_root", args=[c, s]),
            reverse("teacher_student_practice_progress_root", args=[c, s]) + "?q=day&status=completed&per_page=24",
            reverse("teacher_student_admission_progress_root", args=[c, s]),
            reverse("teacher_classroom_student_review_root", args=[c, s, t]),
            reverse("classroom_student_integrity_history", args=[c, s, t]),
        ]

    def test_own_teacher_opens_every_page(self):
        self.client.force_login(self.teacher)
        for url in self.urls(self.kid):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_other_teacher_and_students_are_refused(self):
        for who in (self.other, self.kid):
            self.client.force_login(who)
            for url in self.urls(self.kid):
                self.assertIn(self.client.get(url).status_code, (302, 403), (who.username, url))

    def test_a_student_outside_the_class_is_404(self):
        self.client.force_login(self.teacher)
        for url in self.urls(self.outsider):
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_review_question_of_another_students_attempt_is_not_shown(self):
        foreign = TestReview.objects.create(user=self.outsider, test=self.test, key="tsp-foreign", score=1200)
        self.client.force_login(self.teacher)
        url = reverse("teacher_classroom_student_review_question_root",
                      args=[self.classroom.pk, self.kid.pk, foreign.key, "math", "m1", "1"])
        self.assertContains(self.client.get(url), "no longer available")

    def test_integrity_unlock_is_post_only_and_teacher_only(self):
        stage = TestStage.objects.create(user=self.kid, test=self.test, test_type="regular", classroom=self.classroom,
                                         stage=1, integrity_retake_locked=True)
        url = reverse("classroom_student_integrity_unlock", args=[self.classroom.pk, self.kid.pk, self.test.name])
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code, 403)
        stage.refresh_from_db()
        self.assertTrue(stage.integrity_retake_locked)
        self.client.force_login(self.teacher)
        self.client.post(url)
        stage.refresh_from_db()
        self.assertFalse(stage.integrity_retake_locked)
