"""V107: two assessments per student per week (any lesson days), 2,000 UZS per missing one,
and the homework check at every lesson (default: everyone did it)."""
from datetime import date, datetime, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import Classroom, ClassroomMembership
from apps.sat.student_attention import attention_rows

from .assessment_policy import settle_missed_assessments, students_due_today
from .models import AssessmentObligation, AssessmentPenalty, AssessmentSchedule, LessonHomeworkCheck, RatingAssessment

TZ = ZoneInfo("Asia/Tashkent")


def at(day, hour=12):
    return datetime.combine(day, time(hour, 0), TZ)


class Base(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("v107_teacher", password="x", first_name="Dilnoza")
        self.teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        self.manager = User.objects.create_user("v107_manager", password="x")
        self.manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.classroom = Classroom.objects.create(teacher=self.teacher, name="SAT V107")
        self.students = []
        for name in ("Aziz", "Bekzod", "Malika"):
            user = User.objects.create_user(f"v107_{name.lower()}", password="x", first_name=name)
            ClassroomMembership.objects.create(classroom=self.classroom, user=user, role="student", status="approved",
                                               approved_at=timezone.now() - timedelta(days=60))
            self.students.append(user)
        self.today = timezone.localdate()

    def assess(self, student, day, assessed_day=None):
        return RatingAssessment.objects.create(
            classroom=self.classroom, teacher=self.teacher, student=student, lesson_date=day,
            assessed_at=at(assessed_day or day), homework=8, progress=8, activity=8, attendance=8, behavior=8,
        )


@patch("apps.ratings.assessment_policy.WEEKLY_RULE_FROM", date(2000, 1, 1))
class WeeklyRuleTests(Base):
    def setUp(self):
        super().setUp()
        self.monday = self.today - timedelta(days=self.today.weekday() + 7)  # last week, already closed
        self.days = [self.monday, self.monday + timedelta(days=2), self.monday + timedelta(days=4)]  # Mon, Wed, Fri
        self.schedule = AssessmentSchedule.objects.create(classroom=self.classroom, teacher=self.teacher,
                                                          weekdays=[1, 3, 5], starts_on=self.monday - timedelta(days=30))
        for day in self.days:
            for student in self.students:
                AssessmentObligation.objects.create(schedule=self.schedule, student=student, lesson_date=day)

    def test_any_two_lessons_a_week(self):
        aziz, bekzod, malika = self.students
        self.assess(aziz, self.days[0])
        self.assess(aziz, self.days[2])  # two on any days: no fine
        self.assess(bekzod, self.days[1])  # one: one fine
        self.assess(malika, self.days[0], assessed_day=self.days[0] + timedelta(days=1))  # next day: does not count
        fines = settle_missed_assessments(cutoff=self.today)
        per_student = {}
        for fine in fines:
            per_student[fine.obligation.student.first_name] = per_student.get(fine.obligation.student.first_name, 0) + 1
            self.assertEqual(fine.amount_uzs, 2000)
        self.assertEqual(per_student, {"Bekzod": 1, "Malika": 2})
        self.assertEqual(settle_missed_assessments(cutoff=self.today), [])  # re-runs add nothing

    def test_the_week_is_settled_only_after_sunday(self):
        sunday = self.monday + timedelta(days=6)
        self.assertEqual(settle_missed_assessments(cutoff=sunday), [])
        self.assertEqual(len(settle_missed_assessments(cutoff=sunday + timedelta(days=1))), 6)

    def test_a_week_with_one_lesson_needs_one_assessment(self):
        AssessmentObligation.objects.filter(lesson_date__in=self.days[1:]).delete()
        self.assess(self.students[0], self.days[0])
        fines = settle_missed_assessments(cutoff=self.today)
        self.assertEqual(sorted(f.obligation.student.first_name for f in fines), ["Bekzod", "Malika"])

    def test_cancelled_lessons_do_not_count(self):
        from .models import AssessmentCalendarException

        AssessmentCalendarException.objects.create(schedule=self.schedule, date=self.days[1], action="cancelled")
        AssessmentCalendarException.objects.create(schedule=self.schedule, date=self.days[2], action="cancelled")
        self.assess(self.students[0], self.days[0])
        self.assertEqual(len(settle_missed_assessments(cutoff=self.today)), 2)  # one lesson left: one each

    def test_old_fines_count_and_are_not_doubled(self):
        bekzod = self.students[1]
        old = AssessmentObligation.objects.get(student=bekzod, lesson_date=self.days[0])
        AssessmentPenalty.objects.create(obligation=old, amount_uzs=5000)  # from the old daily rule
        fines = [f for f in settle_missed_assessments(cutoff=self.today) if f.obligation.student == bekzod]
        self.assertEqual(len(fines), 1)  # two missing, one already fined
        self.assertEqual(AssessmentPenalty.objects.get(obligation=old).amount_uzs, 5000)


class ReminderTests(Base):
    def test_due_only_when_the_remaining_lessons_are_not_enough(self):
        monday = self.today - timedelta(days=self.today.weekday()) + timedelta(days=7)  # next week
        schedule = AssessmentSchedule.objects.create(classroom=self.classroom, teacher=self.teacher,
                                                     weekdays=[1, 3, 5], starts_on=self.today)
        wednesday, friday = monday + timedelta(days=2), monday + timedelta(days=4)
        for day in (monday, wednesday, friday):
            for student in self.students:
                AssessmentObligation.objects.create(schedule=schedule, student=student, lesson_date=day)
        self.assertEqual(students_due_today(schedule, monday), [])  # three lessons left, two needed
        aziz = self.students[0]
        self.assess(aziz, monday)
        due_wednesday = students_due_today(schedule, wednesday)
        self.assertNotIn(aziz.id, due_wednesday)  # needs one, two lessons left
        self.assertEqual(len(due_wednesday), 2)  # the others need two with two lessons left
        self.assertIn(aziz.id, students_due_today(schedule, friday))  # last chance for the second one


class HomeworkCheckTests(Base):
    def setUp(self):
        super().setUp()
        self.schedule = AssessmentSchedule.objects.create(classroom=self.classroom, teacher=self.teacher,
                                                          weekdays=[self.today.isoweekday()], starts_on=self.today)
        self.url = reverse("teacher_save_homework_check_root", args=[self.classroom.id])

    def test_teacher_marks_who_did_not_do_it_and_everyone_sees_it(self):
        aziz, bekzod, malika = self.students
        self.client.force_login(self.teacher)
        page = self.client.get(reverse("teacher_classroom_assessments_root", args=[self.classroom.id]))
        self.assertContains(page, "Homework check")
        self.assertContains(page, "counts as everyone did it")
        self.assertContains(page, "0/1 this week")

        self.client.post(self.url, {"not_done": [bekzod.id, "999999"]})
        check = LessonHomeworkCheck.objects.get(classroom=self.classroom, lesson_date=self.today)
        self.assertEqual(list(check.misses.values_list("student_id", flat=True)), [bekzod.id])
        page = self.client.get(reverse("teacher_classroom_assessments_root", args=[self.classroom.id]))
        self.assertContains(page, "1 not done")

        self.client.force_login(bekzod)
        self.assertContains(self.client.get(reverse("rating_home")), "Homework at lessons")
        self.assertEqual(len(self.client.get(reverse("rating_home")).context["lesson_homework_misses"]), 1)
        self.client.force_login(aziz)
        self.assertContains(self.client.get(reverse("rating_home")), "You did the homework for every lesson")

        rows, _ = attention_rows([self.classroom])
        reasons = {r["student"].first_name: [x["kind"] for x in r["reasons"]] for r in rows}
        self.assertNotIn("Bekzod", reasons)  # one miss alone is a weak reason
        yesterday_check = LessonHomeworkCheck.objects.create(classroom=self.classroom, teacher=self.teacher, lesson_date=self.today - timedelta(days=2))
        yesterday_check.misses.create(student=bekzod)
        rows, _ = attention_rows([self.classroom])
        self.assertIn("lesson_homework", {r["student"].first_name: [x["kind"] for x in r["reasons"]] for r in rows}["Bekzod"])

        self.client.force_login(self.manager)
        report = self.client.get(reverse("manager_assessment_report"))
        self.assertContains(report, "Homework at lessons")
        self.assertContains(report, "2,000 UZS")
        self.assertEqual(report.context["homework_rows"][0]["misses"], 2)

        self.client.force_login(self.teacher)
        self.client.post(self.url, {})  # everyone did it after all
        self.assertFalse(check.misses.exists())

    def test_only_on_lesson_days_and_only_the_class_teacher(self):
        other = User.objects.create_user("v107_other", password="x")
        other.groups.add(Group.objects.get(name="Teacher"))
        self.client.force_login(other)
        self.assertEqual(self.client.post(self.url, {"not_done": [self.students[0].id]}).status_code, 403)
        AssessmentSchedule.objects.filter(pk=self.schedule.pk).update(weekdays=[self.today.isoweekday() % 7 + 1])
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.post(self.url, {"not_done": [self.students[0].id]}).status_code, 403)
        self.assertFalse(LessonHomeworkCheck.objects.exists())
