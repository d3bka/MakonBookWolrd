"""V104: find people with two accounts (hand-made + Hollihop) and merge them safely."""
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.base.account_merge import MergeRefused, find_duplicate_pairs, merge_accounts
from apps.base.models import AccountDuplicateDismissal, AccountMerge, UserProfile
from apps.sat.models import (
    Classroom, ClassroomHomeworkAssignment, ClassroomHomeworkSubmission, ClassroomMembership, Test, TestReview,
)


def make(username, first, last, *, group=None, phone=None, email="", last_login=None, **hollihop):
    user = User.objects.create_user(username, email=email, password="x", first_name=first, last_name=last)
    if group:
        user.groups.add(Group.objects.get_or_create(name=group)[0])
    if last_login:
        User.objects.filter(pk=user.pk).update(last_login=last_login)
        user.refresh_from_db()
    UserProfile.objects.filter(user=user).update(phone_number=phone, **hollihop)
    return user


def pair_names(pairs):
    return {frozenset((p["a"].username, p["b"].username)) for p in pairs}


class FindDuplicatesTests(TestCase):
    def test_staff_pairs_across_transliteration_and_contacts(self):
        make("berdakh", "Berdakh", "Jaksymuratov", group="Teacher", last_login=timezone.now())
        make("hh_8871", "BERDAH", "JAHSIMURODOV", group="Teacher", hollihop_teacher_id=8871)
        make("sabina", "Sabina", "Habibova", group="Teacher")
        make("hh_14402", "SABINA", "HABIBOVA", group="Teacher", hollihop_teacher_id=14402)
        make("ozod1", "Ozodbek", "Hamidov", group="Teacher")
        make("ozod2", "Ozodbek", "Hamdamov", group="Teacher")
        make("t_phone1", "Rustam", "R", group="Teacher", phone="+998 90 123 45 67")
        make("t_phone2", "Rustam", "Rahimov", group="Teacher", phone="998901234567")
        pairs = pair_names(find_duplicate_pairs("staff"))
        self.assertIn(frozenset(("berdakh", "hh_8871")), pairs)
        self.assertIn(frozenset(("sabina", "hh_14402")), pairs)
        self.assertIn(frozenset(("t_phone1", "t_phone2")), pairs)  # same phone, staff
        self.assertNotIn(frozenset(("ozod1", "ozod2")), pairs)  # different surnames

    def test_students_need_matching_names_and_different_hollihop_records_never_pair(self):
        make("aziz", "Aziz", "Karimov", phone="+998901112233")
        make("aziza", "Aziza", "Karimova", phone="+998901112233")  # sister, same parent phone
        make("ali1", "Ali", "Valiyev", hollihop_client_id=1)
        make("ali2", "Ali", "Valiyev", hollihop_client_id=2)  # two Hollihop students with the same name
        make("malika_old", "Malika", "Yusupova")
        make("malika_hh", "MALIKA", "YUSUPOVA", hollihop_client_id=3)
        pairs = pair_names(find_duplicate_pairs("students"))
        self.assertEqual(pairs, {frozenset(("malika_old", "malika_hh"))})
        self.assertEqual(find_duplicate_pairs("staff"), [])  # categories are separate

    def test_dismissed_pairs_stay_hidden(self):
        a = make("m1", "Malika", "Yusupova")
        b = make("m2", "Malika", "Yusupova", hollihop_client_id=7)
        self.assertEqual(len(find_duplicate_pairs("students")), 1)
        AccountDuplicateDismissal.objects.create(user_low=a, user_high=b)
        self.assertEqual(find_duplicate_pairs("students"), [])

    def test_two_hand_made_students_with_the_same_name_are_not_suggested(self):
        make("s1", "Jasur", "Karimov")
        make("s2", "Jasur", "Karimov")
        self.assertEqual(find_duplicate_pairs("students"), [])


