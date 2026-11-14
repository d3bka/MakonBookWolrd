"""V70: the "Certificate" button on practice-test results really produces a PDF.

Storage is swapped for a temporary FileSystemStorage so the whole path runs
(button URL -> view -> scoring -> PDF -> upload -> redirect) without R2, and
the generated PDF is opened to check what the student will actually see.
"""
import json
import shutil
import tempfile
import uuid
from pathlib import Path
from unittest import mock

import fitz
from django.contrib.auth.models import Group, User
from django.core.files.storage import FileSystemStorage
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import (
    Classroom, ClassroomMembership, English_Question, Math_Question, QuestionDomain, Test, TestModule, TestReview,
)

ENGLISH_DOMAINS = ("Information and Ideas", "Craft and Structure", "Expression of Ideas", "Standard English Conventions")
MATH_DOMAINS = ("Algebra", "Advanced Math", "Problem-Solving and Data Analysis", "Geometry and Trigonometry")


class CertificateTests(TestCase):
    def setUp(self):
        self.media = Path(tempfile.mkdtemp(prefix="cert-test-"))
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        storage = lambda *a, **k: FileSystemStorage(location=str(self.media), base_url="/cert-test/")  # noqa: E731
        for target in ("apps.sat.storages.PrivateStorage", "apps.sat.libs.certificate.certificate.PrivateStorage"):
            patcher = mock.patch(target, storage)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.student = User.objects.create_user("cert_student", password="x", first_name="Aziz", last_name="Karimov")
        self.test = Test.objects.create(name="CERT DAY1", is_available=True)
        domains = {name: QuestionDomain.objects.create(name=name) for name in ENGLISH_DOMAINS + MATH_DOMAINS}
        self.english, self.math = [], []
        for module in ("module_1", "module_2"):
            for i, name in enumerate(ENGLISH_DOMAINS * 2):
                self.english.append(English_Question.objects.create(test=self.test, module=module, number=i + 1, answer="A", domain=domains[name]))
            for i, name in enumerate(MATH_DOMAINS * 2):
                self.math.append(Math_Question.objects.create(test=self.test, module=module, number=i + 1, answer="5", domain=domains[name]))

    def attempt(self, classroom=None, wrong_math=0):
        attempt_id = uuid.uuid4()
        for section, questions, right in (("english", self.english, "A"), ("math", self.math, "5")):
            for module, prefix in (("m1", "module_1"), ("m2", "module_2")):
                answers = []
                for index, q in enumerate(x for x in questions if x.module == prefix):
                    wrong = section == "math" and module == "m1" and index < wrong_math
                    answers.append({"questionID": q.id, "answer": "9" if wrong else right})
                TestModule.objects.create(test=self.test, user=self.student, classroom=classroom, attempt_id=attempt_id,
                                          section=section, module=module, answers=json.dumps({"answers": answers}))
        return TestReview.objects.create(user=self.student, test=self.test, classroom=classroom, attempt_id=attempt_id,
                                         score=1600, key=uuid.uuid4().hex)

    def certificate_url(self, review):
        return f"{reverse('practice_test_certificate_root', args=[self.test.pk])}?review_key={review.key}"

    def pdf_text(self, response):
        self.assertEqual(response.status_code, 302, response.content[:300])
        name = response["Location"].removeprefix("/cert-test/")
        with fitz.open(self.media / name) as doc:
            return doc[0].get_text()

    def test_certificate_for_a_regular_practice_attempt(self):
        review = self.attempt()
        self.client.force_login(self.student)
        text = self.pdf_text(self.client.get(self.certificate_url(review)))
        self.assertIn("Aziz Karimov", text)  # the student's name, not their login
        self.assertIn("CERT DAY1", text)
        self.assertIn("1580-1600", text)  # total score range for a perfect run
        taken = timezone.localtime(review.created_at)
        self.assertIn(f"{taken:%B} {taken.day}, {taken.year}", text)  # a readable date, not "2026-11-14 "
        review.refresh_from_db()
        self.assertTrue(review.certificate.startswith("certificates/"))

    def test_certificate_for_an_attempt_made_inside_a_classroom(self):
        teacher = User.objects.create_user("cert_teacher", password="x")
        teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        classroom = Classroom.objects.create(teacher=teacher, name="Cert class", is_active=True)
        ClassroomMembership.objects.create(classroom=classroom, user=self.student, role="student", status="approved",
                                           approved_at=timezone.now())
        review = self.attempt(classroom=classroom, wrong_math=3)
        self.client.force_login(self.student)
        text = self.pdf_text(self.client.get(self.certificate_url(review)))
        self.assertIn("Aziz Karimov", text)
        # the template itself prints "400-1600", so compare the score ranges
        self.assertNotIn("1580-1600", text)  # three wrong math answers must lower the score
        self.assertIn("790-800", text)  # reading and writing stayed perfect

    def test_second_click_reuses_the_stored_pdf(self):
        review = self.attempt()
        self.client.force_login(self.student)
        first = self.client.get(self.certificate_url(review))
        second = self.client.get(self.certificate_url(review))
        self.assertEqual(first["Location"], second["Location"])
        self.assertEqual(len(list((self.media / "certificates").iterdir())), 1)

    def test_other_students_cannot_open_someone_elses_certificate(self):
        review = self.attempt()
        intruder = User.objects.create_user("cert_intruder", password="x")
        self.client.force_login(intruder)
        self.assertEqual(self.client.get(self.certificate_url(review)).status_code, 404)

    def test_results_page_button_points_at_the_certificate(self):
        review = self.attempt()
        self.client.force_login(self.student)
        page = self.client.get(f"{reverse('practice_test_results_root', args=[self.test.pk])}?review_key={review.key}")
        self.assertContains(page, reverse("practice_test_certificate_root", args=[self.test.pk]))

    def test_del_cert_forgets_cached_pdfs_so_they_are_rebuilt(self):
        from io import StringIO

        from django.core.management import call_command

        review = self.attempt()
        TestReview.objects.filter(pk=review.pk).update(certificate="certificates/old-with-username.pdf")
        out = StringIO()
        call_command("del_cert", stdout=out)
        review.refresh_from_db()
        self.assertEqual(review.certificate, "")
        self.assertIn("Cleared 1", out.getvalue())
