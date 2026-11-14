"""V50.4.20 multiplayer: Survival, Classroom Battles, early finish, placements + XP, lobby ghosts."""
from datetime import timedelta
from types import SimpleNamespace

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.gamification.models import XPEvent
from apps.sat.models import Classroom, ClassroomMembership, English_Question, Math_Question, Test
from apps.world import services as svc
from apps.world.models import WorldMultiplayerRoom, WorldMultiplayerSeat


def student(name):
    return User.objects.create_user(name, password="x", first_name=name.title(), last_name="S")


@override_settings(MAKONBOOK_WORLD_ENABLED=True)
class MultiplayerModesTests(TestCase):
    def setUp(self):
        test = Test.objects.create(name="WORLD-MP-V50420")
        for i in range(1, 25):
            Math_Question.objects.create(test=test, module="1", number=i, question=f"Math {i}",
                                         a="1", b="2", c="3", d="4", answer="A", written=False)
            English_Question.objects.create(test=test, module="1", number=i, question=f"RW {i}",
                                            a="A1", b="B1", c="C1", d="D1", answer="A", response_type="multiple_choice")
        self.p = [student(f"mp_{n}") for n in ("ann", "bob", "cat", "dan")]

    # ---------------------------------------------------------------- helpers
    def room(self, players, **kw):
        host, *rest = players
        room = svc.create_multiplayer_room(host, subject="math", **kw)
        for user in rest:
            svc.join_multiplayer_room(user, join_code=room.join_code)
        for user in players:
            svc.set_multiplayer_ready(self.fresh(room), user, True)
        svc.start_multiplayer_room(self.fresh(room), host)
        for user in players:
            svc.touch_multiplayer_presence(self.fresh(room), user, arena_ready=True)
        self.go(room)
        return self.fresh(room)

    def fresh(self, room):
        return WorldMultiplayerRoom.objects.get(pk=room.pk)

    def go(self, room):
        """Skip the countdown / reveal so the current question is open."""
        WorldMultiplayerRoom.objects.filter(pk=room.pk).update(question_started_at=timezone.now() - timedelta(seconds=2))

    def answer(self, room, user, correct):
        ticket = svc.issue_multiplayer_question_ticket(self.fresh(room), user)
        return svc.submit_multiplayer_answer(self.fresh(room), user, ticket.token, "A" if correct else "B")

    def round(self, room, results):
        for user, correct in results.items():
            self.answer(room, user, correct)
        self.go(room)

    def seat(self, room, user):
        return WorldMultiplayerSeat.objects.get(room=room, user=user)

    def xp(self, room, user):
        return XPEvent.objects.filter(source_key=f"world-mp:{room.pk}:{user.pk}").values_list("amount", flat=True).first()

    # ---------------------------------------------------------------- survival
    def test_survival_lives_elimination_and_last_one_standing(self):
        a, b, c = self.p[:3]
        room = self.room([a, b, c], capacity=3, question_count=10, game_mode="survival")
        self.round(room, {a: True, b: True, c: False})
        self.round(room, {a: True, b: True, c: False})
        self.assertEqual(self.seat(room, c).lives, 1)
        self.round(room, {a: True, b: False, c: False})  # c is out, b loses one
        self.assertEqual(self.seat(room, c).eliminated_at_index, 2)
        self.assertEqual(self.seat(room, b).lives, 2)
        with self.assertRaisesMessage(ValueError, "out of lives"):
            svc.issue_multiplayer_question_ticket(self.fresh(room), c)  # spectators get no question
        payload = svc.multiplayer_play_payload(self.fresh(room), viewer=c, include_question=True)
        self.assertTrue(payload["my_eliminated"])
        self.assertIsNone(payload.get("question"))
        self.round(room, {a: True, b: False})  # only survivors answer now
        self.round(room, {a: True, b: False})
        room = self.fresh(room)
        self.assertEqual(room.status, "completed")  # one survivor left with questions remaining
        self.assertEqual([self.seat(room, u).placement for u in (a, b, c)], [1, 2, 3])
        self.assertEqual([self.xp(room, u) for u in (a, b, c)], [50, 30, 20])

    def test_survival_forgives_a_question_everyone_misses(self):
        a, b, c = self.p[:3]
        room = self.room([a, b, c], capacity=3, question_count=5, game_mode="survival")
        for user in (a, b, c):
            self.answer(room, user, False)  # stay in the reveal phase
        self.assertEqual([self.seat(room, u).lives for u in (a, b, c)], [3, 3, 3])
        reveal = svc.multiplayer_play_payload(self.fresh(room), viewer=a)
        self.assertTrue(reveal["round_reveal"])
        self.assertTrue(all(row.get("forgiven") and not row["lost_life"] for row in reveal["reveal_ranking"]))
        self.assertEqual((self.fresh(room).status, reveal["alive"]), ("active", 3))

    # ---------------------------------------------------------------- early finish + XP
    def test_battle_ends_when_opponents_leave(self):
        a, b, c = self.p[:3]
        room = self.room([a, b, c], capacity=3, question_count=10)
        self.round(room, {a: True, b: True, c: True})
        svc.leave_multiplayer_room(self.fresh(room), b)
        self.assertEqual(self.fresh(room).status, "active")
        svc.leave_multiplayer_room(self.fresh(room), c)
        room = self.fresh(room)
        self.assertEqual(room.status, "completed")  # a no longer plays 9 questions alone
        self.assertEqual(self.seat(room, a).placement, 1)
        self.assertEqual(self.xp(room, a), 50)
        self.assertIsNone(self.xp(room, b))  # leavers earn nothing
        self.assertEqual(self.seat(room, b).placement, 2)

    def test_2v2_ends_when_a_whole_team_leaves(self):
        room = self.room(self.p, capacity=4, question_count=10, game_mode="team_2v2")
        team_b = [s.user for s in WorldMultiplayerSeat.objects.filter(room=room, team="b")]
        team_a = [s.user for s in WorldMultiplayerSeat.objects.filter(room=room, team="a")]
        self.round(room, {u: True for u in self.p})
        for user in team_b:
            svc.leave_multiplayer_room(self.fresh(room), user)
        room = self.fresh(room)
        self.assertEqual(room.status, "completed")
        self.assertEqual([self.xp(room, u) for u in team_a], [40, 40])

    def test_ties_share_a_place(self):
        seats = [SimpleNamespace(pk=1, score=300), SimpleNamespace(pk=2, score=300), SimpleNamespace(pk=3, score=100)]
        self.assertEqual(svc._competition_places(seats, key=lambda s: (s.score,)), {1: 1, 2: 1, 3: 3})

    def test_afk_players_earn_no_xp(self):
        a, b, c = self.p[:3]
        room = self.room([a, b, c], capacity=3, question_count=5)
        for _ in range(5):
            self.answer(room, a, True)
            self.answer(room, b, False)
            WorldMultiplayerRoom.objects.filter(pk=room.pk).update(question_started_at=timezone.now() - timedelta(minutes=10))
            svc.expire_multiplayer_question_if_needed(self.fresh(room))  # c times out every question
            self.go(room)
        room = self.fresh(room)
        self.assertEqual(room.status, "completed")
        self.assertIsNotNone(self.xp(room, b))  # answered (wrong) — still played
        self.assertIsNone(self.xp(room, c))
        self.assertEqual(self.seat(room, c).xp_awarded, 0)

    # ---------------------------------------------------------------- classroom battles
    def classroom(self, members):
        teacher = User.objects.create_user("mp_teacher", password="x")
        teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        room = Classroom.objects.create(teacher=teacher, name="SAT Group 7", is_active=True)
        for user in members:
            ClassroomMembership.objects.create(classroom=room, user=user, role="student", status="approved", approved_at=timezone.now())
        return room

    def test_classroom_battle_is_only_for_classmates(self):
        a, b, c, outsider = self.p
        group = self.classroom([a, b, c])
        with self.assertRaisesMessage(ValueError, "Choose one of your classrooms"):
            svc.create_multiplayer_room(a, subject="math", game_mode="classroom")
        with self.assertRaisesMessage(ValueError, "Choose one of your classrooms"):
            svc.create_multiplayer_room(outsider, subject="math", game_mode="classroom", classroom_id=group.pk)
        room = svc.create_multiplayer_room(a, subject="math", game_mode="classroom", classroom_id=group.pk,
                                           access_type="public", capacity=3)
        self.assertEqual((room.access_type, room.classroom), ("private", group))  # never public
        with self.assertRaisesMessage(ValueError, "only for students of SAT Group 7"):
            svc.join_multiplayer_room(outsider, join_code=room.join_code)
        with self.assertRaisesMessage(ValueError, "stay inside the classroom"):
            svc.set_multiplayer_access_type(room, a, "public")
        with self.assertRaisesMessage(ValueError, "classroom list"):
            svc.join_public_multiplayer_room(outsider, subject="math", game_mode="classroom")
        listed = svc.classroom_battles_for(b)
        self.assertEqual([row["room"].pk for row in listed], [room.pk])
        self.assertEqual(svc.classroom_battles_for(outsider), [])
        svc.join_multiplayer_room(b, join_code=room.join_code)
        svc.join_multiplayer_room(c, join_code=room.join_code)
        for user in (a, b, c):
            svc.set_multiplayer_ready(self.fresh(room), user, True)
        self.assertEqual(svc.start_multiplayer_room(self.fresh(room), a).status, "active")

    def test_world_home_offers_every_mode_and_open_classroom_battles(self):
        a, b, c, _ = self.p
        group = self.classroom([a, b])
        svc.create_multiplayer_room(a, subject="math", game_mode="classroom", classroom_id=group.pk, capacity=3)
        self.client.force_login(b)
        page = self.client.get(reverse("world_multiplayer_home"))
        for mode in ("ffa", "team_2v2", "survival", "classroom"):
            self.assertContains(page, f'name="game_mode" value="{mode}"')
        self.assertContains(page, "Classroom battles")
        self.assertContains(page, "SAT Group 7")
        self.client.force_login(c)  # no classroom: the option is shown but disabled
        self.assertContains(self.client.get(reverse("world_multiplayer_home")), 'value="classroom" disabled')

    # ---------------------------------------------------------------- lobby ghosts
    def test_lobby_ghosts_are_freed_and_host_moves_on(self):
        a, b, c, _ = self.p
        room = svc.create_multiplayer_room(a, subject="math")
        svc.join_multiplayer_room(b, join_code=room.join_code)
        WorldMultiplayerSeat.objects.filter(room=room, user=a).update(last_seen_at=timezone.now() - timedelta(minutes=10))
        room = svc.reconcile_multiplayer_presence(self.fresh(room))
        self.assertFalse(WorldMultiplayerSeat.objects.filter(room=room, user=a).exists())
        self.assertEqual(self.fresh(room).host, b)

    def test_public_matchmaking_skips_dead_lobbies(self):
        a, b, _, _ = self.p
        dead, _, _ = svc.join_public_multiplayer_room(a, subject="math", game_mode="survival")
        WorldMultiplayerSeat.objects.filter(room=dead).update(last_seen_at=timezone.now() - timedelta(minutes=10))
        joined, _, created = svc.join_public_multiplayer_room(b, subject="math", game_mode="survival")
        self.assertNotEqual(joined.pk, dead.pk)
        self.assertTrue(created)
        self.assertEqual(self.fresh(dead).status, "cancelled")
