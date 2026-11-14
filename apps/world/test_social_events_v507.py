"""V50.7 World: friend duels and events (cooperative goals, seasonal cups)."""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.gamification.models import Friendship, XPEvent
from apps.sat.models import English_Question, MakonNotification, Math_Question, Test
from apps.world import events
from apps.world.models import WorldEvent, WorldMatch
from apps.world.services import FRIEND_CHALLENGE_SECONDS, queue_seconds_remaining


def student(username):
    return User.objects.create_user(username, password="x", first_name=username.title(), last_name="S")


def friends(a, b):
    Friendship.objects.create(from_user=a, to_user=b, status=Friendship.STATUS_ACCEPTED)


@override_settings(MAKONBOOK_WORLD_ENABLED=True)
class FriendDuelTests(TestCase):
    def setUp(self):
        self.a, self.b, self.c = student("duel_a"), student("duel_b"), student("duel_c")
        friends(self.a, self.b)
        test = Test.objects.create(name="WORLD-V507")  # a verified pool, like the World V50.3 tests
        for i in range(1, 7):
            Math_Question.objects.create(test=test, module="1", number=i, question=f"Math {i}",
                                         a="1", b="2", c="3", d="4", answer="A", written=False)
            English_Question.objects.create(test=test, module="1", number=i, question=f"RW {i}",
                                            a="A1", b="B1", c="C1", d="D1", answer="A", response_type="multiple_choice")

    def test_challenge_a_friend_creates_an_unranked_private_duel(self):
        self.client.force_login(self.a)
        response = self.client.post(reverse("world_challenge_friend", args=["duel_b"]), {"subject": "math"})
        match = WorldMatch.objects.get()
        self.assertRedirects(response, reverse("world_match", args=[match.id]), fetch_redirect_response=False)
        self.assertEqual((match.status, match.mode, match.invitee, match.player1), ("waiting", "quick", self.b, self.a))
        self.assertGreater(queue_seconds_remaining(match), 60)  # friends get minutes, not the 60 s queue
        self.assertLessEqual(queue_seconds_remaining(match), FRIEND_CHALLENGE_SECONDS)
        self.assertTrue(MakonNotification.objects.filter(user=self.b, type="social", title__contains="duel").exists())
        self.client.force_login(self.b)
        incoming = self.client.get(reverse("world_rematch_incoming")).json()["invite"]
        self.assertTrue(incoming["friend_challenge"])
        self.assertEqual(incoming["mode"], "Unranked")
        accepted = self.client.post(reverse("world_rematch_accept", args=[match.id])).json()
        self.assertTrue(accepted["ok"])
        match.refresh_from_db()
        self.assertEqual((match.status, match.player2), ("active", self.b))

    def test_strangers_cannot_be_challenged(self):
        self.client.force_login(self.a)
        response = self.client.post(reverse("world_challenge_friend", args=["duel_c"]), {"subject": "math"}, follow=True)
        self.assertContains(response, "only challenge your friends")
        self.assertFalse(WorldMatch.objects.exists())

    def test_crossed_challenges_start_the_duel(self):
        self.client.force_login(self.a)
        self.client.post(reverse("world_challenge_friend", args=["duel_b"]), {"subject": "rw"})
        self.client.force_login(self.b)
        self.client.post(reverse("world_challenge_friend", args=["duel_a"]), {"subject": "rw"})
        self.assertEqual(WorldMatch.objects.count(), 1)
        self.assertEqual(WorldMatch.objects.get().status, "active")

    def test_friends_page_offers_duels_while_world_is_open(self):
        self.client.force_login(self.a)
        page = self.client.get(reverse("friends"))
        self.assertContains(page, reverse("world_challenge_friend", args=["duel_b"]))
        self.assertContains(page, "data-challenge-toast")


@override_settings(MAKONBOOK_WORLD_ENABLED=False)
class ClosedWorldTests(TestCase):
    def test_duels_and_events_stay_closed_with_world(self):
        a, b = student("closed_a"), student("closed_b")
        friends(a, b)
        self.client.force_login(a)
        self.assertEqual(self.client.post(reverse("world_challenge_friend", args=["closed_b"])).status_code, 423)
        self.assertRedirects(self.client.get(reverse("world_events")), reverse("student_dashboard_root"), fetch_redirect_response=False)
        self.assertNotContains(self.client.get(reverse("friends")), "data-challenge-toast")


