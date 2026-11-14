"""V69: student and exam uploads get unguessable storage keys."""
from io import StringIO

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from apps.apclasses.models import APFRQPage, APFRQSubmission
from apps.base.models import GeneralIssueReport
from apps.base.upload_paths import RandomUploadPath, is_random_name, safe_extension
from apps.sat.models import ChatMessage, Classroom, ClassroomLessonResource

IN_MEMORY = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


class RandomUploadPathTests(SimpleTestCase):
    def test_key_is_random_and_keeps_only_a_safe_extension(self):
        path = RandomUploadPath("classroom_chat_files")
        first, second = path(None, "IMG_1234.JPG"), path(None, "IMG_1234.JPG")
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("classroom_chat_files/"))
        self.assertTrue(first.endswith(".jpg"))
        self.assertNotIn("IMG_1234", first)
        self.assertTrue(is_random_name(first))

    def test_weird_extensions_are_dropped(self):
        self.assertEqual(safe_extension("x.tar.gz"), ".gz")
        self.assertEqual(safe_extension("evil.php%00.png"), ".png")
        self.assertEqual(safe_extension("noext"), "")
        self.assertEqual(safe_extension("bad.ext with space"), "")

    def test_sensitive_fields_use_random_keys(self):
        for model, field in (
            (APFRQSubmission, "image"), (APFRQSubmission, "file"),
            (APFRQPage, "image"), (APFRQPage, "file"),
            (ChatMessage, "file"), (ClassroomLessonResource, "file"),
            (GeneralIssueReport, "attachment"),
        ):
            with self.subTest(model=model.__name__, field=field):
                self.assertIsInstance(model._meta.get_field(field).upload_to, RandomUploadPath)


@override_settings(STORAGES=IN_MEMORY)
class ChatUploadKeyTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("key-teacher", password="x")
        self.classroom = Classroom.objects.create(teacher=self.teacher, name="Keys")

    def test_chat_file_keeps_original_name_for_display_only(self):
        message = ChatMessage.objects.create(
            classroom=self.classroom, sender=self.teacher,
            file=SimpleUploadedFile("Homework scan.pdf", b"%PDF-1.4 x"),
        )
        self.assertTrue(is_random_name(message.file.name))
        self.assertNotIn("Homework", message.file.name)
        self.assertEqual(message.file_original_name, "Homework scan.pdf")
        self.assertEqual(message.file_display_name, "Homework scan.pdf")

    def test_command_dry_run_changes_nothing_then_apply_moves_old_files(self):
        old_key = default_storage.save("classroom_chat_files/IMG_1234.jpg", ContentFile(b"jpeg-bytes"))
        message = ChatMessage.objects.create(classroom=self.classroom, sender=self.teacher)
        ChatMessage.objects.filter(pk=message.pk).update(file=old_key)

        out = StringIO()
        call_command("randomize_upload_keys", stdout=out)
        self.assertIn("Would move 1 file(s)", out.getvalue())
        message.refresh_from_db()
        self.assertEqual(message.file.name, old_key)

        call_command("randomize_upload_keys", "--apply", stdout=StringIO())
        message.refresh_from_db()
        self.assertTrue(is_random_name(message.file.name))
        self.assertEqual(message.file_original_name, "IMG_1234.jpg")
        self.assertFalse(default_storage.exists(old_key))
        with default_storage.open(message.file.name) as moved:
            self.assertEqual(moved.read(), b"jpeg-bytes")

        out = StringIO()
        call_command("randomize_upload_keys", "--apply", stdout=out)
        self.assertIn("Moved 0 file(s); 1 already random", out.getvalue())
