from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from apps.apclasses.models import APExamEvent, APMockExam
from apps.sat.models import (
    Classroom,
    ClassroomLesson,
    ClassroomMembership,
    SupportTeacherProfile,
    TestImportJob,
    TestImportReview,
)


class StaffWorkspaceV527Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher_group = Group.objects.get_or_create(name="Teacher")[0]
        cls.manager_group = Group.objects.get_or_create(name="Manager")[0]
        cls.support_group = Group.objects.get_or_create(name="Support Teacher")[0]

        cls.teacher = User.objects.create_user(
            username="teacher_v527",
            password="pass12345",
            first_name="Main",
            last_name="Teacher",
            email="teacher@example.com",
        )
        cls.teacher.groups.add(cls.teacher_group)
        cls.manager = User.objects.create_user(username="manager_v527", password="pass12345", first_name="Ops")
        cls.manager.groups.add(cls.manager_group)
        cls.support_user = User.objects.create_user(username="support_v527", password="pass12345", first_name="Coach")
        cls.support_user.groups.add(cls.support_group)
        cls.support_profile = SupportTeacherProfile.objects.create(
            user=cls.support_user,
            display_name="Coach Support",
            subjects="SAT Math",
            is_active=True,
        )
        cls.multi_role = User.objects.create_user(username="multi_v527", password="pass12345")
        cls.multi_role.groups.add(cls.teacher_group, cls.manager_group)

        cls.classroom = Classroom.objects.create(
            teacher=cls.teacher,
            name="V527 SAT Classroom",
            classroom_type="sat",
            is_active=True,
        )
        cls.student = User.objects.create_user(username="student_v527", password="pass12345")
        ClassroomMembership.objects.create(
            classroom=cls.classroom,
            user=cls.student,
            role="student",
            status="approved",
        )
        cls.pending_student = User.objects.create_user(username="pending_v527", password="pass12345")
        ClassroomMembership.objects.create(
            classroom=cls.classroom,
            user=cls.pending_student,
            role="student",
            status="pending",
        )
        ClassroomLesson.objects.create(classroom=cls.classroom, title="Lesson 1", order=1, is_published=True)

        cls.ap_exam = APMockExam.objects.create(
            title="V527 AP Mock",
            status="published",
            created_by=cls.teacher,
        )
        cls.ap_event = APExamEvent.objects.create(
            title="V527 AP Event",
            exam=cls.ap_exam,
            is_public=True,
            is_global=True,
            status="live",
            always_live=True,
        )

    def assert_staff_shell(self, response, mode=None):
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-staff-workspace')
        self.assertContains(response, 'staff-workspace-v527.css')
        if mode:
            self.assertContains(response, f'data-staff-mode="{mode}"')

    def test_teacher_classroom_list_uses_staff_shell_and_real_summary_counts(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("teacher_classroom_list"))
        self.assert_staff_shell(response, "teacher")
        self.assertContains(response, "V527 SAT Classroom")
        self.assertContains(response, "Teacher workspace")
        stats = response.context["teacher_classroom_stats"]
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["active"], 1)
        self.assertEqual(stats["students"], 1)
        self.assertEqual(stats["pending"], 1)

    def test_teacher_classroom_tools_keep_staff_shell(self):
        self.client.force_login(self.teacher)
        urls = [
            reverse("teacher_classroom_dashboard", args=[self.classroom.pk]),
            reverse("teacher_classroom_homework", args=[self.classroom.pk]),
            reverse("classroom_progress_dashboard", args=[self.classroom.pk]),
            reverse("update_classroom_section_access", args=[self.classroom.pk]),
            reverse("update_classroom_practice_test_access", args=[self.classroom.pk]),
            reverse("classroom_practice_tests", args=[self.classroom.pk]),
            reverse("classroom_chat", args=[self.classroom.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assert_staff_shell(response, "teacher")

        # V50.2.10 moved classroom lesson authoring into the classroom dashboard.
        # Both the legacy /sat/... route and the canonical deep link now redirect
        # to that dashboard with Edit Mode opened instead of rendering a second editor.
        expected = f'{reverse("teacher_classroom_root", args=[self.classroom.pk])}?edit=1#course'
        for url in [
            reverse("teacher_classroom_lessons", args=[self.classroom.pk]),
            reverse("teacher_classroom_lessons_root", args=[self.classroom.pk]),
        ]:
            with self.subTest(lessons_redirect=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, expected)

    def test_teacher_vocabulary_and_rating_surfaces_use_staff_shell(self):
        self.client.force_login(self.teacher)
        for url in [
            reverse("teacher_vocabulary_units"),
            reverse("rating_teacher_classroom", args=[self.classroom.pk]),
        ]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assert_staff_shell(response, "teacher")

    def test_manager_dashboard_is_manager_mode_without_teacher_navigation(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("manager_dashboard"))
        self.assert_staff_shell(response, "manager")
        self.assertContains(response, "Manager home")
        self.assertContains(response, "Management tools")
        self.assertNotContains(response, "Teaching</span>")
        self.assertNotContains(response, "Mentor profile")

    def test_manager_support_inspection_stays_manager_mode_and_view_only(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("support_teacher_detail", args=[self.support_profile.pk]))
        self.assert_staff_shell(response, "manager")
        self.assertContains(response, "View-only access")
        self.assertNotContains(response, "Send this support request?")

    def test_support_teacher_planner_and_profile_use_support_mode(self):
        self.client.force_login(self.support_user)
        planner = self.client.get(reverse("support_teacher_planner"))
        self.assert_staff_shell(planner, "support")
        self.assertContains(planner, "Support teaching")
        profile = self.client.get(reverse("support_teacher_profile_edit"))
        self.assert_staff_shell(profile, "support")
        self.assertContains(profile, "Mentor Profile")

    def test_multi_role_user_gets_role_switcher_and_teacher_is_default_entry(self):
        classroom = Classroom.objects.create(teacher=self.multi_role, name="Multi classroom", classroom_type="sat")
        self.client.force_login(self.multi_role)
        response = self.client.get(reverse("teacher_classroom_list"))
        self.assert_staff_shell(response, "teacher")
        self.assertContains(response, "Teacher</span>")
        self.assertContains(response, "Manager</span>")
        entry = self.client.get(reverse("student_dashboard_root"))
        self.assertRedirects(entry, reverse("teacher_dashboard_root"), fetch_redirect_response=False)
        self.assertTrue(Classroom.objects.filter(pk=classroom.pk).exists())

    def test_ap_list_and_detail_use_staff_shell_for_teacher(self):
        self.client.force_login(self.teacher)
        listing = self.client.get(reverse("apclasses:event_list"))
        self.assert_staff_shell(listing, "teacher")
        self.assertContains(listing, "V527 AP Event")
        detail = self.client.get(reverse("apclasses:event_detail", args=[self.ap_event.slug]))
        self.assert_staff_shell(detail, "teacher")
        self.assertContains(detail, "Schedule &amp; rules")
        self.assertContains(detail, "Open event")

    def test_staff_profile_and_settings_do_not_fall_back_to_legacy_layout(self):
        for user, mode in [(self.teacher, "teacher"), (self.manager, "manager"), (self.support_user, "support")]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                profile = self.client.get(reverse("edit_profile"))
                self.assert_staff_shell(profile, mode)
                self.assertContains(profile, "Staff account")
                settings = self.client.get(reverse("settings_page"))
                self.assert_staff_shell(settings, mode)
                self.assertContains(settings, "Settings, not another profile page.")
                self.assertContains(
                    settings,
                    f'class="mb50-nav-item is-active" href="{reverse("settings_page")}"',
                )


    def test_manager_operations_keep_manager_shell(self):
        self.client.force_login(self.manager)
        for url in [
            reverse("hollihop_dashboard"),
            reverse("manager_test_import_list_root"),
            reverse("manager_managed_test_list_root"),
        ]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assert_staff_shell(response, "manager")

    def test_support_reviewer_queue_keeps_support_shell_without_manager_controls(self):
        job = TestImportJob.objects.create(
            name="V527 review queue",
            created_by=self.manager,
            status=TestImportJob.STATUS_REVIEW_REQUIRED,
        )
        TestImportReview.objects.create(job=job, reviewer=self.support_user)
        self.client.force_login(self.support_user)
        response = self.client.get(reverse("support_teacher_review_list_root"))
        self.assert_staff_shell(response, "support")
        self.assertContains(response, "V527 review queue")
        self.assertNotContains(response, "Import PDF")
        self.assertNotContains(response, "Published tests")

    def test_teacher_creation_and_assessment_surfaces_keep_teacher_shell(self):
        self.client.force_login(self.teacher)
        create = self.client.get(reverse("create_classroom"))
        self.assert_staff_shell(create, "teacher")
        self.assertContains(create, "Create a classroom")
        assessment = self.client.get(reverse("rating_assess_student", args=[self.classroom.pk, self.student.pk]))
        self.assert_staff_shell(assessment, "teacher")
        self.assertContains(assessment, self.student.username)

    def test_manager_cannot_open_teacher_write_surfaces(self):
        self.client.force_login(self.manager)
        create = self.client.get(reverse("create_classroom"))
        self.assertEqual(create.status_code, 403)
        edit_access = self.client.get(reverse("update_classroom_section_access", args=[self.classroom.pk]))
        self.assertEqual(edit_access.status_code, 403)
        assessment = self.client.get(reverse("rating_assess_student", args=[self.classroom.pk, self.student.pk]))
        self.assertEqual(assessment.status_code, 403)


    def test_staff_shell_keeps_canonical_role_home_and_access_navigation(self):
        self.client.force_login(self.teacher)
        access = self.client.get(reverse("update_classroom_section_access", args=[self.classroom.pk]))
        self.assert_staff_shell(access, "teacher")
        self.assertContains(
            access,
            f'class="mb50-nav-item is-active" href="{reverse("teacher_access_root")}"',
        )
        self.assertContains(access, 'Back to Access center')
        self.assertContains(
            access,
            f'href="{reverse("teacher_dashboard_root")}" aria-label="MakonBook staff home"',
        )

        self.client.force_login(self.manager)
        manager = self.client.get(reverse("support_teacher_list"))
        self.assert_staff_shell(manager, "manager")
        self.assertContains(manager, 'Support teachers')
        self.assertContains(manager, 'href="' + reverse("manager_dashboard_root") + '" aria-label="MakonBook staff home"')

        self.client.force_login(self.support_user)
        support = self.client.get(reverse("support_teacher_planner"))
        self.assert_staff_shell(support, "support")
        self.assertContains(
            support,
            f'href="{reverse("support_teacher_dashboard_root")}" aria-label="MakonBook staff home"',
        )

    def test_manager_read_only_teacher_and_classroom_pages_use_staff_shell(self):
        self.client.force_login(self.manager)
        teacher = self.client.get(reverse("manager_teacher_detail", args=[self.teacher.pk]))
        self.assert_staff_shell(teacher, "manager")
        self.assertContains(teacher, "View only")
        classroom = self.client.get(reverse("manager_classroom_detail", args=[self.classroom.pk]))
        self.assert_staff_shell(classroom, "manager")
        self.assertContains(classroom, "Read only")
