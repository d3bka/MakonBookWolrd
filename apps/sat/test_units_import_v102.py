"""V102: teachers import units with their materials from any classroom of the school."""
from django.contrib.auth.models import Group, User
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import (
    Classroom, ClassroomHomeworkAssignment, ClassroomLesson, ClassroomLessonResource, ClassroomMembership,
    MakonNotification, Test,
)


class UnitsImportTests(TestCase):
    def setUp(self):
        group, _ = Group.objects.get_or_create(name="Teacher")
        self.author = User.objects.create_user("iu_author", password="x", first_name="Dilnoza", last_name="Karimova")
        self.teacher = User.objects.create_user("iu_teacher", password="x", first_name="Bekzod")
        for user in (self.author, self.teacher):
            user.groups.add(group)
        self.source = Classroom.objects.create(teacher=self.author, name="SAT Morning")
        self.target = Classroom.objects.create(teacher=self.teacher, name="SAT Evening")
        self.student = User.objects.create_user("iu_student", password="x")
        ClassroomMembership.objects.create(classroom=self.target, user=self.student, role="student", status="approved", approved_at=timezone.now())
        self.test = Test.objects.create(name="DAY7")

        self.u1 = ClassroomLesson.objects.create(classroom=self.source, title="Linear equations", summary="Slope and intercept", order=1, created_by=self.author)
        self.u2 = ClassroomLesson.objects.create(classroom=self.source, title="Systems", order=2, created_by=self.author)
        self.u3 = ClassroomLesson.objects.create(classroom=self.source, title="Quadratics", order=3, created_by=self.author)
        self.file_res = ClassroomLessonResource(lesson=self.u1, title="Worksheet", resource_type="file", order=1)
        self.file_res.file.save("worksheet.pdf", ContentFile(b"%PDF worksheet"), save=False)
        self.file_res.save()
        ClassroomLessonResource.objects.create(
            lesson=self.u1, title="Quiz", resource_type="test", test=self.test, order=2, access_code="SECRET",
            score_visibility="scheduled", score_visible_at=timezone.now(),
        )
        ClassroomLessonResource.objects.create(lesson=self.u2, title="Khan video", resource_type="link", url="https://example.com/v", order=1)

        ClassroomLesson.objects.create(classroom=self.target, title="Intro", order=1, created_by=self.teacher)
        ClassroomLesson.objects.create(classroom=self.target, title="Quadratics", order=2, created_by=self.teacher)
        self.url = reverse("teacher_classroom_units_import_root", args=[self.target.pk])
        self.client.force_login(self.teacher)

    def test_search_finds_classes_by_unit_class_and_teacher(self):
        for query in ("linear", "Morning", "Karimova"):
            page = self.client.get(self.url, {"q": query})
            self.assertEqual([c.pk for c in page.context["results"]], [self.source.pk], query)
        page = self.client.get(self.url, {"q": "linear"})
        self.assertContains(page, "Unit 1 · Linear equations")
        self.assertEqual(self.client.get(self.url, {"q": "nothing-like-this"}).context["results"], [])

    def test_preview_warns_about_duplicates(self):
        page = self.client.get(self.url, {"source": self.source.pk})
        units = {u.title: u for u in page.context["units"]}
        self.assertEqual(units["Quadratics"].duplicate_of.order, 2)
        self.assertIsNone(units["Systems"].duplicate_of)
        self.assertEqual(page.context["duplicate_count"], 1)
        self.assertContains(page, "Already in your class as Unit 2")

    def test_copy_is_independent_and_lands_hidden_at_the_end(self):
        self.client.post(self.url, {"source": self.source.pk, "units": [self.u1.pk, self.u2.pk]})
        copies = list(ClassroomLesson.objects.filter(classroom=self.target).order_by("order"))
        self.assertEqual([(c.order, c.title) for c in copies], [(1, "Intro"), (2, "Quadratics"), (3, "Linear equations"), (4, "Systems")])
        linear = copies[2]
        self.assertFalse(linear.is_published)
        self.assertEqual(linear.copied_from, self.u1)
        self.assertEqual(linear.copied_from_label, "SAT Morning · Dilnoza Karimova")
        self.assertEqual(linear.created_by, self.teacher)
        worksheet, quiz = linear.resources.order_by("order")
        self.assertNotEqual(worksheet.file.name, self.file_res.file.name)  # a new file, not a shared one
        with worksheet.file.open("rb") as fh:
            self.assertEqual(fh.read(), b"%PDF worksheet")
        self.assertEqual((quiz.test, quiz.access_code, quiz.score_visibility, quiz.score_visible_at), (self.test, "", "hidden", None))

        self.file_res.file.delete(save=False)
        self.u1.delete()  # the source class removes its unit: the copy stays
        worksheet.refresh_from_db()
        self.assertTrue(worksheet.file.name)
        linear.refresh_from_db()
        self.assertIsNone(linear.copied_from)
        self.assertEqual(linear.copied_from_label, "SAT Morning · Dilnoza Karimova")
        self.assertFalse(MakonNotification.objects.filter(user=self.student).exists())  # hidden: nobody notified

    def test_insert_in_the_middle_and_publish(self):
        self.client.post(self.url, {"source": self.source.pk, "units": [self.u2.pk, self.u3.pk], "insert_after": "1", "publish": "1"})
        rows = list(ClassroomLesson.objects.filter(classroom=self.target).order_by("order").values_list("order", "title", "is_published"))
        self.assertEqual(rows, [(1, "Intro", True), (2, "Systems", True), (3, "Quadratics", True), (4, "Quadratics", True)])
        self.assertEqual(MakonNotification.objects.filter(user=self.student).count(), 1)
        self.client.post(self.url, {"source": self.source.pk, "units": [self.u1.pk], "insert_after": "0"})
        self.assertEqual(ClassroomLesson.objects.get(classroom=self.target, order=1).title, "Linear equations")
        self.assertEqual(ClassroomLesson.objects.filter(classroom=self.target).count(), 5)

    def test_homework_only_when_ticked_as_hidden_drafts(self):
        hw = ClassroomHomeworkAssignment(
            classroom=self.source, created_by=self.author, title="Worksheet homework", assignment_type="file",
            due_at=timezone.now(), attachment_name="ws.pdf",
        )
        hw.attachment.save("ws.pdf", ContentFile(b"%PDF hw"), save=False)
        hw.save()
        self.client.post(self.url, {"source": self.source.pk, "units": [self.u2.pk]})
        self.assertFalse(ClassroomHomeworkAssignment.objects.filter(classroom=self.target).exists())
        self.client.post(self.url, {"source": self.source.pk, "homework": [hw.pk]})
        copy = ClassroomHomeworkAssignment.objects.get(classroom=self.target)
        self.assertEqual((copy.title, copy.is_active, copy.due_at, copy.created_by), ("Worksheet homework", False, None, self.teacher))
        self.assertNotEqual(copy.attachment.name, hw.attachment.name)
        self.assertEqual(copy.attachment_display_name, "ws.pdf")

    def test_rights(self):
        other = User.objects.create_user("iu_other", password="x")
        other.groups.add(Group.objects.get(name="Teacher"))
        for user in (other, self.student):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.assertEqual(self.client.post(self.url, {"source": self.source.pk, "units": [self.u1.pk]}).status_code, 403)
        self.client.force_login(self.teacher)
        foreign = ClassroomLesson.objects.create(classroom=Classroom.objects.create(teacher=other, name="X"), title="Not from source", order=1)
        self.client.post(self.url, {"source": self.source.pk, "units": [foreign.pk]})  # not in the chosen class
        self.assertFalse(ClassroomLesson.objects.filter(classroom=self.target, title="Not from source").exists())
        self.assertEqual(ClassroomLesson.objects.filter(classroom=self.source).count(), 3)  # the source is never changed

    def test_dashboard_shows_import_button_origin_and_copy_count(self):
        self.client.post(self.url, {"source": self.source.pk, "units": [self.u2.pk]})
        page = self.client.get(reverse("teacher_classroom_root", args=[self.target.pk]), {"edit": "1"})
        self.assertContains(page, self.url)
        self.assertContains(page, "Copied from SAT Morning · Dilnoza Karimova")
        self.client.force_login(self.author)
        page = self.client.get(reverse("teacher_classroom_root", args=[self.source.pk]), {"edit": "1"})
        self.assertContains(page, "Imported by 1 other class")


class BucketCopyTests(TestCase):
    def test_r2_files_are_copied_inside_the_bucket(self):
        from unittest import mock

        from apps.sat import lesson_copy

        storage = mock.Mock(bucket_name="makon", location="media")
        storage._normalize_name.side_effect = lambda name: f"media/{name}"
        source = mock.Mock(storage=storage, name="classroom_lessons/ab/old.pdf")
        source.name = "classroom_lessons/ab/old.pdf"
        target = mock.Mock(storage=storage)
        target.field.generate_filename.return_value = "classroom_lessons/cd/old.pdf"
        target.field.max_length = 100
        storage.get_available_name.return_value = "classroom_lessons/cd/old.pdf"
        self.assertTrue(lesson_copy._copy_file(source, target))
        storage.bucket.copy.assert_called_once_with({"Bucket": "makon", "Key": "media/classroom_lessons/ab/old.pdf"}, "media/classroom_lessons/cd/old.pdf")
        self.assertEqual(target.name, "classroom_lessons/cd/old.pdf")
        source.open.assert_not_called()  # nothing downloaded
