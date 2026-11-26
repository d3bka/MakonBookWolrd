"""V116: the student calendar and its .ics feed for Google / Apple Calendar."""
from datetime import date, datetime, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.integrations.hollihop.schedules import plan_for_edunit
from apps.ratings.models import AssessmentCalendarException, AssessmentSchedule
from apps.sat.calendar_models import StudentCalendarFeed
from apps.sat.event_registration_models import EventRegistration
from apps.sat.models import (
    Classroom, ClassroomHomeworkAssignment, ClassroomHomeworkSubmission, ClassroomMembership, GlobalEvent,
    OfficialSatDate, Test,
)
from apps.sat.student_calendar import events_for, ics_feed

MONDAY = date(2026, 11, 23)


def at(day, hour, minute=0):
    return timezone.make_aware(datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute))


class CalendarTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("v116_teacher", password="x")
        self.kid = User.objects.create_user("v116_kid", password="x", first_name="Aziz")
        self.classroom = Classroom.objects.create(teacher=self.teacher, name="SAT Evening")
        ClassroomMembership.objects.create(classroom=self.classroom, user=self.kid, role="student", status="approved")
        self.schedule = AssessmentSchedule.objects.create(
            classroom=self.classroom, teacher=self.teacher, weekdays=[1, 3, 5], starts_on=MONDAY - timedelta(days=30),
            lesson_times={"1": ["18:00", "19:30"], "3": ["18:00", "19:30"]},
        )

    def week(self):
        return events_for(self.kid, MONDAY, MONDAY + timedelta(days=6))

    def test_lessons_from_the_schedule_with_times_cancellations_and_extra_days(self):
        AssessmentCalendarException.objects.create(schedule=self.schedule, date=MONDAY + timedelta(days=2), action="cancelled")
        AssessmentCalendarException.objects.create(schedule=self.schedule, date=MONDAY + timedelta(days=5), action="added")
        lessons = [e for e in self.week() if e.kind == "lesson"]
        self.assertEqual([(e.day.isoweekday(), e.subtitle) for e in lessons],
                         [(1, ""), (3, "No lesson (cancelled)"), (5, ""), (6, "Extra lesson")])
        monday = lessons[0]
        self.assertEqual((timezone.localtime(monday.start).hour, timezone.localtime(monday.end).strftime("%H:%M")), (18, "19:30"))
        self.assertTrue(lessons[2].all_day)  # Friday: no time from Hollihop

    def test_second_teacher_of_the_class_does_not_double_the_lessons(self):
        other = User.objects.create_user("v116_teacher2", password="x")
        AssessmentSchedule.objects.create(classroom=self.classroom, teacher=other, weekdays=[1], starts_on=MONDAY)
        self.assertEqual(sum(1 for e in self.week() if e.kind == "lesson" and e.day == MONDAY), 1)

    def test_homework_exams_and_sat_dates(self):
        mine = ClassroomHomeworkAssignment.objects.create(
            classroom=self.classroom, created_by=self.teacher, title="Words in context", assignment_type="file",
            due_at=at(MONDAY + timedelta(days=1), 23, 59),
        )
        done = ClassroomHomeworkAssignment.objects.create(
            classroom=self.classroom, created_by=self.teacher, title="DAY7", assignment_type="file",
            due_at=at(MONDAY + timedelta(days=3), 20),
        )
        ClassroomHomeworkSubmission.objects.create(assignment=done, student=self.kid, status="submitted")
        someone_else = ClassroomHomeworkAssignment.objects.create(
            classroom=self.classroom, created_by=self.teacher, title="Only for Malika", assignment_type="file",
            assign_all=False, due_at=at(MONDAY + timedelta(days=2), 20),
        )
        someone_else.assigned_students.add(User.objects.create_user("v116_malika", password="x"))
        event = GlobalEvent.objects.create(title="December Mock", slug="v116-mock", test=Test.objects.create(name="MOCK"),
                                           status="scheduled", start_at=at(MONDAY + timedelta(days=5), 9),
                                           end_at=at(MONDAY + timedelta(days=5), 13))
        EventRegistration.objects.create(event=event, user=self.kid, participant_type="makonbook", full_name="Aziz",
                                         email="aziz@example.com", status=EventRegistration.STATUS_CONFIRMED)
        OfficialSatDate.objects.create(date=MONDAY + timedelta(days=5))
        events = {(e.kind, e.title): e for e in self.week()}
        self.assertFalse(events[("homework", "Words in context")].done)
        self.assertTrue(events[("homework", "DAY7")].done)
        self.assertNotIn(("homework", "Only for Malika"), events)
        self.assertEqual(timezone.localtime(events[("exam", "December Mock")].start).hour, 9)
        self.assertIn(("sat", "SAT test day"), events)

    def test_ics_feed(self):
        ClassroomHomeworkAssignment.objects.create(
            classroom=self.classroom, created_by=self.teacher, title="Grammar, part 1; commas", assignment_type="file",
            due_at=timezone.now() + timedelta(days=2),
        )
        feed = ics_feed(self.kid)
        self.assertTrue(feed.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertTrue(feed.endswith("END:VCALENDAR\r\n"))
        self.assertIn("SUMMARY:Homework due: Grammar\\, part 1\\; commas", feed)
        self.assertIn("SUMMARY:SAT Evening", feed)
        self.assertRegex(feed, r"DTSTART:\d{8}T130000Z")       # 18:00 in Tashkent
        self.assertTrue(all(len(line.encode()) <= 75 for line in feed.split("\r\n")))

    def test_feed_url_works_without_login_and_reset_kills_the_old_link(self):
        self.client.force_login(self.kid)
        page = self.client.get(reverse("student_calendar_root"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Google Calendar")
        self.assertContains(page, 'data-nav-key="calendar"')
        token = StudentCalendarFeed.objects.get(user=self.kid).token
        self.assertContains(page, f"webcal://")
        self.client.logout()
        response = self.client.get(reverse("student_calendar_feed", args=[token]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/calendar; charset=utf-8")
        self.client.force_login(self.kid)
        self.client.post(reverse("student_calendar_root"), {"action": "reset_link"})
        self.client.logout()
        self.assertEqual(self.client.get(reverse("student_calendar_feed", args=[token])).status_code, 404)
        self.assertEqual(self.client.get(reverse("student_calendar_feed", args=["nope"])).status_code, 404)

    def test_month_navigation(self):
        self.client.force_login(self.kid)
        page = self.client.get(reverse("student_calendar_root"), {"month": "2027-02"})
        self.assertContains(page, "February 2027")
        self.assertContains(page, "?month=2027-01")
        self.assertContains(page, "?month=2027-03")
        self.assertEqual(self.client.get(reverse("student_calendar_root"), {"month": "junk"}).status_code, 200)


class HollihopLessonTimeTests(TestCase):
    def test_times_per_weekday_come_from_schedule_items(self):
        today = date(2026, 11, 26)
        plan = plan_for_edunit({"ScheduleItems": [
            {"Weekdays": 5, "BeginTime": "14:00", "EndTime": "16:00:00", "TeacherIds": [1], "BeginDate": "2026-09-01"},
            {"Weekdays": 32, "BeginTime": "10:30", "EndTime": "12:00", "TeacherIds": [1], "BeginDate": "2026-09-01"},
            {"Weekdays": 16, "BeginTime": "", "TeacherIds": [1], "BeginDate": "2026-09-01"},
        ]}, today=today)
        self.assertEqual(plan[1]["times"], {"1": ["14:00", "16:00"], "3": ["14:00", "16:00"], "6": ["10:30", "12:00"]})
        self.assertEqual(plan[1]["weekdays"], {1, 3, 5, 6})
