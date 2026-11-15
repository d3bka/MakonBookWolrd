"""V73 A-to-Z: the custom admin panel (users, groups, tests, mocks, support teachers)."""
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from apps.sat.models import Mock, SecretCode, SupportTeacherAvailability, SupportTeacherProfile, Test, TestReview


class AdminPanelJourneyTests(TestCase):
    def setUp(self):
        self.admin_group = Group.objects.get_or_create(name="Admin")[0]
        self.teacher_group = Group.objects.get_or_create(name="Teacher")[0]
        self.admin = User.objects.create_user("ap_admin", password="x")
        self.admin.groups.add(self.admin_group)
        self.kid = User.objects.create_user("ap_kid", password="x")
        self.test = Test.objects.create(name="AP-DAY1", is_available=True)
        self.client.force_login(self.admin)

    def test_every_admin_page_opens(self):
        mock = Mock.objects.create(name="Mock A", test=self.test, mode="direct", user_count=0, credentials="Username,Password\n")
        group = Group.objects.create(name="Paid")
        pages = [
            reverse("admin_users"), reverse("admin_users") + "?status=inactive&username=ap",
            reverse("admin_user_detail", args=[self.kid.pk]), reverse("admin_user_edit", args=[self.kid.pk]),
            reverse("admin_user_create"), reverse("admin_groups"), reverse("admin_group_detail", args=[group.pk]),
            reverse("admin_group_delete", args=[group.pk]), reverse("edit_group_tests", args=[group.pk]),
            reverse("admin_tests"), reverse("admin_test_detail", args=[self.test.pk]),
            reverse("admin_mocks"), reverse("admin_mock_create"), reverse("admin_mock_detail", args=[mock.pk]),
            reverse("admin_mock_delete", args=[mock.pk]), reverse("admin_support_teachers"),
            reverse("admin_support_bookings"), reverse("admin_support_teacher_create"),
        ]
        for url in pages:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_students_and_teachers_are_kept_out(self):
        teacher = User.objects.create_user("ap_teacher", password="x")
        teacher.groups.add(self.teacher_group)
        for who in (self.kid, teacher):
            self.client.force_login(who)
            for url in (reverse("admin_users"), reverse("admin_groups"), reverse("admin_mocks")):
                self.assertNotEqual(self.client.get(url).status_code, 200, (who.username, url))

    # ---------------------------------------------------------------- users
    def test_edit_a_users_groups(self):
        self.client.post(reverse("admin_user_edit", args=[self.kid.pk]), {"groups": [self.teacher_group.pk]})
        self.assertTrue(self.kid.groups.filter(name="Teacher").exists())
        self.client.post(reverse("admin_user_edit", args=[self.kid.pk]), {})
        self.assertFalse(self.kid.groups.exists())

    def test_admin_cannot_delete_themselves_or_a_superuser(self):
        boss = User.objects.create_superuser("ap_boss", "boss@example.com", "x")
        self.client.post(reverse("admin_user_delete", args=[self.admin.pk]))
        self.client.post(reverse("admin_user_delete", args=[boss.pk]))
        self.assertTrue(User.objects.filter(pk__in=[self.admin.pk, boss.pk]).count() == 2)
        self.client.post(reverse("admin_user_delete", args=[self.kid.pk]))
        self.assertFalse(User.objects.filter(pk=self.kid.pk).exists())
        self.client.get(reverse("admin_user_delete", args=[self.admin.pk]))  # GET never deletes
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())

    # ---------------------------------------------------------------- groups
    def test_create_group_and_remove_a_member(self):
        self.client.post(reverse("admin_groups"), {"name": "Evening SAT"})
        self.client.post(reverse("admin_groups"), {"name": "Evening SAT"})  # duplicate refused
        group = Group.objects.get(name="Evening SAT")
        self.kid.groups.add(group)
        self.client.post(reverse("admin_group_remove_user", args=[group.pk, self.kid.pk]))
        self.assertFalse(group.user_set.exists())
        self.assertTrue(User.objects.filter(pk=self.kid.pk).exists())

    def test_role_groups_cannot_be_deleted(self):
        teacher = User.objects.create_user("ap_teacher", password="x")
        teacher.groups.add(self.teacher_group)
        for group in (self.teacher_group, self.admin_group):
            self.client.post(reverse("admin_group_delete", args=[group.pk]), {"confirmation_name": group.name})
        self.assertTrue(Group.objects.filter(pk__in=[self.teacher_group.pk, self.admin_group.pk]).count() == 2)
        self.assertTrue(User.objects.filter(pk__in=[teacher.pk, self.admin.pk]).count() == 2)

    def test_group_delete_keeps_staff_and_people_with_other_groups(self):
        group = Group.objects.create(name="Old cohort")
        only_here = User.objects.create_user("ap_only", password="x")
        teacher = User.objects.create_user("ap_teacher", password="x")
        teacher.groups.add(self.teacher_group)
        for user in (only_here, teacher, self.admin):
            user.groups.add(group)
        page = self.client.get(reverse("admin_group_delete", args=[group.pk]))
        self.assertEqual((page.context["users_count"], page.context["kept_count"]), (1, 2))
        self.client.post(reverse("admin_group_delete", args=[group.pk]), {"confirmation_name": "wrong"})
        self.assertTrue(Group.objects.filter(pk=group.pk).exists())
        self.client.post(reverse("admin_group_delete", args=[group.pk]), {"confirmation_name": "Old cohort"})
        self.assertFalse(Group.objects.filter(pk=group.pk).exists())
        self.assertFalse(User.objects.filter(pk=only_here.pk).exists())
        self.assertTrue(User.objects.filter(pk__in=[teacher.pk, self.admin.pk]).count() == 2)

    # ---------------------------------------------------------------- mocks
    def create_mock(self, name, mode, count=3):
        return self.client.post(reverse("admin_mock_create"), {
            "name": name, "test": self.test.pk, "user_count": count, "mode": mode,
            "username_prefix": name.lower().replace(" ", ""), "password_length": 10,
        })

    def test_direct_mock_creates_accounts_and_credentials(self):
        response = self.create_mock("Nov Mock", "direct")
        mock = Mock.objects.get(name="Nov Mock")
        self.assertRedirects(response, reverse("admin_mock_detail", args=[mock.pk]), fetch_redirect_response=False)
        self.assertEqual(mock.user_count, 3)
        self.assertEqual(mock.group.user_set.count(), 3)
        self.assertIn(mock.group, self.test.groups.all())
        download = self.client.get(reverse("admin_mock_download", args=[mock.pk]))
        self.assertIn(b"novmock_1,", download.content)
        self.assertIn("attachment", download["Content-Disposition"])

    def test_deleting_a_secret_code_mock_keeps_real_students_who_joined_with_the_code(self):
        self.create_mock("Code Mock", "secret_code", count=2)
        mock = Mock.objects.get(name="Code Mock")
        self.assertIsNotNone(mock.secret_code)
        # a real student enters the code -> joins the mock group
        self.kid.groups.add(mock.group)
        TestReview.objects.create(user=self.kid, test=self.test, key="ap-real-review")
        page = self.client.get(reverse("admin_mock_delete", args=[mock.pk]))
        self.assertEqual((page.context["users_count"], page.context["kept_count"]), (0, 1))  # code mode: generated users are not in the group
        self.client.post(reverse("admin_mock_delete", args=[mock.pk]), {"confirmation_name": "Code Mock"})
        self.assertFalse(Mock.objects.filter(pk=mock.pk).exists())
        self.assertFalse(SecretCode.objects.filter(pk=mock.secret_code_id).exists())
        self.assertTrue(User.objects.filter(pk=self.kid.pk).exists())
        self.assertTrue(TestReview.objects.filter(user=self.kid).exists())

    def test_deleting_a_direct_mock_removes_only_its_generated_accounts(self):
        self.create_mock("Direct Mock", "direct", count=2)
        mock = Mock.objects.get(name="Direct Mock")
        self.kid.groups.add(mock.group)  # someone added by hand
        self.client.post(reverse("admin_mock_delete", args=[mock.pk]), {"confirmation_name": "Direct Mock"})
        self.assertFalse(User.objects.filter(username__startswith="directmock_").exists())
        self.assertTrue(User.objects.filter(pk=self.kid.pk).exists())
        self.assertFalse(Group.objects.filter(name="mock_Direct_Mock").exists())

    def test_assign_tests_to_a_group(self):
        group = Group.objects.create(name="Premium")
        self.client.post(reverse("edit_group_tests", args=[group.pk]), {"tests": [self.test.pk]})
        self.assertIn(self.test, group.tests.all())

    # ---------------------------------------------------------------- support teachers
    def test_support_teacher_create_edit_toggle_and_availability(self):
        mentor = User.objects.create_user("ap_mentor", password="x")
        self.client.post(reverse("admin_support_teacher_create"), {
            "user": mentor.pk, "display_name": "Mentor M", "subjects": "SAT Math", "years_experience": 3,
            "meeting_link": "https://meet.example.com/m", "min_booking_notice_hours": 2, "cancellation_notice_hours": 2,
            "sort_order": 1, "is_active": "on",
        })
        profile = SupportTeacherProfile.objects.filter(user=mentor).first()
        if profile is None:  # the form has more required fields: open the page and show them
            page = self.client.get(reverse("admin_support_teacher_create"))
            self.fail(f"profile not created; form fields: {list(page.context['form'].fields)}")
        self.assertTrue(mentor.groups.filter(name="Support Teacher").exists())
        self.assertEqual(self.client.get(reverse("admin_support_teacher_edit", args=[profile.pk])).status_code, 200)
        self.client.post(reverse("admin_support_teacher_toggle", args=[profile.pk]))
        profile.refresh_from_db()
        self.assertFalse(profile.is_active)
        self.client.post(reverse("admin_support_teacher_availability_add", args=[profile.pk]), {
            "day_of_week": 1, "start_time": "09:00", "end_time": "11:00", "slot_duration_minutes": 45,
            "buffer_minutes": 15, "is_active": "on",
        })
        window = SupportTeacherAvailability.objects.get(teacher=profile)
        self.client.post(reverse("admin_support_teacher_availability_delete", args=[profile.pk, window.pk]))
        self.assertFalse(SupportTeacherAvailability.objects.exists())
