"""V73 A-to-Z: support lessons after booking — teacher controls, student cancel/feedback, availability."""
from datetime import time, timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import (
    Classroom, ClassroomMembership, MakonNotification, SupportLessonBooking, SupportLessonSession, SupportLessonTitle,
    SupportLessonTopic, SupportTeacherAvailability, SupportTeacherProfile, SupportTeacherReview,
)


class SupportLessonJourneyTests(TestCase):
    def setUp(self):
        group = Group.objects.get_or_create(name="Support Teacher")[0]
        self.mentor = User.objects.create_user("sj_mentor", password="x", first_name="Amina")
        self.mentor.groups.add(group)
        self.profile = SupportTeacherProfile.objects.create(
            user=self.mentor, display_name="Amina", subjects="SAT Math", meeting_link="https://meet.example.com/a",
            min_booking_notice_hours=0, cancellation_notice_hours=2, is_active=True,
        )
        self.other_mentor = User.objects.create_user("sj_mentor2", password="x")
        self.other_mentor.groups.add(group)
        SupportTeacherProfile.objects.create(user=self.other_mentor, display_name="Other", is_active=True)

        teacher = User.objects.create_user("sj_teacher", password="x")
        teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        classroom = Classroom.objects.create(teacher=teacher, name="SJ class")
        self.kid = User.objects.create_user("sj_kid", password="x")
        self.kid2 = User.objects.create_user("sj_kid2", password="x")
        for kid in (self.kid, self.kid2):
            ClassroomMembership.objects.create(classroom=classroom, user=kid, role="student", status="approved",
                                               approved_at=timezone.now())
        self.title = SupportLessonTitle.objects.create(name="SJ Math", is_active=True)
        self.topic = SupportLessonTopic.objects.create(title=self.title, name="SJ Linear equations", is_active=True)

    def booking(self, student=None, status=SupportLessonBooking.STATUS_SCHEDULED, starts_in=timedelta(days=1), session=None):
        start = timezone.now() + starts_in
        return SupportLessonBooking.objects.create(
            teacher=self.profile, student=student or self.kid, lesson_title=self.title, lesson_topic=self.topic,
            start_at=start, end_at=start + timedelta(minutes=45), status=status, session=session,
        )

    # ---------------------------------------------------------------- student side
    def test_student_cancels_in_time_but_not_at_the_last_minute(self):
        early = self.booking()
        self.client.force_login(self.kid)
        self.client.post(reverse("cancel_support_lesson_root", args=[early.id]), {"reason": "exam clash"})
        early.refresh_from_db()
        self.assertEqual((early.status, early.cancelled_by), (SupportLessonBooking.STATUS_CANCELLED, SupportLessonBooking.CANCELLED_BY_STUDENT))
        self.assertTrue(MakonNotification.objects.filter(user=self.mentor, title__icontains="cancelled").exists())

        late = self.booking(starts_in=timedelta(minutes=30), student=self.kid)
        response = self.client.post(reverse("cancel_support_lesson_root", args=[late.id]), follow=True)
        self.assertContains(response, "Online cancellation closes")
        late.refresh_from_db()
        self.assertEqual(late.status, SupportLessonBooking.STATUS_SCHEDULED)

    def test_student_cannot_touch_someone_elses_booking(self):
        theirs = self.booking(student=self.kid2)
        self.client.force_login(self.kid)
        self.assertEqual(self.client.post(reverse("cancel_support_lesson_root", args=[theirs.id])).status_code, 404)
        self.assertEqual(self.client.post(reverse("leave_support_lesson_feedback_root", args=[theirs.id]), {"rating": 5}).status_code, 404)

    def test_feedback_once_after_a_completed_lesson(self):
        done = self.booking(status=SupportLessonBooking.STATUS_COMPLETED, starts_in=-timedelta(hours=3))
        url = reverse("leave_support_lesson_feedback_root", args=[done.id])
        self.client.force_login(self.kid)
        self.client.post(url, {"rating": "9"})
        self.client.post(url, {"rating": "abc"})
        self.assertFalse(SupportTeacherReview.objects.exists())
        self.client.post(url, {"rating": "4", "feedback": "Clear explanations"})
        self.client.post(url, {"rating": "1", "feedback": "again"})
        self.assertEqual(list(SupportTeacherReview.objects.values_list("rating", flat=True)), [4])
        upcoming = self.booking(student=self.kid)
        self.client.post(reverse("leave_support_lesson_feedback_root", args=[upcoming.id]), {"rating": "5"})
        self.assertEqual(SupportTeacherReview.objects.count(), 1)
        self.assertEqual(self.client.get(reverse("my_support_lessons_root")).status_code, 200)

    # ---------------------------------------------------------------- mentor side, single booking
    def test_mentor_marks_no_show_complete_and_cancel(self):
        past = self.booking(starts_in=-timedelta(hours=1))
        future = self.booking(student=self.kid2)
        self.client.force_login(self.mentor)
        url = lambda b: reverse("manage_support_lesson_root", args=[b.id])  # noqa: E731
        self.client.post(url(future), {"action": "no_show"})
        future.refresh_from_db()
        self.assertEqual(future.status, SupportLessonBooking.STATUS_SCHEDULED)  # not before it starts
        self.client.post(url(past), {"action": "no_show"})
        past.refresh_from_db()
        self.assertEqual(past.status, SupportLessonBooking.STATUS_NO_SHOW)
        self.client.post(url(future), {"action": "complete"})
        future.refresh_from_db()
        self.assertEqual(future.status, SupportLessonBooking.STATUS_COMPLETED)
        self.client.post(url(future), {"action": "cancel"})  # completed lessons cannot be cancelled
        future.refresh_from_db()
        self.assertEqual(future.status, SupportLessonBooking.STATUS_COMPLETED)
        self.assertTrue(MakonNotification.objects.filter(user=self.kid, title__icontains="no-show").exists())

    def test_other_mentors_and_students_cannot_manage_a_booking(self):
        booking = self.booking(starts_in=-timedelta(hours=1))
        for who in (self.other_mentor, self.kid):
            self.client.force_login(who)
            response = self.client.post(reverse("manage_support_lesson_root", args=[booking.id]), {"action": "no_show"})
            self.assertEqual(response.status_code, 403)
        booking.refresh_from_db()
        self.assertEqual(booking.status, SupportLessonBooking.STATUS_SCHEDULED)

    def test_redirect_after_managing_stays_on_this_site(self):
        booking = self.booking(starts_in=-timedelta(hours=1))
        self.client.force_login(self.mentor)
        response = self.client.post(reverse("manage_support_lesson_root", args=[booking.id]),
                                    {"action": "complete", "next": "https://evil.example.com/"})
        self.assertNotIn("evil.example.com", response["Location"])

    # ---------------------------------------------------------------- mentor side, group sessions
    def session(self, starts_in=timedelta(days=1)):
        start = timezone.now() + starts_in
        return SupportLessonSession.objects.create(teacher=self.profile, lesson_topic=self.topic, start_at=start,
                                                   end_at=start + timedelta(minutes=45), max_students=10)

    def test_group_session_update_cancel_and_complete(self):
        upcoming = self.session()
        seat = self.booking(session=upcoming)
        self.client.force_login(self.mentor)
        url = reverse("manage_support_session_root", args=[upcoming.id])
        self.client.post(url, {"action": "update", "meeting_link": "javascript:alert(1)"})
        upcoming.refresh_from_db()
        self.assertNotIn("javascript", upcoming.meeting_link)
        self.client.post(url, {"action": "update", "meeting_link": "https://meet.example.com/new", "is_open_for_requests": "on"})
        seat.refresh_from_db()
        self.assertEqual(seat.meeting_link, "https://meet.example.com/new")
        self.client.post(url, {"action": "complete"})  # before it starts: refused
        upcoming.refresh_from_db()
        self.assertEqual(upcoming.status, SupportLessonSession.STATUS_SCHEDULED)
        self.client.post(url, {"action": "cancel", "cancellation_reason": "teacher ill"})
        upcoming.refresh_from_db()
        seat.refresh_from_db()
        self.assertEqual((upcoming.status, seat.status), (SupportLessonSession.STATUS_CANCELLED, SupportLessonBooking.STATUS_CANCELLED))

        finished = self.session(starts_in=-timedelta(hours=2))
        attended = self.booking(session=finished, starts_in=-timedelta(hours=2), student=self.kid2)
        self.client.post(reverse("manage_support_session_root", args=[finished.id]), {"action": "complete"})
        attended.refresh_from_db()
        self.assertEqual(attended.status, SupportLessonBooking.STATUS_COMPLETED)

    def test_another_mentor_cannot_manage_my_session(self):
        mine = self.session()
        self.client.force_login(self.other_mentor)
        response = self.client.post(reverse("manage_support_session_root", args=[mine.id]), {"action": "cancel"})
        self.assertEqual(response.status_code, 403)

    # ---------------------------------------------------------------- availability
    def test_availability_add_and_delete(self):
        self.client.force_login(self.mentor)
        self.client.post(reverse("support_teacher_availability_add_root"), {
            "day_of_week": 2, "start_time": "10:00", "end_time": "12:00", "slot_duration_minutes": 45,
            "buffer_minutes": 15, "is_active": "on",
        })
        window = SupportTeacherAvailability.objects.get(teacher=self.profile)
        self.assertEqual(window.start_time, time(10, 0))
        self.client.post(reverse("support_teacher_availability_add_root"), {
            "day_of_week": 2, "start_time": "12:00", "end_time": "10:00", "slot_duration_minutes": 45, "buffer_minutes": 0,
        })
        self.assertEqual(SupportTeacherAvailability.objects.filter(teacher=self.profile).count(), 1)  # end before start
        self.client.force_login(self.other_mentor)
        self.assertEqual(self.client.post(reverse("support_teacher_availability_delete_root", args=[window.id])).status_code, 404)
        self.client.force_login(self.mentor)
        self.client.post(reverse("support_teacher_availability_delete_root", args=[window.id]))
        self.assertFalse(SupportTeacherAvailability.objects.exists())

    def test_students_cannot_open_the_mentor_workspace(self):
        self.client.force_login(self.kid)
        self.assertEqual(self.client.post(reverse("support_teacher_availability_add_root"), {}).status_code, 403)
        response = self.client.get(reverse("support_teacher_dashboard_root"))
        self.assertNotEqual(response.status_code, 200)
        self.client.force_login(self.mentor)
        self.assertEqual(self.client.get(reverse("support_teacher_dashboard_root")).status_code, 200)
