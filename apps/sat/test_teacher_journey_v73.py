"""V73 A-to-Z: teacher classroom management at the view level (these views had no tests)."""
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import (
    ChatMessage, Classroom, ClassroomHomeworkAssignment, ClassroomMembership, MakonNotification,
    StudentSectionAccess, Test,
)


def teacher(name):
    user = User.objects.create_user(name, password="x", first_name=name.title(), last_name="T")
    user.groups.add(Group.objects.get_or_create(name="Teacher")[0])
    return user


class TeacherClassroomJourneyTests(TestCase):
    def setUp(self):
        self.teacher = teacher("tj_teacher")
        self.other = teacher("tj_other")
        self.classroom = Classroom.objects.create(teacher=self.teacher, name="SAT Group A", is_active=True)
        self.kid = User.objects.create_user("tj_kid", password="x", first_name="Kid", last_name="One")
        self.newcomer = User.objects.create_user("tj_new", password="x", first_name="New", last_name="Comer")
        self.member = ClassroomMembership.objects.create(classroom=self.classroom, user=self.kid, role="student",
                                                         status="approved", approved_at=timezone.now())
        self.pending = ClassroomMembership.objects.create(classroom=self.classroom, user=self.newcomer, role="student",
                                                          status="pending")

    def test_join_requests_page_lists_pending_students(self):
        self.client.force_login(self.teacher)
        page = self.client.get(reverse("classroom_join_requests", args=[self.classroom.pk]))
        self.assertContains(page, "New Comer")
        # V73: a pending request can be rejected from the page, not only approved
        self.assertContains(page, reverse("teacher_reject_join_request_root", args=[self.classroom.pk, self.pending.pk]))
        self.assertContains(page, reverse("teacher_approve_join_request_root", args=[self.classroom.pk, self.pending.pk]))

    def test_approve_and_reject_requests_notify_the_student(self):
        self.client.force_login(self.teacher)
        self.client.post(reverse("reject_join_request", args=[self.classroom.pk, self.pending.pk]))
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, "rejected")
        self.assertTrue(MakonNotification.objects.filter(user=self.newcomer, message__icontains="not approved").exists())
        # a rejected request cannot be approved by replaying the old link... but a fresh request can be
        self.pending.status = "pending"
        self.pending.save()
        self.client.post(reverse("approve_join_request", args=[self.classroom.pk, self.pending.pk]))
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, "approved")

    def test_remove_student_and_cannot_remove_twice(self):
        self.client.force_login(self.teacher)
        self.client.post(reverse("remove_student_from_classroom", args=[self.classroom.pk, self.kid.pk]))
        self.member.refresh_from_db()
        self.assertEqual(self.member.status, "removed")
        response = self.client.post(reverse("remove_student_from_classroom", args=[self.classroom.pk, self.kid.pk]), follow=True)
        self.assertContains(response, "already removed")

    def test_section_access_per_student(self):
        self.client.force_login(self.teacher)
        url = reverse("update_student_section_access", args=[self.classroom.pk, self.kid.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {"sections": ["vocabulary"]})
        access = {a.section: a.has_access for a in StudentSectionAccess.objects.filter(membership=self.member)}
        self.assertTrue(access["vocabulary"])
        self.assertFalse(access["admissions"])
        self.assertFalse(access["practice_tests"])

    def test_practice_test_access_per_student(self):
        Test.objects.create(name="TJ DAY1", is_available=True)
        self.client.force_login(self.teacher)
        url = reverse("update_student_practice_test_access", args=[self.classroom.pk, self.kid.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {"access_mode": "selected", "tests": ["TJ DAY1"]})
        self.assertEqual(response.status_code, 302)

    def test_chat_message_can_be_deleted_by_the_teacher_only(self):
        msg = ChatMessage.objects.create(classroom=self.classroom, sender=self.kid, message="hello")
        url = reverse("delete_classroom_message", args=[self.classroom.pk, msg.pk])
        self.client.force_login(self.kid)
        self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertTrue(ChatMessage.objects.filter(pk=msg.pk).exists())
        self.client.force_login(self.teacher)
        response = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ChatMessage.objects.filter(pk=msg.pk, is_deleted=False).exists()
                         if hasattr(ChatMessage, "is_deleted") else ChatMessage.objects.filter(pk=msg.pk).exists())

    def test_homework_delete_from_the_hub_modal(self):
        hw = ClassroomHomeworkAssignment.objects.create(classroom=self.classroom, created_by=self.teacher,
                                                        title="Vocab week 1", assignment_type="vocabulary_unit")
        url = reverse("teacher_homework_root")
        self.client.force_login(self.other)  # another teacher: not found, nothing deleted
        response = self.client.post(url, {"action": "delete", "assignment_id": hw.pk}, HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                                    HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 404)
        self.assertTrue(ClassroomHomeworkAssignment.objects.filter(pk=hw.pk).exists())
        self.client.force_login(self.teacher)
        response = self.client.post(url, {"action": "delete", "assignment_id": hw.pk}, HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                                    HTTP_ACCEPT="application/json")
        self.assertEqual(response.json()["ok"], True)
        self.assertFalse(ClassroomHomeworkAssignment.objects.filter(pk=hw.pk).exists())

    def test_another_teacher_cannot_manage_this_classroom(self):
        self.client.force_login(self.other)
        for name, args in (
            ("classroom_join_requests", [self.classroom.pk]),
            ("update_student_section_access", [self.classroom.pk, self.kid.pk]),
            ("update_student_practice_test_access", [self.classroom.pk, self.kid.pk]),
        ):
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 403, name)
        self.client.post(reverse("approve_join_request", args=[self.classroom.pk, self.pending.pk]))
        self.client.post(reverse("remove_student_from_classroom", args=[self.classroom.pk, self.kid.pk]))
        self.pending.refresh_from_db()
        self.member.refresh_from_db()
        self.assertEqual((self.pending.status, self.member.status), ("pending", "approved"))