@override_settings(MAKONBOOK_WORLD_ENABLED=True)
class WorldEventTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.p = [student(f"ev_{i}") for i in range(4)]

    def play(self, a, b, winner, when=None, score=(300, 100)):
        return WorldMatch.objects.create(
            subject="math", mode="quick", status="completed", player1=a, player2=b, winner=winner,
            player1_score=score[0], player2_score=score[1], completed_at=when or self.now - timedelta(hours=1),
        )

    def event(self, **kw):
        defaults = dict(title="Test cup", kind=WorldEvent.KIND_COMPETITION, metric=WorldEvent.METRIC_WINS,
                        starts_at=self.now - timedelta(days=1), ends_at=self.now + timedelta(days=1), reward_xp=40)
        defaults.update(kw)
        return WorldEvent.objects.create(**defaults)

    def test_wins_inside_the_window_count_and_pair_farming_is_capped(self):
        a, b, c, _ = self.p
        cup = self.event()
        for _ in range(5):  # same pair, same day: only 3 count
            self.play(a, b, a)
        self.play(c, b, c)
        self.play(a, c, a, when=self.now - timedelta(days=3))  # before the event
        self.assertEqual(events.standings(cup), {a.pk: 3, c.pk: 1})

    def test_competition_pays_the_top_players_once(self):
        a, b, c, d = self.p
        cup = self.event(top_rewarded=2, starts_at=self.now - timedelta(days=2), ends_at=self.now - timedelta(minutes=1))
        self.play(a, b, a); self.play(a, c, a); self.play(c, d, c); self.play(b, d, b)
        events.settle(cup)
        events.settle(cup)  # idempotent
        rewarded = set(XPEvent.objects.filter(source_key__startswith=f"world-event:{cup.pk}:").values_list("user_id", flat=True))
        self.assertEqual(len(rewarded), 2)
        self.assertIn(a.pk, rewarded)
        cup.refresh_from_db()
        self.assertIsNotNone(cup.settled_at)

    def test_cooperative_goal_rewards_everyone_who_joined(self):
        a, b, c, d = self.p
        coop = self.event(kind=WorldEvent.KIND_COOP, metric=WorldEvent.METRIC_MATCHES, goal=4,
                          starts_at=self.now - timedelta(days=2), ends_at=self.now - timedelta(minutes=1))
        self.play(a, b, a); self.play(c, d, None)
        self.assertEqual(sum(events.standings(coop).values()), 4)
        events.settle(coop)
        self.assertEqual(XPEvent.objects.filter(source_key__startswith=f"world-event:{coop.pk}:").count(), 4)

    def test_missed_cooperative_goal_pays_nothing(self):
        a, b, _, _ = self.p
        coop = self.event(kind=WorldEvent.KIND_COOP, metric=WorldEvent.METRIC_WINS, goal=50,
                          starts_at=self.now - timedelta(days=2), ends_at=self.now - timedelta(minutes=1))
        self.play(a, b, a)
        events.settle(coop)
        self.assertFalse(XPEvent.objects.filter(source_key__startswith=f"world-event:{coop.pk}:").exists())

    def test_events_page_shows_live_progress_and_my_rank(self):
        a, b, _, _ = self.p
        self.event(title="Navro'z Cup")
        self.event(title="Team goal", kind=WorldEvent.KIND_COOP, metric=WorldEvent.METRIC_MATCHES, goal=10)
        self.play(a, b, a)
        self.client.force_login(a)
        page = self.client.get(reverse("world_events"))
        self.assertContains(page, "Navro&#x27;z Cup")
        self.assertContains(page, "You're <b>#1</b>")
        self.assertContains(page, 'aria-valuenow="20"')  # 2 of 10 matches
        self.assertContains(page, reverse("world_events"))  # Events tab in the World bar

    def test_seasonal_cup_is_created_once_per_season(self):
        cup, created = events.ensure_seasonal_competition(date(2027, 1, 15))
        again, created_again = events.ensure_seasonal_competition(date(2027, 2, 20))
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(cup.pk, again.pk)
        self.assertEqual((cup.season, cup.title), ("winter", "Qish Cup 2026/27"))
        self.assertEqual(timezone.localtime(cup.starts_at).date(), date(2026, 12, 1))
        self.assertEqual(timezone.localtime(cup.ends_at).date(), date(2027, 3, 1))
        spring, _ = events.ensure_seasonal_competition(date(2027, 3, 21))
        self.assertEqual(spring.title, "Navro'z Cup 2027")
