"""V50.7 Friends: codes, requests, friend list, classmates, visiting rooms and trophies."""
from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.gamification import friends as social
from apps.gamification.models import Friendship, UserAchievement
from apps.sat.models import Classroom, ClassroomMembership, MakonNotification


def student(username, first="Stu", last="Dent"):
    return User.objects.create_user(username, password="x", first_name=first, last_name=last)


@override_settings(MAKONBOOK_WORLD_ENABLED=False)
class FriendsTests(TestCase):
    def setUp(self):
        self.aziz = student("fr_aziz", "Aziz", "Karimov")
        self.laylo = student("fr_laylo", "Laylo", "Usmonova")

    def add_by_code(self, sender, target):
        self.client.force_login(sender)
        return self.client.post(reverse("friends_add"), {"code": social.friend_code_for(target).lower().replace("-", " ")})

    def befriend(self):
        self.add_by_code(self.aziz, self.laylo)
        row = Friendship.objects.get(from_user=self.aziz, to_user=self.laylo)
        self.client.force_login(self.laylo)
        self.client.post(reverse("friends_respond", args=[row.pk, "accept"]))

    def test_friend_code_is_stable_readable_and_unique(self):
        code = social.friend_code_for(self.aziz)
        self.assertRegex(code, r"^[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}$")
        self.assertEqual(code, social.friend_code_for(self.aziz))
        self.assertNotEqual(code, social.friend_code_for(self.laylo))
        self.assertEqual(social.user_by_code(code.lower().replace("-", "")), self.aziz)
        self.assertIsNone(social.user_by_code("NOPE"))

    def test_request_accept_and_both_see_each_other(self):
        response = self.add_by_code(self.aziz, self.laylo)
        self.assertRedirects(response, reverse("friends"))
        self.assertTrue(MakonNotification.objects.filter(user=self.laylo, type="social").exists())
        self.client.force_login(self.laylo)
        page = self.client.get(reverse("friends"))
        self.assertContains(page, "Friend requests")
        self.assertContains(page, "Aziz Karimov")
        self.assertContains(page, '<span>Friends</span><b>1</b>')  # sidebar badge
        row = Friendship.objects.get(from_user=self.aziz, to_user=self.laylo)
        self.client.post(reverse("friends_respond", args=[row.pk, "accept"]))
        self.assertTrue(social.are_friends(self.aziz, self.laylo))
        self.client.force_login(self.aziz)
        page = self.client.get(reverse("friends"))
        self.assertContains(page, "Laylo Usmonova")
        self.assertContains(page, reverse("friend_room", args=["fr_laylo"]))
        self.assertNotContains(page, "world/challenge")  # World is closed: no duel button

    def test_crossed_requests_become_a_friendship(self):
        self.add_by_code(self.aziz, self.laylo)
        self.add_by_code(self.laylo, self.aziz)
        self.assertTrue(social.are_friends(self.aziz, self.laylo))
        self.assertEqual(Friendship.objects.count(), 1)

    def test_bad_requests_are_explained_not_saved(self):
        teacher = User.objects.create_user("fr_teacher", password="x")
        teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        cases = [
            (self.aziz, {"code": social.friend_code_for(self.aziz)}, "your own code"),
            (self.aziz, {"code": "ZZZZ-ZZZZ"}, "No student has that friend code"),
            (self.aziz, {"code": social.friend_code_for(teacher)}, "student accounts"),
        ]
        for sender, data, message in cases:
            self.client.force_login(sender)
            response = self.client.post(reverse("friends_add"), data, follow=True)
            self.assertContains(response, message)
        self.add_by_code(self.aziz, self.laylo)
        again = self.client.post(reverse("friends_add"), {"code": social.friend_code_for(self.laylo)}, follow=True)
        self.assertContains(again, "still waiting")
        self.assertEqual(Friendship.objects.count(), 1)

    def test_decline_cancel_and_remove(self):
        self.add_by_code(self.aziz, self.laylo)
        row = Friendship.objects.get()
        self.client.force_login(self.laylo)
        self.client.post(reverse("friends_respond", args=[row.pk, "decline"]))
        self.assertFalse(Friendship.objects.exists())
        self.add_by_code(self.aziz, self.laylo)
        self.client.post(reverse("friends_cancel", args=[Friendship.objects.get().pk]))
        self.assertFalse(Friendship.objects.exists())
        self.befriend()
        self.client.force_login(self.aziz)
        self.client.post(reverse("friends_remove", args=["fr_laylo"]))
        self.assertFalse(social.are_friends(self.aziz, self.laylo))

    def test_only_the_receiver_can_answer_a_request(self):
        self.add_by_code(self.aziz, self.laylo)
        row = Friendship.objects.get()
        self.client.force_login(self.aziz)  # the sender tries to accept their own request
        self.client.post(reverse("friends_respond", args=[row.pk, "accept"]))
        self.assertFalse(social.are_friends(self.aziz, self.laylo))

    def test_classmates_are_suggested_and_can_be_added(self):
        teacher = User.objects.create_user("fr_t", password="x")
        teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        room = Classroom.objects.create(teacher=teacher, name="Friends class", is_active=True)
        for user in (self.aziz, self.laylo):
            ClassroomMembership.objects.create(classroom=room, user=user, role="student", status="approved", approved_at=timezone.now())
        stranger = student("fr_stranger")
        self.client.force_login(self.aziz)
        page = self.client.get(reverse("friends"))
        self.assertContains(page, "Your classmates")
        self.assertContains(page, f'name="suggest" value="{self.laylo.pk}"')
        self.client.post(reverse("friends_add"), {"suggest": stranger.pk})  # not a classmate: refused
        self.assertFalse(Friendship.objects.filter(to_user=stranger).exists())
        self.client.post(reverse("friends_add"), {"suggest": self.laylo.pk})
        self.assertTrue(Friendship.objects.filter(from_user=self.aziz, to_user=self.laylo).exists())

    def test_friends_can_visit_each_others_room_and_trophies(self):
        UserAchievement.objects.create(user=self.laylo, code="streak_3", title="Three-Day Spark", description="x")
        self.client.force_login(self.aziz)
        self.assertEqual(self.client.get(reverse("friend_room", args=["fr_laylo"])).status_code, 404)  # not friends yet
        self.befriend()
        self.client.force_login(self.aziz)
        page = self.client.get(reverse("friend_room", args=["fr_laylo"]))
        self.assertContains(page, "Laylo Usmonova's room")
        self.assertContains(page, "Three-Day Spark")
        self.assertContains(page, 'class="mr-trophy is-earned"', count=1)
        self.assertNotContains(page, "Customize your room")  # visiting is read-only
        self.assertNotContains(page, "data-equip-url")
