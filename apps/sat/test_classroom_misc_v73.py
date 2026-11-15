"""V73 A-to-Z: classroom edit, chat fetch / file delete, teacher hubs and same-day assessment edits."""
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.ratings.models import AssessmentSchedule, RatingAssessment
from apps.sat.models import ChatMessage, Classroom, ClassroomMembership


def teacher(name):
    user = User.objects.create_user(name, password="x", first_name=name.title())
    user.groups.add(Group.objects.get_or_create(name="Teacher")[0])
    return user


class ClassroomMiscTests(TestCase):
    def setUp(self):
        self.teacher = teacher("cm_teacher")
        self.other = teacher("cm_other")
        self.classroom = Classroom.objects.create(teacher=self.teacher, name="CM class", is_active=True)
        self.kid = User.objects.create_user("cm_kid", password="x", first_name="Kid")
        self.outsider = User.objects.create_user("cm_outsider", password="x")
        ClassroomMembership.objects.create(classroom=self.classroom, user=self.kid, role="student", status="approved",
                                           approved_at=timezone.now())

    def test_edit_classroom(self):
        url = reverse("edit_classroom", args=[self.classroom.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url, {"name": "Hijacked"}).status_code, 403)
        self.client.force_login(self.teacher)
        self.client.post(url, {"name": "", "classroom_type": "sat"})
        self.client.post(url, {"name": "X", "classroom_type": "chemistry"})
        self.client.post(url, {"name": "N" * 500, "classroom_type": "sat"})
        self.classroom.refresh_from_db()
        self.assertEqual(self.classroom.name, "CM class")
        self.client.post(url, {"name": "SAT Evening", "description": "Mon/Wed", "classroom_type": "ap"})
        self.classroom.refresh_from_db()
        self.assertEqual((self.classroom.name, self.classroom.classroom_type), ("SAT Evening", "ap"))

    def test_hollihop_managed_classrooms_are_read_only_here(self):
        Classroom.objects.filter(pk=self.classroom.pk).update(hollihop_edunit_id=4242, hollihop_managed=True)
        self.client.force_login(self.teacher)
        self.client.post(reverse("edit_classroom", args=[self.classroom.pk]), {"name": "Renamed", "classroom_type": "sat"})
        self.classroom.refresh_from_db()
        self.assertEqual(self.classroom.name, "CM class")

    def test_chat_fetch_returns_only_newer_messages_to_members(self):
        first = ChatMessage.objects.create(classroom=self.classroom, sender=self.kid, message="hello")
        second = ChatMessage.objects.create(classroom=self.classroom, sender=self.teacher, message="hi class")
        url = reverse("fetch_classroom_messages", args=[self.classroom.pk])
        self.client.force_login(self.kid)
        payload = self.client.get(url, {"last_id": first.pk}).json()
        ids = [row["id"] for row in payload.get("messages", payload.get("results", []))]
        self.assertEqual(ids, [second.pk])
        self.assertEqual(self.client.get(url, {"last_id": "zz"}).status_code, 200)
        self.client.force_login(self.outsider)
        self.assertIn(self.client.get(url).status_code, (403, 404))

    @override_settings(MEDIA_ROOT=__import__("tempfile").mkdtemp(prefix="cm-media-"))
    def test_only_the_teacher_removes_a_chat_file(self):
        msg = ChatMessage.objects.create(classroom=self.classroom, sender=self.kid, message="see file",
                                         file=SimpleUploadedFile("notes.txt", b"hello"))
        url = reverse("delete_classroom_message_file", args=[self.classroom.pk, msg.pk])
        self.client.force_login(self.kid)
        self.assertEqual(self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest").status_code, 403)
        self.assertEqual(self.client.get(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest").status_code, 405)
        self.client.force_login(self.teacher)
        self.assertTrue(self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest").json()["ok"])
        msg.refresh_from_db()
        self.assertFalse(msg.file)

    def test_teacher_hubs(self):
        self.client.force_login(self.teacher)
        for name in ("teacher_lessons_root", "teacher_progress_root", "teacher_assessments_root"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)
            self.assertContains(response, "CM class")
        self.client.force_login(self.kid)
        for name in ("teacher_lessons_root", "teacher_progress_root", "teacher_assessments_root"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_assessment_can_be_edited_on_the_lesson_day_by_its_teacher_only(self):
        AssessmentSchedule.objects.create(classroom=self.classroom, teacher=self.teacher,
                                          weekdays=[timezone.localdate().isoweekday()])
        scores = dict(homework=5, progress=5, activity=5, attendance=5, behavior=5)
        today = RatingAssessment.objects.create(classroom=self.classroom, teacher=self.teacher, student=self.kid,
                                                lesson_date=timezone.localdate(), **scores)
        url = reverse("teacher_edit_assessment_root", args=[today.pk])
        new = {**scores, "homework": 9, "comment": "better"}
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url, new).status_code, 403)
        self.client.force_login(self.teacher)
        self.client.post(url, {**new, "homework": 11})  # out of range: not saved
        today.refresh_from_db()
        self.assertEqual(today.homework, 5)
        self.client.post(url, new)
        today.refresh_from_db()
        self.assertEqual(today.homework, 9)
        yesterday = RatingAssessment.objects.create(classroom=self.classroom, teacher=self.teacher, student=self.outsider,
                                                    lesson_date=timezone.localdate() - timedelta(days=1), **scores)
        self.assertEqual(self.client.post(reverse("teacher_edit_assessment_root", args=[yesterday.pk]), new).status_code, 403)
