from pathlib import Path
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import (
    Classroom,
    ClassroomHomeworkAssignment,
    ClassroomLesson,
    ClassroomLessonResource,
    ClassroomMembership,
    MakonNotification,
    SupportTeacherProfile,
    Test,
    VocabularyUnit,
    VocabularyWord,
)


class StaffWorkspaceV50211Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher_group = Group.objects.get_or_create(name="Teacher")[0]
        cls.manager_group = Group.objects.get_or_create(name="Manager")[0]
        cls.support_group = Group.objects.get_or_create(name="Support Teacher")[0]
        cls.teacher = User.objects.create_user(username="teacher_v50211", password="pass12345", first_name="Teacher")
        cls.teacher.groups.add(cls.teacher_group)
        cls.manager = User.objects.create_user(username="manager_v50211", password="pass12345", first_name="Manager")
        cls.manager.groups.add(cls.manager_group)
        cls.support = User.objects.create_user(username="support_v50211", password="pass12345", first_name="Support")
        cls.support.groups.add(cls.support_group)
        SupportTeacherProfile.objects.create(user=cls.support, display_name="Support V50211", subjects="SAT", is_active=True)
        cls.student = User.objects.create_user(username="student_v50211", password="pass12345", first_name="Student")
        cls.classroom = Classroom.objects.create(
            teacher=cls.teacher, name="V50211 Classroom", classroom_type=Classroom.CLASSROOM_TYPE_SAT, is_active=True
        )
        cls.membership = ClassroomMembership.objects.create(
            classroom=cls.classroom, user=cls.student, role="student", status="approved"
        )
        cls.test = Test.objects.create(name="DAY11", is_available=True)
        cls.lesson = ClassroomLesson.objects.create(
            classroom=cls.classroom, title="Vocabulary unit", order=1, is_published=True, created_by=cls.teacher
        )
        cls.vocab = VocabularyUnit.objects.create(title="V50211 Vocabulary", order=1, is_active=True)
        for idx in range(1, 7):
            VocabularyWord.objects.create(
                unit=cls.vocab, word=f"word{idx}", meaning=f"meaning{idx}", is_active=True
            )

    def test_eclass_unit_creation_is_modal_and_vocabulary_quiz_material_can_launch(self):
        self.client.force_login(self.teacher)
        dashboard = self.client.get(reverse("teacher_classroom_root", args=[self.classroom.pk]), {"edit": "1"})
        self.assertContains(dashboard, 'data-v50211-modal-open="create-unit"')
        self.assertContains(dashboard, 'data-v50211-modal="create-unit"')
        self.assertContains(dashboard, f'data-v50211-modal-open="edit-unit-{self.lesson.pk}"')
        self.assertContains(dashboard, f'data-v50211-modal="edit-unit-{self.lesson.pk}"')
        self.assertContains(dashboard, f'data-v50211-modal-open="add-material-{self.lesson.pk}"')
        self.assertContains(dashboard, f'data-v50211-modal="add-material-{self.lesson.pk}"')
        self.assertContains(dashboard, 'data-v50212-danger-confirm')
        self.assertNotContains(dashboard, 'onsubmit="return confirm(')
        self.assertNotContains(dashboard, 'sf210-inline-editor')
        self.assertNotContains(dashboard, 'sf210-add-material')
        self.assertNotContains(dashboard, 'data-v50210-resource-editor-toggle')
        self.assertContains(dashboard, 'value="vocabulary_quiz"')

        response = self.client.post(reverse("teacher_classroom_root", args=[self.classroom.pk]), {
            "course_action": "add_resource",
            "lesson_id": self.lesson.pk,
            "resource_title": "Vocabulary checkpoint",
            "resource_type": ClassroomLessonResource.RESOURCE_VOCAB_QUIZ,
            "vocabulary_unit": self.vocab.pk,
            "vocabulary_question_count": "5",
            "vocabulary_quiz_mode": "mixed",
            "resource_order": "1",
            "is_visible": "1",
        })
        self.assertEqual(response.status_code, 302)
        resource = ClassroomLessonResource.objects.get(
            lesson=self.lesson, resource_type=ClassroomLessonResource.RESOURCE_VOCAB_QUIZ
        )
        self.assertEqual(resource.vocabulary_unit, self.vocab)
        self.assertEqual(resource.vocabulary_question_count, 5)

        dashboard = self.client.get(reverse("teacher_classroom_root", args=[self.classroom.pk]), {"edit": "1"})
        self.assertContains(dashboard, f'data-v50211-modal-open="edit-material-{resource.pk}"')
        self.assertContains(dashboard, f'data-v50211-modal="edit-material-{resource.pk}"')

        self.client.force_login(self.student)
        classroom_page = self.client.get(reverse("student_classroom_home_root", args=[self.classroom.pk]))
        self.assertContains(classroom_page, "Vocabulary Quiz")
        preview_url = reverse("student_lesson_vocabulary_quiz_root", args=[self.classroom.pk, resource.pk])
        preview = self.client.get(preview_url)
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, "Vocabulary checkpoint")
        start = self.client.post(preview_url)
        self.assertEqual(start.status_code, 200)
        self.assertContains(start, "Vocabulary Quiz")

    def test_homework_delete_js_uses_attribute_action_not_shadowed_form_property(self):
        # A form control named "action" shadows HTMLFormElement.action in browsers.
        # The delete modal contains <input name="action">, so form.action becomes
        # the HTMLInputElement and stringifies to "[object HTMLInputElement]".
        script_path = finders.find("assets/js/workspace-v50211.js")
        self.assertTrue(script_path)
        script = Path(script_path).read_text(encoding="utf-8")
        self.assertIn("form.getAttribute('action')", script)
        self.assertIn("homeworkDeleteRequest(formActionUrl(form),form)", script)
        self.assertNotIn("homeworkDeleteRequest(form.action,form)", script)
        self.assertNotIn("filterForm.action", script)

    def test_homework_ajax_delete_does_not_notify_student_about_removed_work(self):
        assignment = ClassroomHomeworkAssignment.objects.create(
            classroom=self.classroom,
            created_by=self.teacher,
            title="Temporary homework",
            assignment_type=ClassroomHomeworkAssignment.TYPE_TEST,
            test=self.test,
            assign_all=True,
        )
        self.client.force_login(self.teacher)
        hub = self.client.get(reverse("teacher_homework_root"))
        self.assertContains(hub, f'data-assignment-id="{assignment.pk}"')
        self.assertContains(hub, f'action="{reverse("teacher_homework_root")}"')
        self.assertNotContains(hub, 'data-delete-url=')
        response = self.client.post(
            reverse("teacher_homework_root"),
            {"action": "delete", "assignment_id": assignment.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertFalse(ClassroomHomeworkAssignment.objects.filter(pk=assignment.pk).exists())
        self.assertFalse(MakonNotification.objects.filter(user=self.student, title__icontains="removed").exists())

    def test_homework_hub_ajax_delete_is_a_route_independent_fallback(self):
        assignment = ClassroomHomeworkAssignment.objects.create(
            classroom=self.classroom,
            created_by=self.teacher,
            title="Fallback homework",
            assignment_type=ClassroomHomeworkAssignment.TYPE_TEST,
            test=self.test,
            assign_all=True,
        )
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse("teacher_homework_root"),
            {"action": "delete", "assignment_id": assignment.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"].split(";")[0], "application/json")
        self.assertTrue(response.json()["ok"])
        self.assertFalse(ClassroomHomeworkAssignment.objects.filter(pk=assignment.pk).exists())

    def test_homework_ajax_delete_returns_json_for_missing_rows_instead_of_html(self):
        self.client.force_login(self.teacher)
        response = self.client.post(reverse("teacher_homework_root"), {
            "action": "delete",
            "assignment_id": 99999999,
            "classroom": self.classroom.pk,
        }, HTTP_X_REQUESTED_WITH="XMLHttpRequest", HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["Content-Type"].split(";")[0], "application/json")
        self.assertFalse(response.json()["ok"])

    def test_homework_ajax_delete_returns_json_for_non_teacher(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("teacher_homework_root"),
            {"action": "delete", "assignment_id": 99999999},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response["Content-Type"].split(";")[0], "application/json")
        self.assertFalse(response.json()["ok"])

    def test_homework_ajax_delete_rejects_malformed_ids_as_json(self):
        self.client.force_login(self.teacher)
        response = self.client.post(reverse("teacher_homework_root"), {
            "action": "delete",
            "assignment_id": "not-a-number",
            "classroom": self.classroom.pk,
        }, HTTP_X_REQUESTED_WITH="XMLHttpRequest", HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["Content-Type"].split(";")[0], "application/json")
        self.assertFalse(response.json()["ok"])

    def test_deadline_notice_is_deduplicated_and_read_all_endpoint_clears_it(self):
        assignment = ClassroomHomeworkAssignment.objects.create(
            classroom=self.classroom,
            created_by=self.teacher,
            title="Urgent DAY11",
            assignment_type=ClassroomHomeworkAssignment.TYPE_TEST,
            test=self.test,
            assign_all=True,
            due_at=timezone.now() + timedelta(hours=2),
        )
        self.client.force_login(self.student)
        first = self.client.get(reverse("student_homework_root"))
        self.assertEqual(first.status_code, 200)
        notice_qs = MakonNotification.objects.filter(
            user=self.student, type=MakonNotification.TYPE_HOMEWORK,
            url=reverse("student_homework_launch_root", args=[assignment.pk]),
        )
        self.assertEqual(notice_qs.count(), 1)
        self.client.get(reverse("student_homework_root"))
        self.assertEqual(notice_qs.count(), 1)
        mark = self.client.post(reverse("notifications_read_root"))
        self.assertEqual(mark.status_code, 200)
        self.assertFalse(notice_qs.filter(is_read=False).exists())

    def test_notification_endpoint_can_mark_only_rendered_notice_ids(self):
        shown = MakonNotification.objects.create(
            user=self.student, type=MakonNotification.TYPE_CLASSROOM, title="Shown notice", message="Shown"
        )
        hidden = MakonNotification.objects.create(
            user=self.student, type=MakonNotification.TYPE_ACCESS, title="Older hidden notice", message="Hidden"
        )
        self.client.force_login(self.student)
        response = self.client.post(reverse("notifications_read_root"), {"ids": [shown.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        shown.refresh_from_db()
        hidden.refresh_from_db()
        self.assertTrue(shown.is_read)
        self.assertFalse(hidden.is_read)
        self.assertGreaterEqual(response.json()["unread"], 1)

    def test_notification_endpoint_invalid_id_filter_never_falls_back_to_read_all(self):
        first = MakonNotification.objects.create(
            user=self.student, type=MakonNotification.TYPE_CLASSROOM, title="First unread", message="First"
        )
        second = MakonNotification.objects.create(
            user=self.student, type=MakonNotification.TYPE_ACCESS, title="Second unread", message="Second"
        )
        self.client.force_login(self.student)
        response = self.client.post(reverse("notifications_read_root"), {"ids": ["not-a-number"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["updated"], 0)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_read)
        self.assertFalse(second.is_read)

    def test_legacy_sat_import_and_goal_pages_never_render_under_sat_prefix(self):
        self.client.force_login(self.manager)
        legacy = self.client.get("/sat/test-imports/published/?q=50&state=all&source=all&per_page=24")
        self.assertEqual(legacy.status_code, 302)
        self.assertEqual(
            legacy["Location"],
            "/manager/tests-import/published/?q=50&state=all&source=all&per_page=24",
        )

        self.client.force_login(self.student)
        goal = self.client.get("/sat/student/goals/")
        self.assertEqual(goal.status_code, 302)
        self.assertEqual(goal["Location"], "/dashboard/?goal=1")
        dashboard = self.client.get(reverse("student_dashboard_root"))
        self.assertContains(dashboard, reverse("student_goal_settings_root"))
        self.assertNotContains(dashboard, 'action="/sat/student/goals/"')

    def test_staff_settings_include_functional_settings_script_for_every_staff_mode(self):
        for user in (self.teacher, self.manager, self.support):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(reverse("settings_page"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "data-staff-workspace")
                expected_mode = "support" if user == self.support else ("manager" if user == self.manager else "teacher")
                self.assertContains(response, f'data-workspace-storage-scope="staff-{expected_mode}"')
                self.assertContains(response, "Object.keys(localStorage)")


    def test_settings_preserves_explicit_workspace_for_multi_role_staff(self):
        self.teacher.groups.add(self.manager_group)
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("settings_page"), {"workspace": "manager"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-staff-mode="manager"')
        self.assertContains(response, 'data-workspace-storage-scope="staff-manager"')
        self.assertContains(response, reverse("manager_teacher_list_root"))
        self.assertNotContains(response, reverse("teacher_homework_root"))

        profile = self.client.get(reverse("edit_profile"), {"workspace": "manager"})
        self.assertEqual(profile.status_code, 200)
        self.assertContains(profile, 'data-staff-mode="manager"')
        self.assertContains(profile, 'data-workspace-storage-scope="staff-manager"')

    def test_live_search_surfaces_use_ajax_regions_and_canonical_actions(self):
        self.client.force_login(self.teacher)
        homework = self.client.get(reverse("teacher_homework_root"))
        self.assertContains(homework, 'data-v50211-live-form')
        self.assertContains(homework, 'data-v50211-live-region="teacher-homework"')
        self.assertContains(homework, f'action="{reverse("teacher_homework_root")}"')

        self.client.force_login(self.manager)
        for url, region in [
            (reverse("manager_teacher_list_root"), "manager-teachers"),
            (reverse("manager_support_teacher_list_root"), "manager-support-teachers"),
            (reverse("manager_managed_test_list_root"), "published-tests"),
        ]:
            response = self.client.get(url)
            self.assertContains(response, 'data-v50211-live-form')
            self.assertContains(response, f'data-v50211-live-region="{region}"')
            self.assertNotContains(response, 'data-v50210-live-form')

    def test_homework_edit_uses_delegated_modal_handler_after_live_refresh(self):
        js_path = settings.BASE_DIR / 'static' / 'assets' / 'js' / 'staff-workspace-v50210.js'
        source = js_path.read_text(encoding='utf-8')
        self.assertIn("document.addEventListener('click'", source)
        self.assertIn("closest('[data-v50210-edit-homework]')", source)
        self.assertIn("openHomeworkEdit(btn)", source)
        self.assertNotIn("document.querySelectorAll('[data-v50210-edit-homework]').forEach", source)

    def test_support_planner_uses_compact_workspace_hero(self):
        self.client.force_login(self.support)
        response = self.client.get(reverse("support_teacher_planner_root"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "support-v50211-hero")
        self.assertContains(response, "Topic planner")
        self.assertNotContains(response, "support-card support-hero")
