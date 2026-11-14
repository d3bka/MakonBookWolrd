"""V50.6 MakonRoom: cosmetic items unlock from real progress and only unlocked items can be placed."""
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.gamification import room
from apps.gamification.models import GamificationProfile, RoomLayout, UserAchievement
from apps.gamification.services import ensure_gamification_profile

SCENE = Path(settings.BASE_DIR) / "templates/gamification/_room_scene.html"


class RoomCatalogTests(SimpleTestCase):
    def test_every_slot_has_exactly_one_free_starter_item(self):
        for slot in room.SLOT_KEYS:
            with self.subTest(slot=slot):
                defaults = [i for i in room.ITEMS if i.slot == slot and i.is_default]
                self.assertEqual(len(defaults), 1)
                self.assertIn(slot, room.THUMB_VIEWBOX)

    def test_every_item_is_drawn_in_the_scene(self):
        scene = SCENE.read_text(encoding="utf-8")
        for item in room.ITEMS:
            with self.subTest(item=item.code):
                self.assertIn(f'id="ri-{item.code}"', scene)

    def test_requirements_only_use_known_progress(self):
        for item in room.ITEMS:
            if item.requirement:
                self.assertIn(item.requirement[0], room.REQUIREMENT_LABELS)


class MakonRoomTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user("room_student", password="x", first_name="Aziz", last_name="K")
        self.client.force_login(self.student)
        self.url = reverse("makon_room")
        self.equip_url = reverse("makon_room_equip")

    def give_xp(self, xp):
        profile = ensure_gamification_profile(self.student)
        GamificationProfile.objects.filter(pk=profile.pk).update(xp_total=xp)

    def test_page_shows_the_room_with_starter_items(self):
        page = self.client.get(self.url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "data-room-scene")
        self.assertContains(page, 'id="pdBodyr"')  # Mako lives in the room
        self.assertNotContains(page, "data-mako-companion")  # ...so the corner one stays away
        for code in room.DEFAULTS.values():
            self.assertContains(page, f'data-room-item="{code}" data-room-slot=')
        self.assertContains(page, "Reach level 3")

    def test_locked_and_unknown_items_are_refused(self):
        locked = self.client.post(self.equip_url, {"slot": "wallpaper", "item": "wp_ikat"})
        self.assertEqual(locked.status_code, 403)
        self.assertIn("Reach level 3", locked.json()["error"])
        self.assertEqual(self.client.post(self.equip_url, {"slot": "rug", "item": "wp_ikat"}).status_code, 400)
        self.assertEqual(self.client.post(self.equip_url, {"slot": "wallpaper", "item": "nope"}).status_code, 400)
        self.assertFalse(RoomLayout.objects.filter(user=self.student).exclude(slots={}).exists())

    def test_progress_unlocks_and_the_choice_is_saved(self):
        self.give_xp(300)  # level 3
        response = self.client.post(self.equip_url, {"slot": "wallpaper", "item": "wp_ikat"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["equipped"]["wallpaper"], "wp_ikat")
        self.assertEqual(RoomLayout.objects.get(user=self.student).slots, {"wallpaper": "wp_ikat"})
        page = self.client.get(self.url)
        self.assertContains(page, '<use href="#ri-wp_ikat" data-room-item="wp_ikat" data-room-slot="wallpaper"/>')

    def test_an_item_that_is_no_longer_unlocked_falls_back_to_the_starter(self):
        RoomLayout.objects.create(user=self.student, slots={"wallpaper": "wp_night", "rug": "garbage"})
        page = self.client.get(self.url)
        self.assertContains(page, '<use href="#ri-wp_lavender" data-room-item="wp_lavender" data-room-slot="wallpaper"/>')
        self.assertContains(page, '<use href="#ri-rug_mat" data-room-item="rug_mat" data-room-slot="rug"/>')

    def test_new_unlocks_are_announced_once(self):
        self.give_xp(300)
        first = self.client.get(self.url)
        self.assertContains(first, "New for your room")
        self.assertContains(first, "Atlas ikat")
        second = self.client.get(self.url)
        self.assertNotContains(second, "New for your room")

    def test_achievements_become_trophies(self):
        UserAchievement.objects.create(user=self.student, code="first_xp", title="First Step", description="x")
        page = self.client.get(self.url)
        self.assertContains(page, 'class="mr-trophy is-earned"', count=1)
        self.assertContains(page, 'data-trophy="first_xp"')

    def test_trophies_catch_up_with_existing_progress(self):
        self.give_xp(300)  # "First Step" is earned but was never evaluated
        page = self.client.get(self.url)
        self.assertTrue(UserAchievement.objects.filter(user=self.student, code="first_xp").exists())
        self.assertContains(page, 'class="mr-trophy is-earned"')

    def test_staff_do_not_get_a_room(self):
        teacher = User.objects.create_user("room_teacher", password="x")
        teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        self.client.force_login(teacher)
        self.assertRedirects(self.client.get(self.url), reverse("student_dashboard_root"), fetch_redirect_response=False)
        self.assertEqual(self.client.post(self.equip_url, {"slot": "rug", "item": "rug_mat"}).status_code, 403)

    def test_sidebar_links_to_the_room(self):
        page = self.client.get(reverse("settings_page"))
        self.assertContains(page, 'data-nav-key="room"')