class MergeTests(TestCase):
    def setUp(self):
        self.manager = make("mgr", "Main", "Manager", group="Manager")
        self.old = make("berdakh", "Berdakh", "Jaksymuratov", group="Teacher", email="b@makonbook.example")
        self.hh = make("hh_8871", "BERDAH", "JAHSIMURODOV", group="Teacher", phone="+998901234567", hollihop_teacher_id=8871)
        self.hh.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.class_hh = Classroom.objects.create(teacher=self.hh, name="Mr Berdakh Macro 14:00")
        self.class_old = Classroom.objects.create(teacher=self.old, name="Old manual class")

    def test_merge_moves_everything_and_switches_the_old_account_off(self):
        merge = merge_accounts(self.old, self.hh, by=self.manager)
        self.class_hh.refresh_from_db()
        self.assertEqual(self.class_hh.teacher, self.old)
        profile = UserProfile.objects.get(user=self.old)
        self.assertEqual((profile.hollihop_teacher_id, profile.phone_number), (8871, "+998901234567"))
        self.assertTrue(self.old.groups.filter(name="Manager").exists())
        self.hh.refresh_from_db()
        self.assertFalse(self.hh.is_active)
        self.assertFalse(self.hh.has_usable_password())
        self.assertIsNone(UserProfile.objects.get(user=self.hh).hollihop_teacher_id)
        self.assertIsNone(UserProfile.objects.get(user=self.hh).phone_number)  # no longer found by contact matching
        self.assertEqual(merge.removed_username, "hh_8871")
        self.assertEqual(merge.moved.get("sat.classroom.teacher"), 1)
        self.assertEqual(merge.moved.get("hollihop_links"), ["hollihop_teacher_id"])
        self.assertEqual(AccountMerge.objects.count(), 1)
        # Hollihop synchronization finds the kept account by its external id.
        self.assertEqual(UserProfile.objects.get(hollihop_teacher_id=8871).user, self.old)

    def test_colliding_rows_stay_with_the_old_account(self):
        student_old = make("malika_old", "Malika", "Yusupova")
        student_hh = make("malika_hh", "MALIKA", "YUSUPOVA", hollihop_client_id=3)
        for user in (student_old, student_hh):
            ClassroomMembership.objects.create(classroom=self.class_hh, user=user, role="student", status="approved")
        ClassroomMembership.objects.create(classroom=self.class_old, user=student_hh, role="student", status="approved")
        hw = ClassroomHomeworkAssignment.objects.create(classroom=self.class_hh, created_by=self.hh, title="HW", assignment_type="file", attachment="x.pdf")
        ClassroomHomeworkSubmission.objects.create(assignment=hw, student=student_old, status="submitted")
        ClassroomHomeworkSubmission.objects.create(assignment=hw, student=student_hh, status="not_started")
        review = TestReview.objects.create(test=Test.objects.create(name="DAY1"), user=student_hh, score=30, key="k1")

        merge = merge_accounts(student_old, student_hh, by=self.manager)
        review.refresh_from_db()
        self.assertEqual(review.user, student_old)
        self.assertEqual(ClassroomMembership.objects.filter(user=student_old).count(), 2)
        self.assertEqual(ClassroomMembership.objects.filter(user=student_hh).count(), 1)  # the duplicate membership stayed
        self.assertEqual(ClassroomHomeworkSubmission.objects.get(assignment=hw, student=student_old).status, "submitted")
        self.assertTrue(ClassroomHomeworkSubmission.objects.filter(student=student_hh).exists())  # nothing deleted
        self.assertEqual(sum(merge.dropped.values()), 2)
        self.assertEqual(UserProfile.objects.get(user=student_old).hollihop_client_id, 3)

    def test_refusals(self):
        other = make("other_hh", "Berdakh", "Jaksymuratov", group="Teacher", hollihop_teacher_id=9999)
        with self.assertRaises(MergeRefused):
            merge_accounts(self.hh, other, by=self.manager)  # two different Hollihop teachers
        admin = make("boss", "Berdakh", "Jaksymuratov")
        User.objects.filter(pk=admin.pk).update(is_staff=True)
        admin.refresh_from_db()
        with self.assertRaises(MergeRefused):
            merge_accounts(self.old, admin, by=self.manager)
        with self.assertRaises(MergeRefused):
            merge_accounts(self.old, self.old, by=self.manager)
        self.assertTrue(User.objects.get(pk=self.hh.pk).is_active)


class DuplicatePagesTests(TestCase):
    def setUp(self):
        self.manager = make("mgr", "Main", "Manager", group="Manager")
        self.old = make("berdakh", "Berdakh", "Jaksymuratov", group="Teacher", last_login=timezone.now())
        self.hh = make("hh_8871", "BERDAH", "JAHSIMURODOV", group="Teacher", hollihop_teacher_id=8871)
        Classroom.objects.create(teacher=self.hh, name="Macro 14:00")
        self.url = reverse("manager_account_duplicates_root")

    def test_manager_sees_the_pair_and_merges_after_typing_merge(self):
        self.client.force_login(self.manager)
        page = self.client.get(self.url)
        self.assertContains(page, "BERDAH JAHSIMURODOV")
        self.assertContains(page, "Recommended to keep")
        self.assertEqual(page.context["pairs"][0]["keep_id"], self.old.id)  # the account that logs in
        self.assertEqual(page.context["staff_workspace_mode"], "manager")

        merge_url = reverse("manager_account_merge_root", args=[self.old.id, self.hh.id])
        preview = self.client.get(merge_url)
        self.assertContains(preview, "Type MERGE to confirm")
        self.assertContains(preview, "Hollihop teacher")
        self.client.post(merge_url, {"confirm": "merge please"})
        self.assertTrue(User.objects.get(pk=self.hh.pk).is_active)
        response = self.client.post(merge_url, {"confirm": "MERGE"}, follow=True)
        self.assertContains(response, "Merged: hh_8871")
        self.assertFalse(User.objects.get(pk=self.hh.pk).is_active)
        self.assertContains(response, "Recent merges")

    def test_different_people_and_rights(self):
        self.client.force_login(self.manager)
        self.client.post(self.url, {"action": "dismiss", "a": self.old.id, "b": self.hh.id})
        self.assertEqual(self.client.get(self.url).context["pairs"], [])
        self.client.force_login(self.old)  # a teacher
        self.assertEqual(self.client.get(self.url).status_code, 403)
        merge_url = reverse("manager_account_merge_root", args=[self.old.id, self.hh.id])
        self.assertEqual(self.client.post(merge_url, {"confirm": "MERGE"}).status_code, 403)
        self.assertTrue(User.objects.get(pk=self.hh.pk).is_active)
