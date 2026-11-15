"""V73 A-to-Z: the full AP mock exam journey at the view level (it had no view tests at all)."""
import io
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.apclasses.models import (
    APClass, APExamAnswer, APExamAttempt, APExamEvent, APFRQPage, APFRQSubmission, APMockExam, APMultipleChoiceQuestion,
)


def png_bytes():
    from PIL import Image
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class APFixture:
    def setUp(self):
        ap_class = APClass.objects.create(name="AP Calculus AB", code="AP-CALC-AB")
        self.exam = APMockExam.objects.create(title="Calc mock 1", slug="calc-mock-1", ap_class=ap_class, status="published")
        self.qa1 = APMultipleChoiceQuestion.objects.create(exam=self.exam, part="part_a", number=1, question="2+2?", a="4", b="5", correct_answer="A")
        self.qa2 = APMultipleChoiceQuestion.objects.create(exam=self.exam, part="part_a", number=2, question="3+3?", a="5", b="6", correct_answer="B")
        self.qb1 = APMultipleChoiceQuestion.objects.create(exam=self.exam, part="part_b", number=1, question="d/dx x^2?", c="2x", correct_answer="C")
        APFRQPage.objects.create(exam=self.exam, page_number=1, title="FRQ 1", instructions="Show your work")
        self.event = APExamEvent.objects.create(
            title="November AP mock", slug="nov-ap", exam=self.exam, status="live", always_live=True,
            is_public=True, is_global=True, max_attempts=1, allow_guest_attempts=True,
        )
        self.student = User.objects.create_user("ap_student", password="x", first_name="Aziz", last_name="K")

    def start(self, client=None):
        client = client or self.client
        response = client.post(reverse("apclasses:start_event", args=[self.event.slug]))
        self.assertEqual(response.status_code, 302)
        return response["Location"]

    def answer(self, attempt, part, q, question, choice, action="next", client=None):
        client = client or self.client
        url = reverse("apclasses:attempt", args=[attempt.token])
        return client.post(f"{url}?part={part}&q={q}", {f"question_{question.id}": choice, "action": action})



class APJourneyTests(APFixture, TestCase):
    def test_student_takes_the_whole_exam(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("apclasses:event_detail", args=[self.event.slug])).status_code, 200)
        location = self.start()
        attempt = APExamAttempt.objects.get(student=self.student)
        self.assertIn(str(attempt.token), location)
        page = self.client.get(f"{reverse('apclasses:attempt', args=[attempt.token])}?part=part_a&q=1")
        self.assertContains(page, "2+2?")
        self.answer(attempt, "part_a", 1, self.qa1, "A")          # right
        self.answer(attempt, "part_a", 2, self.qa2, "A")          # wrong
        to_b = self.answer(attempt, "part_b", 1, self.qb1, "C")   # right -> FRQ
        self.assertIn("part=frq", to_b["Location"])
        finish = self.client.post(f"{reverse('apclasses:attempt', args=[attempt.token])}?part=frq&q=1", {"action": "finish"})
        self.assertRedirects(finish, reverse("apclasses:event_result", args=[attempt.token]), fetch_redirect_response=False)
        attempt.refresh_from_db()
        self.assertEqual((attempt.status, attempt.raw_score, attempt.answered_questions), ("submitted", 2, 3))
        self.assertEqual(attempt.score, Decimal("66.67"))
        self.assertEqual(self.client.get(reverse("apclasses:event_result", args=[attempt.token])).status_code, 200)
        review = self.client.get(reverse("apclasses:question_review", args=[attempt.token, self.qa2.id]))
        self.assertEqual(review.status_code, 200)
        # one attempt allowed: starting again shows the result instead of a new attempt
        again = self.start()
        self.assertIn("/result/", again)
        self.assertEqual(APExamAttempt.objects.filter(student=self.student).count(), 1)

    def test_answers_can_be_changed_before_submitting(self):
        self.client.force_login(self.student)
        self.start()
        attempt = APExamAttempt.objects.get(student=self.student)
        self.answer(attempt, "part_a", 1, self.qa1, "B", action="goto")
        self.answer(attempt, "part_a", 1, self.qa1, "a", action="goto")  # lower case is accepted
        self.assertEqual(APExamAnswer.objects.get(attempt=attempt, question=self.qa1).selected_answer, "A")
        self.answer(attempt, "part_a", 1, self.qa1, "Z", action="goto")  # junk clears the answer
        self.assertEqual(APExamAnswer.objects.get(attempt=attempt, question=self.qa1).selected_answer, "")

    def test_attempts_are_private(self):
        self.client.force_login(self.student)
        self.start()
        attempt = APExamAttempt.objects.get(student=self.student)
        other = User.objects.create_user("ap_other", password="x")
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("apclasses:attempt", args=[attempt.token])).status_code, 404)
        self.assertEqual(self.client.get(reverse("apclasses:event_result", args=[attempt.token])).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("apclasses:attempt", args=[attempt.token])).status_code, 404)

    def test_guest_can_take_the_exam_in_their_own_session(self):
        location = self.start()
        attempt = APExamAttempt.objects.get(student__isnull=True)
        self.assertIn(str(attempt.token), location)
        self.answer(attempt, "part_a", 1, self.qa1, "A")
        self.client.post(f"{reverse('apclasses:attempt', args=[attempt.token])}?part=frq&q=1", {"action": "finish"})
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "submitted")
        self.assertEqual(self.client.get(reverse("apclasses:event_result", args=[attempt.token])).status_code, 200)
        stranger = self.client_class()
        self.assertEqual(stranger.get(reverse("apclasses:event_result", args=[attempt.token])).status_code, 404)

    def test_guests_are_refused_when_the_event_does_not_allow_them(self):
        APExamEvent.objects.filter(pk=self.event.pk).update(allow_guest_attempts=False)
        self.start()
        self.assertFalse(APExamAttempt.objects.exists())

    def test_secret_code_gates_the_start(self):
        APExamEvent.objects.filter(pk=self.event.pk).update(access_code="CALC-2026")
        self.client.force_login(self.student)
        self.start()
        self.assertFalse(APExamAttempt.objects.exists())
        detail = reverse("apclasses:event_detail", args=[self.event.slug])
        self.client.post(detail, {"access_code": "wrong"})
        self.start()
        self.assertFalse(APExamAttempt.objects.exists())
        self.client.post(detail, {"access_code": "CALC-2026"})
        self.start()
        self.assertTrue(APExamAttempt.objects.filter(student=self.student).exists())

    def test_events_that_are_not_live_cannot_be_started(self):
        APExamEvent.objects.filter(pk=self.event.pk).update(status="draft")
        self.client.force_login(self.student)
        response = self.client.post(reverse("apclasses:start_event", args=[self.event.slug]), follow=True)
        self.assertContains(response, "not live now")
        self.assertFalse(APExamAttempt.objects.exists())

    def test_server_timer_moves_on_when_a_part_runs_out(self):
        self.client.force_login(self.student)
        self.start()
        attempt = APExamAttempt.objects.get(student=self.student)
        APExamAttempt.objects.filter(pk=attempt.pk).update(part_a_started_at=timezone.now() - timedelta(hours=3))
        response = self.client.get(f"{reverse('apclasses:attempt', args=[attempt.token])}?part=part_a&q=1")
        self.assertEqual(response.status_code, 302)
        self.assertIn("part=part_b", response["Location"])


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                             "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
                   MEDIA_ROOT=tempfile.mkdtemp(prefix="ap-frq-"))
