from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from apps.ratings.models import RatingAssessment
from apps.sat.models import (
    Classroom,
    ClassroomHomeworkAssignment,
    ClassroomLesson,
    ClassroomLessonResource,
    ClassroomMembership,
    English_Question,
    MakonNotification,
    StudentPracticeTestAccess,
    StudentSectionAccess,
    SupportTeacherProfile,
    Test,
    TestImportJob,
    TestImportReview,
)


class StaffWorkspaceV50210Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher_group = Group.objects.get_or_create(name="Teacher")[0]
        cls.manager_group = Group.objects.get_or_create(name="Manager")[0]
        cls.support_group = Group.objects.get_or_create(name="Support Teacher")[0]

        cls.teacher = User.objects.create_user(
            username="teacher_v50210", password="pass12345", first_name="Course", last_name="Teacher"
        )
        cls.teacher.groups.add(cls.teacher_group)
        cls.manager = User.objects.create_user(username="manager_v50210", password="pass12345", first_name="Manager")
        cls.manager.groups.add(cls.manager_group)
        cls.student = User.objects.create_user(username="student_v50210", password="pass12345", first_name="First")
        cls.student2 = User.objects.create_user(username="student2_v50210", password="pass12345", first_name="Second")

        cls.classroom = Classroom.objects.create(
            teacher=cls.teacher, name="V50210 SAT", classroom_type=Classroom.CLASSROOM_TYPE_SAT, is_active=True
        )
        cls.membership = ClassroomMembership.objects.create(
            classroom=cls.classroom, user=cls.student, role="student", status="approved"
        )
        cls.membership2 = ClassroomMembership.objects.create(
            classroom=cls.classroom, user=cls.student2, role="student", status="approved"
        )
        cls.test = Test.objects.create(name="DAY2", is_available=True)
        cls.lesson = ClassroomLesson.objects.create(
            classroom=cls.classroom, title="Unit one", order=1, is_published=True, created_by=cls.teacher
        )

    def _homework_payload(self, **overrides):
        payload = {
            "action": "create",
            "submission_token": "v50210-token",
            "classroom": str(self.classroom.pk),
            "assignment_type": ClassroomHomeworkAssignment.TYPE_TEST,
            "title": "Focused SAT homework",
            "instructions": "Finish this test.",
            "test": self.test.pk,
            "assign_all": "1",
        }
        payload.update(overrides)
        return payload

    def test_homework_create_is_idempotent_notifies_and_supports_edit_delete(self):
        self.client.force_login(self.teacher)
        create = self.client.post(reverse("teacher_homework_root"), self._homework_payload())
        self.assertRedirects(create, reverse("teacher_homework_root"), fetch_redirect_response=False)
        assignment = ClassroomHomeworkAssignment.objects.get(title="Focused SAT homework")
        self.assertEqual(MakonNotification.objects.filter(user=self.student, type=MakonNotification.TYPE_HOMEWORK).count(), 1)
        self.assertTrue(StudentPracticeTestAccess.objects.filter(membership=self.membership, test=self.test, has_access=True).exists())

        # Replaying the same browser submission token must not create a duplicate.
        self.client.post(reverse("teacher_homework_root"), self._homework_payload())
        self.assertEqual(ClassroomHomeworkAssignment.objects.filter(title="Focused SAT homework").count(), 1)

        # The compact edit form preserves the original audience and updates the row.
        assignment.assign_all = False
        assignment.save(update_fields=["assign_all"])
        assignment.assigned_students.set([self.student])
        edit = self.client.post(reverse("teacher_homework_root"), self._homework_payload(
            action="edit",
            assignment_id=str(assignment.pk),
            submission_token="",
            title="Updated SAT homework",
            preserve_targets="1",
            is_active="1",
        ))
        self.assertRedirects(edit, reverse("teacher_homework_root"), fetch_redirect_response=False)
        assignment.refresh_from_db()
        self.assertEqual(assignment.title, "Updated SAT homework")
        self.assertFalse(assignment.assign_all)
        self.assertEqual(list(assignment.assigned_students.values_list("pk", flat=True)), [self.student.pk])

        delete = self.client.post(reverse("teacher_homework_root"), {
            "action": "delete", "assignment_id": assignment.pk, "classroom": self.classroom.pk,
        })
        self.assertRedirects(delete, reverse("teacher_homework_root"), fetch_redirect_response=False)
        self.assertFalse(ClassroomHomeworkAssignment.objects.filter(pk=assignment.pk).exists())
        self.assertFalse(MakonNotification.objects.filter(user=self.student, title__startswith="Homework removed:").exists())

    def test_homework_pages_have_live_filters_and_60_item_option(self):
        ClassroomHomeworkAssignment.objects.create(
            classroom=self.classroom, created_by=self.teacher, title="Needle assignment",
            assignment_type=ClassroomHomeworkAssignment.TYPE_TEST, test=self.test, assign_all=True,
        )
        ClassroomHomeworkAssignment.objects.create(
            classroom=self.classroom, created_by=self.teacher, title="Other assignment",
            assignment_type=ClassroomHomeworkAssignment.TYPE_TEST, test=self.test, assign_all=True,
        )

        self.client.force_login(self.teacher)
        teacher_page = self.client.get(reverse("teacher_homework_root"), {"q": "Needle", "per_page": 60})
        self.assertContains(teacher_page, "data-v50211-live-form")
        self.assertContains(teacher_page, "Needle assignment")
        self.assertNotContains(teacher_page, "Other assignment")
        self.assertContains(teacher_page, 'value="60" selected')

        self.client.force_login(self.student)
        student_page = self.client.get(reverse("student_homework_root"), {"q": "Needle", "type": "sat_test"})
        self.assertContains(student_page, "v50210-homework-grid")
        self.assertContains(student_page, "data-v50211-live-form")
        self.assertContains(student_page, "Needle assignment")
        self.assertNotContains(student_page, "Other assignment")

    def test_test_lists_use_natural_day_order_and_drop_days_above_60(self):
        for name in ["DAY10", "DAY1", "DAY60", "DAY61", "ALPHA"]:
            Test.objects.get_or_create(name=name, defaults={"is_available": True})
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("teacher_homework_root"))
        names = [test.name for test in response.context["tests"]]
        self.assertEqual([name for name in names if name.startswith("DAY")], ["DAY1", "DAY2", "DAY10", "DAY60"])
        self.assertNotIn("DAY61", names)
        self.assertIn("ALPHA", names)

        # Student libraries must enforce the same active DAY1..DAY60 window even
        # when a stale/forged access row exists for a later DAY test.
        StudentSectionAccess.objects.update_or_create(
            membership=self.membership, section="practice_tests", defaults={"has_access": True}
        )
        for test in Test.objects.filter(name__in=["DAY1", "DAY2", "DAY10", "DAY60", "DAY61", "ALPHA"]):
            StudentPracticeTestAccess.objects.update_or_create(
                membership=self.membership, test=test, defaults={"has_access": True}
            )
        self.client.force_login(self.student)
        student_library = self.client.get(reverse("practice_tests_root"))
        student_names = [test.name for test in list(student_library.context["active_tests"]) + list(student_library.context["past_tests"])]
        self.assertEqual([name for name in student_names if name.startswith("DAY")], ["DAY1", "DAY2", "DAY10", "DAY60"])
        self.assertNotIn("DAY61", student_names)
        self.assertIn("ALPHA", student_names)

    def test_eclass_test_material_authoring_preview_and_password_do_not_grant_global_access(self):
        # One real question is enough to make the material launchable.
        English_Question.objects.create(
            test=self.test,
            module="module_1",
            number=1,
            question="What is correct?",
            a="A",
            b="B",
            c="C",
            d="D",
            answer="A",
        )
        self.client.force_login(self.teacher)
        add = self.client.post(reverse("teacher_classroom_root", args=[self.classroom.pk]), {
            "course_action": "add_resource",
            "lesson_id": self.lesson.pk,
            "resource_title": "DAY2 checkpoint",
            "resource_type": ClassroomLessonResource.RESOURCE_TEST,
            "test": self.test.pk,
            "access_code": "2468",
            "total_points": "40",
            "score_visibility": ClassroomLessonResource.SCORE_IMMEDIATE,
            "resource_order": "1",
            "is_visible": "1",
        })
        self.assertEqual(add.status_code, 302)
        resource = ClassroomLessonResource.objects.get(lesson=self.lesson, resource_type="test")
        self.assertEqual(resource.total_points, 40)
        self.assertEqual(resource.access_code, "2468")

        self.client.force_login(self.student)
        preview_url = reverse("student_lesson_test_preview_root", args=[self.classroom.pk, resource.pk])
        preview = self.client.get(preview_url)
        self.assertContains(preview, "40")
        self.assertContains(preview, "Questions")
        self.assertContains(preview, ">1<", html=False)
        wrong = self.client.post(preview_url, {"access_code": "wrong"})
        self.assertContains(wrong, "Incorrect access code")
        ok = self.client.post(preview_url, {"access_code": "2468"})
        self.assertRedirects(
            ok,
            reverse("practice_test_start_root", args=[self.test.name]),
            fetch_redirect_response=False,
        )
        # A unit password is session-scoped; it must not silently open the global Tests library.
        self.assertFalse(StudentSectionAccess.objects.filter(membership=self.membership, section="practice_tests", has_access=True).exists())
        self.assertFalse(StudentPracticeTestAccess.objects.filter(membership=self.membership, test=self.test, has_access=True).exists())
        launch = self.client.get(reverse("student_classroom_test_start_root", args=[self.classroom.pk, self.test.pk]))
        self.assertRedirects(
            launch,
            reverse("practice_test_start_root", args=[self.test.name]),
            fetch_redirect_response=False,
        )

        fresh = Client()
        fresh.force_login(self.student)
        blocked = fresh.get(reverse("student_classroom_test_start_root", args=[self.classroom.pk, self.test.pk]))
        self.assertEqual(blocked.status_code, 403)

    def test_empty_eclass_test_material_cannot_start(self):
        empty_test = Test.objects.create(name="DAY8", is_available=True)
        resource = ClassroomLessonResource.objects.create(
            lesson=self.lesson,
            title="Empty checkpoint",
            resource_type=ClassroomLessonResource.RESOURCE_TEST,
            test=empty_test,
            total_points=20,
            is_visible=True,
        )
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_lesson_test_preview_root", args=[self.classroom.pk, resource.pk]))
        self.assertContains(response, "no questions", html=False)
        self.assertNotContains(response, ">Start test<", html=False)

    def test_assessment_deck_saves_every_included_student_atomically(self):
        self.client.force_login(self.teacher)
        payload = {"student_ids": [str(self.student.pk), str(self.student2.pk)]}
        for student in [self.student, self.student2]:
            payload.update({
                f"include_{student.pk}": "1",
                f"homework_{student.pk}": "8.0",
                f"progress_{student.pk}": "8.5",
                f"activity_{student.pk}": "9.0",
                f"attendance_{student.pk}": "10.0",
                f"behavior_{student.pk}": "9.5",
                f"comment_{student.pk}": f"Assessment for {student.username}",
            })
        response = self.client.post(reverse("teacher_save_assessment_deck_root", args=[self.classroom.pk]), payload)
        self.assertRedirects(response, reverse("teacher_classroom_assessments_root", args=[self.classroom.pk]), fetch_redirect_response=False)
        self.assertEqual(RatingAssessment.objects.filter(classroom=self.classroom).count(), 2)
        self.assertEqual(MakonNotification.objects.filter(type=MakonNotification.TYPE_ASSESSMENT).count(), 2)

    def test_access_hub_contains_direct_editors_without_intermediate_manager_button(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("teacher_access_root"))
        self.assertContains(response, f'data-v50210-access-modal="sections-{self.classroom.pk}"')
        self.assertContains(response, f'data-v50210-access-modal="practice-{self.classroom.pk}"')
        self.assertContains(response, reverse("teacher_classroom_section_access_root", args=[self.classroom.pk]))
        self.assertContains(response, reverse("teacher_classroom_practice_access_root", args=[self.classroom.pk]))
        self.assertNotContains(response, "Open manager")

    def test_teacher_sidebar_has_practice_tests_and_directories_use_live_search(self):
        self.client.force_login(self.teacher)
        teacher_home = self.client.get(reverse("teacher_dashboard_root"))
        self.assertContains(teacher_home, reverse("teacher_practice_tests_root"))
        self.assertContains(teacher_home, "Practice Tests")

        self.client.force_login(self.manager)
        main = self.client.get(reverse("manager_teacher_list_root"))
        support = self.client.get(reverse("manager_support_teacher_list_root"))
        published = self.client.get(reverse("manager_managed_test_list_root"))
        for response in [main, support, published]:
            self.assertContains(response, "data-v50211-live-form")
        self.assertNotContains(published, '>Search</button>', html=False)

    def test_support_group_without_profile_is_repaired_before_dashboard_redirect(self):
        support = User.objects.create_user(username="support_noprofile_v50210", password="pass12345")
        support.groups.add(self.support_group)
        self.client.force_login(support)
        response = self.client.get(reverse("student_dashboard_root"))
        self.assertRedirects(response, reverse("support_teacher_dashboard_root"), fetch_redirect_response=False)
        profile = SupportTeacherProfile.objects.get(user=support)
        self.assertTrue(profile.is_active)

    def test_canonical_manager_and_support_import_urls_do_not_expose_sat_prefix(self):
        self.assertEqual(reverse("manager_test_import_list_root"), "/manager/tests-import/")
        self.assertEqual(reverse("manager_managed_test_list_root"), "/manager/tests-import/published/")
        self.assertEqual(reverse("support_teacher_review_list_root"), "/support-teacher/reviewer/")
        self.assertEqual(reverse("notifications_read_root"), "/notifications/read/")
        self.assertEqual(reverse("practice_test_start_root", args=["DAY2"]), "/tests/DAY2/start/")
        self.assertEqual(reverse("practice_test_results_root", args=["DAY2"]), "/tests/DAY2/results/")
        self.assertEqual(
            reverse("practice_test_review_question_root", args=["review-key", "english", "m1", "7"]),
            "/tests/review/review-key/english/m1/7/",
        )
        self.assertEqual(reverse("classroom_practice_tests_root", args=[self.classroom.pk]), f"/classrooms/{self.classroom.pk}/tests/")
        self.assertEqual(
            reverse("teacher_classroom_student_review_root", args=[self.classroom.pk, self.student.pk, "DAY2"]),
            f"/teacher/classrooms/{self.classroom.pk}/progress/student/{self.student.pk}/practice/DAY2/review/",
        )

        support = User.objects.create_user(username="reviewer_v50210", password="pass12345")
        support.groups.add(self.support_group)
        SupportTeacherProfile.objects.create(user=support, display_name="Reviewer", subjects="SAT", is_active=True)
        job = TestImportJob.objects.create(name="Canonical review", created_by=self.manager, status=TestImportJob.STATUS_REVIEW_REQUIRED)
        TestImportReview.objects.create(job=job, reviewer=support)
        self.client.force_login(support)
        response = self.client.get(reverse("support_teacher_review_list_root"))
        self.assertContains(response, reverse("support_teacher_review_detail_root", args=[job.pk]))
        self.assertNotContains(response, f'/manager/tests-import/{job.pk}/')
        self.assertNotContains(response, f'/sat/test-imports/{job.pk}/')

    def test_generic_notification_endpoint_marks_all_notification_types_read(self):
        notice = MakonNotification.objects.create(
            user=self.student,
            type=MakonNotification.TYPE_HOMEWORK,
            title="New homework",
            message="V50210",
            url=reverse("student_homework_root"),
        )
        self.client.force_login(self.student)
        response = self.client.post(reverse("notifications_read_root"))
        self.assertEqual(response.status_code, 200)
        notice.refresh_from_db()
        self.assertTrue(notice.is_read)

    def test_student_target_cta_and_progress_pages_use_v50210_workspace_styles(self):
        self.client.force_login(self.student)
        dashboard = self.client.get(reverse("student_dashboard_root"))
        self.assertContains(dashboard, "student-workspace-v50210.css")
        self.assertContains(dashboard, "data-goal-modal-open")

        self.client.force_login(self.teacher)
        practice = self.client.get(reverse("teacher_student_practice_progress_root", args=[self.classroom.pk, self.student.pk]))
        vocabulary = self.client.get(reverse("teacher_student_vocab_progress_root", args=[self.classroom.pk, self.student.pk]))
        for response in [practice, vocabulary]:
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "sf210-progress-shell")
            self.assertContains(response, "data-v50211-live-form")
