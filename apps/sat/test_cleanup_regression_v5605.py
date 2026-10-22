from django.test import SimpleTestCase

from . import views


class CleanupCompatibilityV5605Tests(SimpleTestCase):
    def test_classroom_chat_wrapper_keeps_legacy_delegate(self):
        self.assertTrue(callable(views._legacy_classroom_chat_v523))
        self.assertTrue(callable(views.classroom_chat))
        self.assertIsNot(views._legacy_classroom_chat_v523, views.classroom_chat)