class APFRQUploadTests(APFixture, TestCase):
    """FRQ uploads and the explicit Submit button."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.student)
        self.start()
        self.attempt = APExamAttempt.objects.get(student=self.student)
        self.url = reverse("apclasses:frq_upload", args=[self.attempt.token])

    def upload(self, **files):
        return self.client.post(self.url, {"page_number": 1, **files})

    def test_image_is_stored_under_its_real_extension(self):
        self.upload(image=SimpleUploadedFile("answer.html", png_bytes(), content_type="image/png"))
        submission = APFRQSubmission.objects.get(attempt=self.attempt)
        self.assertTrue(submission.image.name.endswith(".png"), submission.image.name)
        self.assertNotIn(".html", submission.image.name)

    def test_fake_images_and_fake_pdfs_are_refused(self):
        self.upload(image=SimpleUploadedFile("a.png", b"<script>alert(1)</script>", content_type="image/png"))
        self.upload(file=SimpleUploadedFile("a.pdf", b"<html>not a pdf</html>", content_type="application/pdf"))
        self.upload(file=SimpleUploadedFile("a.exe", b"%PDF-1.4", content_type="application/pdf"))
        self.assertFalse(APFRQSubmission.objects.exists())
        self.upload(file=SimpleUploadedFile("a.pdf", b"%PDF-1.4 minimal", content_type="application/pdf"))
        self.assertTrue(APFRQSubmission.objects.filter(attempt=self.attempt).exists())

    def test_wrong_page_nothing_uploaded_and_someone_elses_attempt(self):
        self.client.post(self.url, {"page_number": 99, "image": SimpleUploadedFile("a.png", png_bytes(), content_type="image/png")})
        self.client.post(self.url, {"page_number": 1})
        self.assertFalse(APFRQSubmission.objects.exists())
        self.client.force_login(User.objects.create_user("ap_intruder", password="x"))
        response = self.client.post(self.url, {"page_number": 1, "image": SimpleUploadedFile("a.png", png_bytes(), content_type="image/png")})
        self.assertEqual(response.status_code, 404)

    def test_submit_button_and_no_uploads_after_submitting(self):
        submit = reverse("apclasses:submit_attempt", args=[self.attempt.token])
        self.assertEqual(self.client.get(submit).status_code, 405)
        self.assertRedirects(self.client.post(submit), reverse("apclasses:event_result", args=[self.attempt.token]),
                             fetch_redirect_response=False)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, "submitted")
        self.upload(image=SimpleUploadedFile("late.png", png_bytes(), content_type="image/png"))
        self.assertFalse(APFRQSubmission.objects.exists())

    def test_coming_soon_page(self):
        self.assertEqual(self.client.get(reverse("apclasses:coming_soon")).status_code, 200)
