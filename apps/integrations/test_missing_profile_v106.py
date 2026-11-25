"""V106: an old account without a UserProfile no longer breaks Hollihop synchronization."""
from importlib import import_module
from unittest import mock

from django.apps import apps as django_apps
from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.base.models import UserProfile
from apps.integrations.hollihop.sync import HollihopSyncEngine, _profile_of


class MissingProfileTests(TestCase):
    def test_student_matched_by_email_without_a_profile_is_synced(self):
        old = User.objects.create_user("old_student", email="aziz@makonbook.example", password="x", first_name="Aziz")
        UserProfile.objects.filter(user=old).delete()
        engine = HollihopSyncEngine(client=mock.Mock())
        row = {"ClientId": 4145, "FirstName": "Aziz", "LastName": "Karimov", "MiddleName": "",
               "EMail": "aziz@makonbook.example", "Mobile": "", "Status": "Занимается"}
        engine._sync_student(row)  # crashed with RelatedObjectDoesNotExist before V106
        profile = UserProfile.objects.get(user=old)
        self.assertEqual(profile.hollihop_client_id, 4145)
        self.assertEqual(User.objects.get(pk=old.pk).last_name, "Karimov")

    def test_profile_helper_and_data_migration(self):
        user = User.objects.create_user("no_profile", password="x")
        UserProfile.objects.filter(user=user).delete()
        user = User.objects.get(pk=user.pk)
        self.assertEqual(_profile_of(user).user_id, user.pk)
        UserProfile.objects.filter(user=user).delete()
        migration = import_module("apps.base.migrations.0051_missing_profiles_v106")
        migration.create_missing_profiles(django_apps, None)
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertFalse(User.objects.filter(profile__isnull=True).exists())


class DuplicateWarningTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user("w_manager", password="x")
        self.manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.client.force_login(self.manager)
        self.url = reverse("hollihop_credential_campaign")

    def test_no_warning_without_duplicates(self):
        page = self.client.get(self.url)
        self.assertContains(page, "No duplicate accounts found")
        self.assertNotContains(page, "possible duplicate account")

    def test_warning_with_the_real_count(self):
        User.objects.create_user("malika_old", password="x", first_name="Malika", last_name="Yusupova")
        hh = User.objects.create_user("malika_hh", password="x", first_name="MALIKA", last_name="YUSUPOVA")
        UserProfile.objects.filter(user=hh).update(hollihop_client_id=3301)
        page = self.client.get(self.url)
        self.assertContains(page, "1 possible duplicate account (0 staff, 1 students)")
