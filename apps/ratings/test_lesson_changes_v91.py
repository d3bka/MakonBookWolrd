"""V91: teachers report cancelled/covered lessons, managers decide, monthly reports."""
from datetime import timedelta
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.ratings.assessment_policy import prepare_today_obligations, today_assessment_state
from apps.ratings.models import (
    AssessmentCalendarException, AssessmentObligation, AssessmentPenalty, AssessmentSchedule, LessonChangeRequest,
)
from apps.sat.models import Classroom, ClassroomMembership, MakonNotification

TODAY = timezone.localdate()


class LessonChangeTests(TestCase):
    def setUp(self):
        teachers = Group.objects.get_or_create(name="Teacher")[0]
        self.aziz = User.objects.create_user("v91_aziz", first_name="Aziz", password="x")
        self.bek = User.objects.create_user("v91_bek", first_name="Bek", password="x")
        self.aziz.groups.add(teachers)
        self.bek.groups.add(teachers)
        self.manager = User.objects.create_user("v91_manager", password="x")
        self.manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.classroom = Classroom.objects.create(name="SAT Math A", teacher=self.aziz)
        self.student = User.objects.create_user("v91_kid", password="x")
        ClassroomMembership.objects.create(classroom=self.classroom, user=self.student, role="student",
                                           status="approved", approved_at=timezone.now() - timedelta(days=10))
        self.schedule = AssessmentSchedule.objects.create(
            classroom=self.classroom, teacher=self.aziz, starts_on=TODAY - timedelta(days=7),
            # Three lesson days from today: today is always one of the week's three mandatory lessons.
            weekdays=sorted({(TODAY + timedelta(days=i)).isoweekday() for i in range(3)}))

    def report(self, day=None, kind="cancel", reason="I am ill", **extra):
        self.client.force_login(self.aziz)
        data = {"date": (day or TODAY).isoformat(), "kind": kind, "reason": reason, **extra}
        return self.client.post(reverse("teacher_report_lesson_change", args=[self.classroom.pk]), data, follow=True)

    def decide(self, change, decision, note=""):
        self.client.force_login(self.manager)
        return self.client.post(reverse("manager_decide_lesson_change", args=[change.pk]),
                                {"decision": decision, "note": note}, follow=True)

    def test_teacher_reports_and_managers_are_notified(self):
        page = self.client.get(reverse("teacher_classroom_assessments_root", args=[self.classroom.pk]))
        self.assertEqual(page.status_code, 302)  # not logged in yet
        self.client.force_login(self.aziz)
        page = self.client.get(reverse("teacher_classroom_assessments_root", args=[self.classroom.pk]))
        self.assertContains(page, "Lesson cancelled or covered?")
        response = self.report()
        self.assertContains(response, "Sent to the managers")
        change = LessonChangeRequest.objects.get()
        self.assertEqual((change.status, change.kind, change.date), ("pending", "cancel", TODAY))
        note = MakonNotification.objects.get(user=self.manager)
        self.assertIn("SAT Math A", note.title)
        self.assertIn("I am ill", note.message)
        self.assertContains(self.client.get(reverse("teacher_classroom_assessments_root", args=[self.classroom.pk])),
                            "Waiting for a manager")

    def test_reports_are_only_for_today_or_future_lesson_days(self):
        self.assertContains(self.report(TODAY - timedelta(days=1)), "only for today or a future lesson")
        AssessmentSchedule.objects.filter(pk=self.schedule.pk).update(weekdays=[(TODAY + timedelta(days=1)).isoweekday()])
        self.assertContains(self.report(TODAY + timedelta(days=2)), "no scheduled lesson on that day")
        self.assertFalse(LessonChangeRequest.objects.exists())

    def test_one_waiting_request_per_lesson_and_a_cover_needs_a_teacher(self):
        self.report()
        self.assertContains(self.report(), "already waiting")
        self.assertContains(self.report(TODAY + timedelta(days=1), kind="cover"), "teacher who covers")
        self.assertEqual(LessonChangeRequest.objects.count(), 1)

    def test_other_teachers_cannot_report_for_this_class(self):
        self.client.force_login(self.bek)
        response = self.client.post(reverse("teacher_report_lesson_change", args=[self.classroom.pk]),
                                    {"date": TODAY.isoformat(), "kind": "cancel", "reason": "x" * 5})
        self.assertEqual(response.status_code, 403)

    def test_approval_cancels_the_day_and_removes_the_duty_and_fine(self):
        self.report()
        change = LessonChangeRequest.objects.get()
        response = self.decide(change, "approve", "Get well")
        self.assertContains(response, "is cancelled")
        exception = AssessmentCalendarException.objects.get(schedule=self.schedule, date=TODAY)
        self.assertEqual(exception.action, "cancelled")
        self.assertEqual(prepare_today_obligations(), 0)
        _, allowed, required = today_assessment_state(self.classroom, self.aziz)
        self.assertEqual((allowed, required), (False, False))
        message = MakonNotification.objects.get(user=self.aziz)
        self.assertIn("approved", message.title)
        self.assertIn("Get well", message.message)

    def test_a_fine_created_before_approval_is_waived(self):
        self.report()
        obligation, _ = AssessmentObligation.objects.get_or_create(schedule=self.schedule, student=self.student, lesson_date=TODAY)
        penalty = AssessmentPenalty.objects.create(obligation=obligation)
        self.decide(LessonChangeRequest.objects.get(), "approve")
        penalty.refresh_from_db()
        self.assertEqual(penalty.status, AssessmentPenalty.WAIVED)
        self.assertEqual(penalty.reviewed_by, self.manager)

    def test_rejection_keeps_the_lesson(self):
        self.report()
        self.decide(LessonChangeRequest.objects.get(), "reject", "Please assess")
        self.assertFalse(AssessmentCalendarException.objects.exists())
        prepare_today_obligations()
        self.assertTrue(AssessmentObligation.objects.filter(schedule=self.schedule, lesson_date=TODAY).exists())
        self.assertIn("rejected", MakonNotification.objects.get(user=self.aziz).title)
        # A decided request cannot be decided again.
        self.assertContains(self.decide(LessonChangeRequest.objects.get(), "approve"), "already decided")

    def test_teacher_can_withdraw_a_waiting_request(self):
        self.report()
        change = LessonChangeRequest.objects.get()
        self.client.force_login(self.bek)
        self.assertEqual(self.client.post(reverse("teacher_withdraw_lesson_change", args=[change.pk])).status_code, 404)
        self.client.force_login(self.aziz)
        self.client.post(reverse("teacher_withdraw_lesson_change", args=[change.pk]))
        change.refresh_from_db()
        self.assertEqual(change.status, "withdrawn")

    def test_cover_is_recorded_and_works_like_a_cancellation(self):
        self.report(kind="cover", cover_teacher_id=self.bek.pk, reason="Conference")
        change = LessonChangeRequest.objects.get()
        self.assertEqual(change.cover_teacher, self.bek)
        self.decide(change, "approve")
        self.assertIn("Covered by Bek", AssessmentCalendarException.objects.get().reason)
        self.assertEqual(prepare_today_obligations(), 0)

    def test_monthly_report_and_excel(self):
        self.report(kind="cover", cover_teacher_id=self.bek.pk, reason="Conference")
        self.decide(LessonChangeRequest.objects.get(), "approve")
        self.report(TODAY + timedelta(days=1), reason="Doctor")
        self.decide(LessonChangeRequest.objects.get(status="pending"), "reject")
        AssessmentCalendarException.objects.create(schedule=self.schedule, date=TODAY + timedelta(days=2),
                                                   action="cancelled", reason="Navruz", changed_by=self.manager)
        month = TODAY.strftime("%Y-%m")
        self.client.force_login(self.manager)
        page = self.client.get(reverse("manager_lesson_changes_report") + f"?month={month}")
        self.assertEqual(page.status_code, 200)
        counts = page.context["counts"]
        if (TODAY + timedelta(days=2)).month == TODAY.month and (TODAY + timedelta(days=1)).month == TODAY.month:
            self.assertEqual((counts["covered"], counts["rejected"], counts["manager"]), (1, 1, 1))
            self.assertContains(page, "Navruz")
        self.assertContains(page, "Conference")

        export = self.client.get(reverse("manager_lesson_changes_xlsx") + f"?month={month}")
        self.assertEqual(export["Content-Type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        from openpyxl import load_workbook

        book = load_workbook(BytesIO(export.content))
        self.assertEqual(book.sheetnames, ["By Teacher", "All Changes"])
        self.assertIn("Aziz", [row[0] for row in book["By Teacher"].iter_rows(min_row=2, values_only=True)])

    def test_only_managers_see_reports_and_decide(self):
        self.report()
        self.client.force_login(self.aziz)
        self.assertEqual(self.client.get(reverse("manager_lesson_changes_report")).status_code, 403)
        self.assertEqual(self.client.get(reverse("manager_lesson_changes_xlsx")).status_code, 403)
        response = self.client.post(reverse("manager_decide_lesson_change", args=[LessonChangeRequest.objects.get().pk]),
                                    {"decision": "approve"})
        self.assertEqual(response.status_code, 403)

    def test_manager_page_lists_waiting_requests(self):
        self.report()
        self.client.force_login(self.manager)
        page = self.client.get(reverse("manager_assessment_schedules"))
        self.assertContains(page, "Requests from teachers")
        self.assertContains(page, "1 waiting")
        self.assertContains(page, "I am ill")
