"""V100: homework as a file — the teacher attaches it, students press Done, the teacher checks."""
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import (
    Classroom, ClassroomHomeworkAssignment, ClassroomHomeworkSubmission, ClassroomMembership, MakonNotification,
)


def pdf(name="worksheet.pdf", size=None):
    return SimpleUploadedFile(name, b"%PDF-1.4 demo" if size is None else b"x" * size, content_type="application/pdf")


class FileHomeworkTests(TestCase):
    def setUp(self):
        group, _ = Group.objects.get_or_create(name="Teacher")
        self.teacher = User.objects.create_user("fhw_teacher", password="x", first_name="Dilnoza")
        self.teacher.groups.add(group)
        self.classroom = Classroom.objects.create(teacher=self.teacher, name="SAT Group V100")
        self.students = []
        for i in range(3):
            user = User.objects.create_user(f"fhw_student{i}", password="x", first_name=f"Student{i}")
            ClassroomMembership.objects.create(classroom=self.classroom, user=user, role="student", status="approved", approved_at=timezone.now())
            self.students.append(user)

    def create(self, **extra):
        self.client.force_login(self.teacher)
        data = {
            "action": "create", "classroom": self.classroom.pk, "assignment_type": "file",
            "title": "Worksheet 3", "instructions": "Do exercises 1-6.", "attachment": pdf(), "assign_all": "1",
        }
        data.update(extra)
        return self.client.post(reverse("teacher_homework_root"), data)

    def test_teacher_creates_file_homework_and_students_get_it(self):
        self.create()
        assignment = ClassroomHomeworkAssignment.objects.get(title="Worksheet 3")
        self.assertEqual(assignment.assignment_type, "file")
        self.assertEqual(assignment.attachment_display_name, "worksheet.pdf")
        self.assertEqual(MakonNotification.objects.filter(type=MakonNotification.TYPE_HOMEWORK).count(), 3)
        hub = self.client.get(reverse("teacher_homework_root"))
        self.assertContains(hub, "worksheet.pdf")
        self.assertContains(hub, reverse("teacher_homework_review_root", args=[assignment.pk]))

        self.client.force_login(self.students[0])
        listing = self.client.get(reverse("student_homework_root"))
        self.assertContains(listing, "Worksheet 3")
        self.assertContains(listing, "bi-paperclip")
        page = self.client.get(reverse("student_homework_launch_root", args=[assignment.pk]))
        self.assertContains(page, "Download")
        self.assertContains(page, assignment.attachment.url)
        self.assertContains(page, "Done")

    def test_files_are_checked(self):
        self.create(attachment=SimpleUploadedFile("evil.html", b"<script>", content_type="text/html"))
        self.create(title="Too big", attachment=pdf(size=ClassroomHomeworkAssignment.FILE_MAX_BYTES + 1))
        self.client.post(reverse("teacher_homework_root"), {
            "action": "create", "classroom": self.classroom.pk, "assignment_type": "file", "title": "No file", "assign_all": "1",
        })
        self.assertFalse(ClassroomHomeworkAssignment.objects.exists())

    def test_student_presses_done_and_can_take_it_back(self):
        self.create()
        assignment = ClassroomHomeworkAssignment.objects.get()
        student = self.students[0]
        self.client.force_login(student)
        self.client.get(reverse("student_homework_launch_root", args=[assignment.pk]))
        self.client.post(reverse("student_homework_file_done_root", args=[assignment.pk]), {"action": "done"})
        submission = ClassroomHomeworkSubmission.objects.get(assignment=assignment, student=student)
        self.assertEqual(submission.status, ClassroomHomeworkSubmission.STATUS_SUBMITTED)
        listing = self.client.get(reverse("student_homework_root"), {"view": "completed"})
        self.assertIn(assignment, listing.context["homework_completed_assignments"])
        self.client.post(reverse("student_homework_file_done_root", args=[assignment.pk]), {"action": "undo"})
        submission.refresh_from_db()
        self.assertEqual(submission.status, ClassroomHomeworkSubmission.STATUS_IN_PROGRESS)

    def test_done_is_locked_after_the_deadline(self):
        self.create()
        assignment = ClassroomHomeworkAssignment.objects.get()
        ClassroomHomeworkAssignment.objects.filter(pk=assignment.pk).update(due_at=timezone.now() - timedelta(hours=1))
        self.client.force_login(self.students[0])
        page = self.client.get(reverse("student_homework_launch_root", args=[assignment.pk]))
        self.assertContains(page, "Deadline closed")
        self.client.post(reverse("student_homework_file_done_root", args=[assignment.pk]), {"action": "done"})
        self.assertFalse(ClassroomHomeworkSubmission.objects.filter(status=ClassroomHomeworkSubmission.STATUS_SUBMITTED).exists())

    def test_teacher_checks_who_really_did_it(self):
        self.create()
        assignment = ClassroomHomeworkAssignment.objects.get()
        a, b, c = self.students
        for student in (a, b):
            self.client.force_login(student)
            self.client.post(reverse("student_homework_file_done_root", args=[assignment.pk]), {"action": "done"})
        self.client.force_login(self.teacher)
        url = reverse("teacher_homework_review_root", args=[assignment.pk])
        page = self.client.get(url)
        self.assertContains(page, "Student0")
        self.assertEqual(page.context["counts"], {"done": 2, "pending": 1})
        MakonNotification.objects.all().delete()
        self.client.post(url, {
            f"verdict_{a.pk}": "done",
            f"verdict_{b.pk}": "partial", f"note_{b.pk}": "Exercises 4-6 missing",
            f"verdict_{c.pk}": "done",  # did it on paper but forgot to press Done
        })
        rows = {s.student_id: s for s in ClassroomHomeworkSubmission.objects.filter(assignment=assignment)}
        self.assertEqual((rows[a.pk].teacher_verdict, rows[a.pk].status), ("done", "submitted"))
        self.assertEqual((rows[b.pk].teacher_verdict, rows[b.pk].teacher_note), ("partial", "Exercises 4-6 missing"))
        self.assertEqual((rows[c.pk].teacher_verdict, rows[c.pk].status, rows[c.pk].reviewed_by), ("done", "submitted", self.teacher))
        self.assertEqual(list(MakonNotification.objects.values_list("user_id", flat=True)), [b.pk])

        self.client.post(url, {f"verdict_{a.pk}": "not_done", f"verdict_{b.pk}": "partial", f"note_{b.pk}": "Exercises 4-6 missing", f"verdict_{c.pk}": "done"})
        rows[a.pk].refresh_from_db()
        self.assertEqual((rows[a.pk].teacher_verdict, rows[a.pk].status), ("not_done", "not_started"))

        self.client.force_login(b)
        page = self.client.get(reverse("student_homework_launch_root", args=[assignment.pk]))
        self.assertContains(page, "partly done")
        self.assertContains(page, "Exercises 4-6 missing")
        self.assertNotContains(page, 'value="undo"')  # checked homework can no longer be changed by the student
        self.client.post(reverse("student_homework_file_done_root", args=[assignment.pk]), {"action": "undo"})
        rows[b.pk].refresh_from_db()
        self.assertEqual(rows[b.pk].status, "submitted")

    def test_other_teachers_and_students_cannot_check(self):
        self.create()
        assignment = ClassroomHomeworkAssignment.objects.get()
        url = reverse("teacher_homework_review_root", args=[assignment.pk])
        other = User.objects.create_user("fhw_other", password="x")
        other.groups.add(Group.objects.get(name="Teacher"))
        for user in (other, self.students[0]):
            self.client.force_login(user)
            self.assertEqual(self.client.post(url, {f"verdict_{self.students[1].pk}": "done"}).status_code, 403)
        self.assertFalse(ClassroomHomeworkSubmission.objects.filter(teacher_verdict="done").exists())

    def test_edit_keeps_the_file_unless_a_new_one_is_sent(self):
        self.create()
        assignment = ClassroomHomeworkAssignment.objects.get()
        old_name = assignment.attachment.name
        base = {"action": "edit", "assignment_id": assignment.pk, "classroom": self.classroom.pk, "assignment_type": "file",
                "title": "Worksheet 3 (fixed)", "preserve_targets": "1", "is_active": "1"}
        self.client.post(reverse("teacher_homework_root"), base)
        assignment.refresh_from_db()
        self.assertEqual((assignment.title, assignment.attachment.name), ("Worksheet 3 (fixed)", old_name))
        self.client.post(reverse("teacher_homework_root"), {**base, "attachment": pdf("worksheet-v2.pdf")})
        assignment.refresh_from_db()
        self.assertEqual(assignment.attachment_display_name, "worksheet-v2.pdf")

    def test_older_homework_types_still_work(self):
        page = self.client.get(reverse("student_homework_root"))
        self.assertEqual(page.status_code, 302)  # login required, unchanged
        self.client.force_login(self.teacher)
        response = self.client.post(reverse("teacher_homework_root"), {
            "action": "create", "classroom": self.classroom.pk, "assignment_type": "vocabulary_unit",
            "title": "Vocab", "vocabulary_unit": "999", "assign_all": "1",
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ClassroomHomeworkAssignment.objects.filter(title="Vocab").exists())  # still needs a unit
