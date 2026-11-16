"""V73 A-to-Z: student pages that had no tests (admissions, topic practice, stickers, retakes, makeup, AP, lessons)."""
import io
import tempfile

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import (
    Classroom, ClassroomMembership, MakeupTest, Math_Question, QuestionType, Test, TestReview, UserChatSticker,
)


def png_bytes(size=(8, 8)):
    from PIL import Image
    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format="PNG")
    return buffer.getvalue()


class StudentPagesTests(TestCase):
    def setUp(self):
        self.kid = User.objects.create_user("sp_kid", password="x", first_name="Kid")
        teacher = User.objects.create_user("sp_teacher", password="x")
        teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        self.teacher = teacher
        self.classroom = Classroom.objects.create(teacher=teacher, name="SP class", is_active=True)
        ClassroomMembership.objects.create(classroom=self.classroom, user=self.kid, role="student", status="approved",
                                           approved_at=timezone.now())
        self.test = Test.objects.create(name="SP-DAY1", is_available=True)
        self.client.force_login(self.kid)

    def test_admissions_pages(self):
        self.assertEqual(self.client.get(reverse("admissions_root")).status_code, 200)
        # V80: the old three sections became a lesson course; their links go to the course index.
        for slug in ("university_guide", "application_help", "scholarships"):
            self.assertRedirects(self.client.get(reverse("admissions_section_root", args=[slug])),
                                 reverse("admissions_root"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("admissions_section_root", args=["how-admissions-work"])).status_code, 200)
        self.assertEqual(self.client.get(reverse("admissions_section_root", args=["nope"])).status_code, 404)

    def test_topic_practice(self):
        from apps.sat.models import QuestionDomain
        qtype = QuestionType.objects.create(name="Linear equations", domain=QuestionDomain.objects.create(name="Algebra"))
        self.assertEqual(self.client.get(reverse("student_topic_practice_root", args=["chemistry", qtype.pk])).status_code, 404)
        response = self.client.get(reverse("student_topic_practice_root", args=["math", qtype.pk]))
        self.assertIn(response.status_code, (200, 302))

    def test_restart_section_is_post_only_and_validates_the_section(self):
        url = reverse("practice_test_restart_section_root", args=[self.test.name, "math"])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(reverse("practice_test_restart_section_root", args=[self.test.name, "physics"])).status_code, 400)
        self.assertContains(self.client.post(reverse("practice_test_restart_section_root", args=["NOPE", "math"])), "not found")

    def test_makeup_test_needs_the_right_group(self):
        group = Group.objects.create(name="Makeup Nov")
        makeup = MakeupTest.objects.create(name="MAKEUP-NOV")
        makeup.groups.add(group)
        url = reverse("makeup_test_start_root", args=[makeup.name])
        self.assertContains(self.client.get(url), "Permission Denied")
        self.kid.groups.add(group)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_certificate_by_user_is_admin_only_and_needs_a_review_key(self):
        review = TestReview.objects.create(user=self.kid, test=self.test, key="sp-review", score=1300)
        url = reverse("results_certificate_by_user", args=[self.test.pk, self.kid.username])
        self.assertEqual(self.client.get(url, {"review_key": review.key}).status_code, 403)  # a student
        admin = User.objects.create_user("sp_admin", password="x")
        admin.groups.add(Group.objects.get_or_create(name="Admin")[0])
        self.client.force_login(admin)
        self.assertEqual(self.client.get(url).status_code, 400)
        self.assertEqual(self.client.get(url, {"review_key": "wrong"}).status_code, 404)

    def test_classroom_ap_pages(self):
        self.assertEqual(self.client.get(reverse("classroom_ap_tests_root", args=[self.classroom.pk])).status_code, 302)  # SAT class
        Classroom.objects.filter(pk=self.classroom.pk).update(classroom_type=Classroom.CLASSROOM_TYPE_AP)
        self.assertEqual(self.client.get(reverse("classroom_ap_tests_root", args=[self.classroom.pk])).status_code, 200)
        access = reverse("teacher_classroom_ap_access_root", args=[self.classroom.pk])
        self.assertEqual(self.client.get(access).status_code, 403)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(access).status_code, 200)
        self.assertEqual(self.client.post(access, {"events": ["999"]}).status_code, 302)
        self.assertEqual(self.client.get(reverse("classroom_ap_tests_root", args=[self.classroom.pk])).status_code, 200)

    def test_classroom_vocabulary_quiz_start_respects_section_access(self):
        response = self.client.post(reverse("classroom_vocabulary_practice_quiz_start", args=[self.classroom.pk]), {"question_count": 4})
        self.assertIn(response.status_code, (200, 302, 403))
        outsider = User.objects.create_user("sp_outsider", password="x")
        self.client.force_login(outsider)
        response = self.client.post(reverse("classroom_vocabulary_practice_quiz_start", args=[self.classroom.pk]), {"question_count": 4})
        self.assertNotEqual(response.status_code, 200)

    def test_lesson_page_needs_a_purchase(self):
        from apps.sat.models import Lesson, LessonPackage, PurchasedLessonPackage
        package = LessonPackage.objects.create(name="SP package", description="d")
        lesson = Lesson.objects.create(package=package, order=1, name="Lesson 1")
        url = reverse("lesson_detail_root", args=[lesson.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        PurchasedLessonPackage.objects.create(user=self.kid, package=package)
        self.assertEqual(self.client.get(url).status_code, 200)


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                             "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
                   MEDIA_ROOT=tempfile.mkdtemp(prefix="sp-stickers-"))
class StickerUploadTests(TestCase):
    def setUp(self):
        self.kid = User.objects.create_user("st_kid", password="x")
        teacher = User.objects.create_user("st_teacher", password="x")
        classroom = Classroom.objects.create(teacher=teacher, name="ST class", is_active=True)
        ClassroomMembership.objects.create(classroom=classroom, user=self.kid, role="student", status="approved",
                                           approved_at=timezone.now())
        self.client.force_login(self.kid)
        self.url = reverse("student_chat_sticker_upload_root")

    def upload(self, name, data, content_type="image/png", **extra):
        return self.client.post(self.url, {"sticker": SimpleUploadedFile(name, data, content_type=content_type), **extra})

    def test_real_image_is_saved_under_its_real_extension(self):
        response = self.upload("cat.html", png_bytes())
        self.assertEqual(response.status_code, 200, response.content)
        sticker = UserChatSticker.objects.get(user=self.kid)
        self.assertTrue(sticker.image.name.endswith(".png"), sticker.image.name)
        self.assertEqual(sticker.title, "cat")

    def test_non_images_and_bad_packs_are_refused(self):
        self.assertEqual(self.upload("x.png", b"<svg onload=alert(1)>").status_code, 400)
        self.assertEqual(self.upload("x.png", png_bytes(), content_type="image/svg+xml").status_code, 400)
        self.assertEqual(self.upload("x.png", png_bytes(), pack_id="zz").status_code, 400)
        self.assertEqual(self.upload("x.png", png_bytes(), pack_id="999").status_code, 400)
        self.assertEqual(self.client.post(self.url).status_code, 400)
        self.assertFalse(UserChatSticker.objects.exists())

    def test_delete_own_sticker_only(self):
        self.upload("mine.png", png_bytes())
        sticker = UserChatSticker.objects.get()
        other = User.objects.create_user("st_other", password="x")
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse("student_chat_sticker_delete_root", args=[sticker.pk])).status_code, 404)
        self.client.force_login(self.kid)
        self.assertTrue(self.client.post(reverse("student_chat_sticker_delete_root", args=[sticker.pk])).json()["ok"])
        self.assertFalse(UserChatSticker.objects.exists())
