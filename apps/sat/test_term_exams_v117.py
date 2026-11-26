"""V117: Mid-term / Final exams — exam variants, sessions, seats, Exams page and calendar."""
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.ratings.models import TermGrade
from apps.sat import term_exams as svc
from apps.sat.exam_models import ExamSeat, ExamSession, TermExam, current_academic_year
from apps.sat.models import (
    Classroom, ClassroomMembership, English_Question, Math_Question, StudentPracticeTestAccess, Test, TestReview,
)
from apps.sat.student_calendar import events_for


def exam_test(name, *, english=3, math=2, test_type=Test.TYPE_EXAM, available=False):
    test = Test.objects.create(name=name, test_type=test_type, is_available=available)
    for n in range(english):
        English_Question.objects.create(test=test, module="module_1", number=n + 1, question=f"E{n}", answer="A")
    for n in range(math):
        Math_Question.objects.create(test=test, module="module_1", number=n + 1, question=f"M{n}", answer="B")
    return test


class TermExamBase(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user("v117_manager", password="x")
        self.manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.teacher = User.objects.create_user("v117_teacher", password="x", first_name="Dilnoza")
        self.teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        self.a = Classroom.objects.create(teacher=self.teacher, name="SAT A")
        self.b = Classroom.objects.create(teacher=self.teacher, name="SAT B")
        self.kids = []
        for n, classroom in enumerate([self.a, self.a, self.b]):
            kid = User.objects.create_user(f"v117_kid{n}", password="x", first_name=f"Kid{n}")
            ClassroomMembership.objects.create(classroom=classroom, user=kid, role="student", status="approved")
            self.kids.append(kid)
        self.exam = svc.create_exam(kind="midterm", academic_year="2026/2027", classrooms=[self.a, self.b],
                                    created_by=self.manager)
        self.variant = exam_test("MID-A")
        self.retake_variant = exam_test("MID-B")
        self.when = timezone.now() + timedelta(days=3)

    def main_session(self, subject="math"):
        return svc.create_session(self.exam, subject=subject, test=self.variant, starts_at=self.when,
                                  duration_minutes=70, room="Room 3", teacher=self.teacher)


class RulesTests(TermExamBase):
    def test_main_session_seats_every_student_and_retake_rules(self):
        session = self.main_session()
        self.assertEqual(session.seats.count(), 3)
        with self.assertRaisesMessage(svc.ExamError, "already has a main session"):
            self.main_session()
        with self.assertRaisesMessage(svc.ExamError, "different test variant"):
            svc.create_session(self.exam, subject="math", test=self.variant, starts_at=self.when,
                               duration_minutes=70, is_retake=True)
        retake = svc.create_session(self.exam, subject="math", test=self.retake_variant, starts_at=self.when + timedelta(days=7),
                                    duration_minutes=70, is_retake=True)
        self.assertEqual(retake.seats.count(), 0)
        self.assertEqual(svc.add_retake_students(retake, [str(self.kids[0].pk), "999999"]), 1)
        self.assertEqual(retake.seats.get().classroom, self.a)

    def test_only_exam_variants_with_questions_of_the_subject(self):
        practice = exam_test("DAY1", test_type=Test.TYPE_REGULAR)
        with self.assertRaisesMessage(svc.ExamError, "Only a test of type Exam"):
            svc.create_session(self.exam, subject="math", test=practice, starts_at=self.when, duration_minutes=70)
        english_only = exam_test("MID-EN", math=0)
        with self.assertRaisesMessage(svc.ExamError, "has no Math questions"):
            svc.create_session(self.exam, subject="math", test=english_only, starts_at=self.when, duration_minutes=70)

    def test_a_variant_is_used_by_one_exam_only(self):
        self.main_session()
        other = svc.create_exam(kind="final", academic_year="2026/2027", classrooms=[self.a])
        with self.assertRaisesMessage(svc.ExamError, "already used in another exam"):
            svc.create_session(other, subject="math", test=self.variant, starts_at=self.when, duration_minutes=70)

    def test_new_class_members_get_seats_and_sessions_with_answers_stay(self):
        session = self.main_session()
        late = User.objects.create_user("v117_late", password="x")
        ClassroomMembership.objects.create(classroom=self.b, user=late, role="student", status="approved")
        self.assertEqual(svc.fill_main_seats(session), 1)
        ExamSeat.objects.filter(session=session, student=late).update(answers={"1": "B"})
        with self.assertRaisesMessage(svc.ExamError, "cannot be deleted"):
            svc.delete_session(session)

    def test_marking_a_test_as_exam_hides_it(self):
        test = exam_test("DAY99", test_type=Test.TYPE_REGULAR, available=True)
        with self.assertRaisesMessage(svc.ExamError, "Hide the test first"):
            svc.mark_as_exam(test)
        Test.objects.filter(pk=test.pk).update(is_available=False)
        test.refresh_from_db()
        StudentPracticeTestAccess.objects.create(membership=ClassroomMembership.objects.first(), test=test)
        svc.mark_as_exam(test)
        test.refresh_from_db()
        self.assertEqual(test.test_type, Test.TYPE_EXAM)
        self.assertFalse(StudentPracticeTestAccess.objects.filter(test=test).exists())

        taken = exam_test("DAY100", test_type=Test.TYPE_REGULAR)
        TestReview.objects.create(test=taken, user=self.kids[0], key="v117-taken", score=900)
        with self.assertRaisesMessage(svc.ExamError, "already took this test"):
            svc.mark_as_exam(taken)

    def test_students_cannot_open_an_exam_variant(self):
        self.client.force_login(self.kids[0])
        response = self.client.get(reverse("practice_test_start_root", args=[self.variant.pk]))
        self.assertEqual(response.status_code, 403)
        from apps.sat.views import user_has_test_access
        self.assertFalse(user_has_test_access(self.kids[0], self.variant))

    def test_term_grade_per_subject(self):
        for subject in ("math", "english"):
            TermGrade.objects.create(student=self.kids[0], classroom=self.a, academic_year="2026/2027", term="midterm",
                                     subject=subject, score=80)
        self.assertEqual(TermGrade.objects.filter(student=self.kids[0]).count(), 2)

    def test_academic_year(self):
        from datetime import date
        self.assertEqual(current_academic_year(date(2026, 11, 26)), "2026/2027")
        self.assertEqual(current_academic_year(date(2027, 3, 1)), "2026/2027")
        self.assertEqual(current_academic_year(date(2027, 8, 20)), "2027/2028")


class PagesTests(TermExamBase):
    def test_manager_creates_exam_and_session_on_the_pages(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse("manager_exams_root"), {
            "kind": "final", "academic_year": "2026/2027", "classrooms": [self.a.pk],
        })
        exam = TermExam.objects.get(kind="final")
        self.assertRedirects(response, reverse("manager_exam_detail_root", args=[exam.pk]))
        day = (timezone.localdate() + timedelta(days=5)).isoformat()
        response = self.client.post(reverse("manager_exam_detail_root", args=[exam.pk]), {
            "action": "add_session", "subject": "english", "test": self.variant.pk, "date": day, "time": "16:00",
            "duration": "64", "room": "Room 1", "teacher": self.teacher.pk, "is_retake": "0",
        }, follow=True)
        self.assertContains(response, "Session added: Reading and Writing, 2 students.")
        session = ExamSession.objects.get(exam=exam)
        self.assertEqual(timezone.localtime(session.starts_at).strftime("%H:%M"), "16:00")
        self.assertContains(response, 'data-nav-key="term-exams"')

    def test_teacher_and_student_pages_and_calendar(self):
        session = self.main_session()
        self.client.force_login(self.teacher)
        self.assertContains(self.client.get(reverse("teacher_exams_root")), "Mid-term 2026/2027")
        self.client.force_login(self.kids[2])
        page = self.client.get(reverse("student_exams_root"))
        self.assertContains(page, "Mid-term · Math")
        self.assertContains(page, "Room 3")
        self.assertNotContains(page, "MID-A")  # the variant name is not shown to students
        day = timezone.localtime(session.starts_at).date()
        term = [e for e in events_for(self.kids[2], day, day) if e.kind == "term"]
        self.assertEqual(term[0].title, "Mid-term · Math")

    def test_past_session_waits_for_results(self):
        session = self.main_session()
        ExamSession.objects.filter(pk=session.pk).update(starts_at=timezone.now() - timedelta(days=1))
        self.client.force_login(self.kids[0])
        self.assertContains(self.client.get(reverse("student_exams_root")), "Waiting for results")

    def test_access(self):
        self.client.force_login(self.kids[0])
        self.assertEqual(self.client.get(reverse("manager_exams_root")).status_code, 403)
        self.assertEqual(self.client.get(reverse("teacher_exams_root")).status_code, 403)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(reverse("manager_exam_detail_root", args=[self.exam.pk])).status_code, 403)
