"""V102: "Needs attention" lists students who miss homework or lessons, score lower or stopped visiting."""
from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.integrations.models import HollihopAttendance
from apps.ratings.models import UserActivityDay
from apps.sat.models import (
    Classroom, ClassroomHomeworkAssignment, ClassroomHomeworkSubmission, ClassroomMembership,
    StudentAttentionSnooze, Test, TestReview,
)
from apps.sat.student_attention import attention_rows


class AttentionTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        teacher_group, _ = Group.objects.get_or_create(name="Teacher")
        self.teacher = User.objects.create_user("na_teacher", password="x", first_name="Dilnoza")
        self.teacher.groups.add(teacher_group)
        self.classroom = Classroom.objects.create(teacher=self.teacher, name="SAT Evening")
        self.students = {}
        for name in ("Aziz", "Bekzod", "Malika", "Sardor"):
            user = User.objects.create_user(f"na_{name.lower()}", password="x", first_name=name)
            ClassroomMembership.objects.create(classroom=self.classroom, user=user, role="student", status="approved", approved_at=self.now - timedelta(days=60))
            UserActivityDay.objects.create(user=user, date=timezone.localdate(), last_seen_at=self.now)
            self.students[name] = user

    def homework(self, title, days_ago, **extra):
        return ClassroomHomeworkAssignment.objects.create(
            classroom=self.classroom, created_by=self.teacher, title=title, assignment_type="file",
            attachment="classroom_homework/x.pdf", due_at=self.now - timedelta(days=days_ago), **extra,
        )

    def done(self, assignment, student, verdict=""):
        ClassroomHomeworkSubmission.objects.update_or_create(
            assignment=assignment, student=student,
            defaults={"status": "submitted" if verdict != "not_done" else "not_started", "teacher_verdict": verdict, "submitted_at": self.now},
        )

    def rows(self):
        rows, snoozed = attention_rows([self.classroom], now=self.now)
        return {r["student"].first_name: r for r in rows}, snoozed

    def test_missed_homework_and_teacher_verdicts(self):
        a, b, c = self.homework("Worksheet 1", 10), self.homework("Worksheet 2", 5), self.homework("Worksheet 3", 2)
        for student in self.students.values():
            for hw in (a, b, c):
                self.done(hw, student)
        aziz, bekzod = self.students["Aziz"], self.students["Bekzod"]
        ClassroomHomeworkSubmission.objects.filter(student=aziz, assignment__in=[a, b]).delete()  # never did two
        self.done(c, bekzod, "not_done")  # pressed Done earlier, the teacher found it was not done
        self.done(a, bekzod, "partial")
        self.done(b, bekzod, "partial")
        future = self.homework("Not due yet", -3)  # nobody did it, but it is not late
        rows, _ = self.rows()
        self.assertEqual(set(rows), {"Aziz", "Bekzod"})
        self.assertEqual(rows["Aziz"]["reasons"][0]["title"], "2 homework missed")
        self.assertIn("Worksheet 1", rows["Aziz"]["reasons"][0]["detail"])
        kinds = {r["kind"] for r in rows["Bekzod"]["reasons"]}
        self.assertEqual(kinds, {"homework", "partial"})  # 1 missed + 2 partly done
        self.assertTrue(future.pk)

    def test_homework_for_selected_students_only(self):
        hw1 = self.homework("Extra 1", 3, assign_all=False)
        hw2 = self.homework("Extra 2", 2, assign_all=False)
        for hw in (hw1, hw2):
            hw.assigned_students.add(self.students["Malika"])
        rows, _ = self.rows()
        self.assertEqual(set(rows), {"Malika"})

    def test_absences_scores_and_inactivity(self):
        for day, status in ((3, "absent"), (6, "absent"), (9, "absent"), (12, "present")):
            HollihopAttendance.objects.create(
                student=self.students["Aziz"], classroom=self.classroom, date=timezone.localdate() - timedelta(days=day),
                status=status, external_key=f"att-{day}",
            )
        test = Test.objects.create(name="DAY12")
        for days_ago, score in ((20, 30), (14, 32), (7, 29), (1, 18)):
            review = TestReview.objects.create(test=test, user=self.students["Bekzod"], score=score, key=f"k{days_ago}")
            TestReview.objects.filter(pk=review.pk).update(created_at=self.now - timedelta(days=days_ago))
        UserActivityDay.objects.filter(user=self.students["Malika"]).update(last_seen_at=self.now - timedelta(days=20))
        rows, _ = self.rows()
        self.assertEqual(rows["Aziz"]["reasons"][0]["title"], "Missed 3 of 4 lessons")
        self.assertEqual(rows["Aziz"]["level"], "medium")
        self.assertEqual(rows["Bekzod"]["reasons"][0]["detail"], "DAY12: 18, usually about 30")
        self.assertNotIn("Malika", rows)  # only inactive: one weak reason is not enough
        self.homework("Essay", 4)
        rows, _ = self.rows()
        self.assertEqual({r["kind"] for r in rows["Malika"]["reasons"]}, {"homework", "inactive"})

    def test_teacher_page_snooze_and_unsnooze(self):
        for name in ("Essay 1", "Essay 2"):
            self.homework(name, 3)
        self.client.force_login(self.teacher)
        url = reverse("teacher_attention_root")
        page = self.client.get(url)
        self.assertContains(page, "Needs attention")
        self.assertContains(page, "2 homework missed")
        self.assertEqual(page.context["counts"]["listed"], 4)
        self.assertEqual(page.context["staff_workspace_mode"], "teacher")

        aziz = self.students["Aziz"]
        self.client.post(url, {"action": "snooze", "classroom": self.classroom.pk, "student": aziz.pk, "note": "Called the parent"})
        snooze = StudentAttentionSnooze.objects.get(student=aziz)
        self.assertEqual((snooze.note, snooze.snoozed_by), ("Called the parent", self.teacher))
        page = self.client.get(url)
        self.assertEqual(page.context["counts"]["listed"], 3)
        self.assertContains(page, "Called the parent")

        self.client.post(url, {"action": "unsnooze", "classroom": self.classroom.pk, "student": aziz.pk})
        self.assertFalse(StudentAttentionSnooze.objects.exists())

        StudentAttentionSnooze.objects.create(classroom=self.classroom, student=aziz, until=self.now - timedelta(days=1))
        self.assertEqual(self.client.get(url).context["counts"]["listed"], 4)  # an old snooze no longer hides

    def test_other_teachers_and_students_are_kept_out(self):
        other = User.objects.create_user("na_other", password="x")
        other.groups.add(Group.objects.get(name="Teacher"))
        Classroom.objects.create(teacher=other, name="Other class")
        self.homework("Essay 1", 3)
        self.homework("Essay 2", 2)
        self.client.force_login(other)
        page = self.client.get(reverse("teacher_attention_root"))
        self.assertEqual(page.context["counts"]["listed"], 0)
        response = self.client.post(reverse("teacher_attention_root"), {"action": "snooze", "classroom": self.classroom.pk, "student": self.students["Aziz"].pk})
        self.assertEqual(response.status_code, 403)
        self.client.force_login(self.students["Aziz"])
        self.assertEqual(self.client.get(reverse("teacher_attention_root")).status_code, 403)
        self.assertEqual(self.client.get(reverse("manager_attention_root")).status_code, 403)

    def test_manager_sees_the_whole_school(self):
        manager = User.objects.create_user("na_manager", password="x")
        manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.homework("Essay 1", 3)
        self.homework("Essay 2", 2)
        Classroom.objects.create(teacher=self.teacher, name="Archived", is_active=False)
        self.client.force_login(manager)
        page = self.client.get(reverse("manager_attention_root"))
        self.assertEqual(page.context["counts"]["listed"], 4)
        self.assertEqual(page.context["staff_workspace_mode"], "manager")
        self.assertContains(page, "Dilnoza")  # the teacher filter and the teacher on each card
        filtered = self.client.get(reverse("manager_attention_root"), {"teacher": 999999})
        self.assertEqual(filtered.context["counts"]["listed"], 0)
