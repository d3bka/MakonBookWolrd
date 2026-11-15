"""V73 A-to-Z: World views that had no HTTP-level tests (queue, public join, kick, seat swap, start, leave)."""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.sat.models import English_Question, Math_Question, Test
from apps.world.models import WorldMatch, WorldMultiplayerRoom, WorldMultiplayerSeat, WorldMultiplayerSeatSwapRequest


def student(name):
    return User.objects.create_user(name, password="x", first_name=name.title(), last_name="S")


@override_settings(MAKONBOOK_WORLD_ENABLED=True)
class WorldViewsJourneyTests(TestCase):
    def setUp(self):
        test = Test.objects.create(name="WORLD-VIEWS-V73")
        for i in range(1, 25):
            Math_Question.objects.create(test=test, module="1", number=i, question=f"Math {i}",
                                         a="1", b="2", c="3", d="4", answer="A", written=False)
            English_Question.objects.create(test=test, module="1", number=i, question=f"RW {i}",
                                            a="A1", b="B1", c="C1", d="D1", answer="A", response_type="multiple_choice")
        self.ann, self.bob, self.cat, self.dan = (student(f"wv_{n}") for n in ("ann", "bob", "cat", "dan"))

    def as_(self, user):
        self.client.force_login(user)
        return self.client

    # ---------------------------------------------------------------- 1v1 queue
    def test_queue_join_cancel_and_only_the_owner_can_cancel(self):
        response = self.as_(self.ann).post(reverse("world_queue_join"), {"subject": "math", "mode": "ranked"})
        self.assertEqual(response.status_code, 200, response.content)
        match_id = response.json()["match_id"]
        self.assertEqual(self.as_(self.bob).post(reverse("world_queue_cancel", args=[match_id])).status_code, 409)
        self.assertEqual(self.as_(self.ann).post(reverse("world_queue_cancel", args=[match_id])).status_code, 200)
        self.assertEqual(WorldMatch.objects.get(pk=match_id).status, WorldMatch.STATUS_CANCELLED)
        self.assertEqual(self.as_(self.ann).post(reverse("world_queue_cancel", args=[match_id])).status_code, 409)

    def test_cancel_never_overwrites_a_match_that_was_just_matched(self):
        match_id = self.as_(self.ann).post(reverse("world_queue_join"), {"subject": "math", "mode": "ranked"}).json()["match_id"]
        stale = WorldMatch.objects.get(pk=match_id)  # ann's tab still thinks it is waiting
        WorldMatch.objects.filter(pk=match_id).update(status=WorldMatch.STATUS_ACTIVE, player2=self.bob)
        from apps.world.services import cancel_waiting_match
        self.assertFalse(cancel_waiting_match(stale, self.ann))
        self.assertEqual(WorldMatch.objects.get(pk=match_id).status, WorldMatch.STATUS_ACTIVE)

    def test_two_players_meet_and_heartbeat(self):
        first = self.as_(self.ann).post(reverse("world_queue_join"), {"subject": "math", "mode": "ranked"}).json()
        second = self.as_(self.bob).post(reverse("world_queue_join"), {"subject": "math", "mode": "ranked"}).json()
        self.assertEqual(first["match_id"], second["match_id"])
        match_id = first["match_id"]
        beat = self.as_(self.ann).post(reverse("world_match_heartbeat", args=[match_id]))
        self.assertEqual(beat.json()["status"], WorldMatch.STATUS_ACTIVE)
        self.assertEqual(self.as_(self.cat).post(reverse("world_match_heartbeat", args=[match_id])).status_code, 404)

    def test_bad_queue_requests(self):
        response = self.as_(self.ann).post(reverse("world_queue_join"), {"subject": "chemistry", "mode": "ranked"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.as_(self.ann).get(reverse("world_queue_join")).status_code, 405)

    # ---------------------------------------------------------------- multiplayer lobby
    def create_room(self, host, **extra):
        data = {"subject": "math", "capacity": 4, "question_count": 5, "access_type": "private", **extra}
        response = self.as_(host).post(reverse("world_multiplayer_create"), data)
        self.assertEqual(response.status_code, 200, response.content)
        return WorldMultiplayerRoom.objects.get(pk=response.json()["room_id"])

    def join(self, user, room):
        response = self.as_(user).post(reverse("world_multiplayer_join"), {"join_code": room.join_code})
        self.assertEqual(response.status_code, 200, response.content)

    def test_public_join_fills_one_room_then_opens_another(self):
        url = reverse("world_multiplayer_public_join")
        first = self.as_(self.ann).post(url, {"subject": "math", "capacity": 3}).json()
        self.assertTrue(first["created_room"], first)
        for user in (self.bob, self.cat):
            joined = self.as_(user).post(url, {"subject": "math", "capacity": 3}).json()
            self.assertEqual((joined["room_id"], joined["created_room"]), (first["room_id"], False))
        late = self.as_(self.dan).post(url, {"subject": "math", "capacity": 3}).json()
        self.assertNotEqual(late["room_id"], first["room_id"])  # the 3-seat room is full
        self.assertEqual(self.as_(student("wv_eve")).post(url, {"subject": "math", "capacity": 2}).status_code, 400)
        junk = self.as_(student("wv_fay")).post(url, {"subject": "math", "capacity": "x", "question_count": "y"})
        self.assertEqual(junk.status_code, 200)  # junk numbers fall back to the defaults

    def test_host_kicks_a_player_but_guests_cannot(self):
        room = self.create_room(self.ann)
        self.join(self.bob, room)
        self.join(self.cat, room)
        url = reverse("world_multiplayer_kick", args=[room.id])
        self.assertEqual(self.as_(self.bob).post(url, {"user_id": self.cat.id}).status_code, 400)
        self.assertEqual(self.as_(self.ann).post(url, {"user_id": "zz"}).status_code, 400)
        self.assertEqual(self.as_(self.ann).post(url, {"user_id": self.ann.id}).status_code, 400)
        self.assertEqual(self.as_(self.ann).post(url, {"user_id": self.cat.id}).status_code, 200)
        self.assertFalse(WorldMultiplayerSeat.objects.filter(room=room, user=self.cat, is_active=True).exists())
        status = self.as_(self.cat).get(reverse("world_multiplayer_status", args=[room.id])).json()
        self.assertTrue(status["removed"])
        self.assertEqual(self.as_(self.dan).post(url, {"user_id": self.bob.id}).status_code, 404)  # not in the room

    def test_seat_swap_request_accept_and_cancel_in_2v2(self):
        room = self.create_room(self.ann, game_mode="team_2v2")
        for user in (self.bob, self.cat, self.dan):
            self.join(user, room)
        team = {s.user_id: s.team for s in WorldMultiplayerSeat.objects.filter(room=room, is_active=True)}
        other_team = next(uid for uid, t in team.items() if t != team[self.ann.id])
        ask = self.as_(self.ann).post(reverse("world_multiplayer_swap_request", args=[room.id]), {"target_user_id": other_team})
        self.assertEqual(ask.status_code, 200, ask.content)
        request_id = ask.json()["swap_request_id"]
        target = User.objects.get(pk=other_team)
        junk = self.as_(target).post(reverse("world_multiplayer_swap_respond", args=[room.id]), {"action": "accept", "request_id": "zz"})
        self.assertEqual(junk.status_code, 409)
        bad_action = self.as_(target).post(reverse("world_multiplayer_swap_respond", args=[room.id]), {"action": "maybe", "request_id": request_id})
        self.assertEqual(bad_action.status_code, 400)
        accept = self.as_(target).post(reverse("world_multiplayer_swap_respond", args=[room.id]), {"action": "accept", "request_id": request_id})
        self.assertEqual(accept.status_code, 200, accept.content)
        self.assertEqual(WorldMultiplayerSeatSwapRequest.objects.get(pk=request_id).status, WorldMultiplayerSeatSwapRequest.STATUS_ACCEPTED)
        swapped = {s.user_id: s.team for s in WorldMultiplayerSeat.objects.filter(room=room, is_active=True)}
        self.assertEqual(swapped[self.ann.id], team[other_team])

        again = self.as_(self.ann).post(reverse("world_multiplayer_swap_request", args=[room.id]), {"target_user_id": other_team}).json()
        cancel = self.as_(self.ann).post(reverse("world_multiplayer_swap_cancel", args=[room.id]), {"request_id": again["swap_request_id"]})
        self.assertEqual(cancel.status_code, 200)

    def test_swap_is_only_for_2v2_rooms(self):
        room = self.create_room(self.ann)
        self.join(self.bob, room)
        response = self.as_(self.ann).post(reverse("world_multiplayer_swap_request", args=[room.id]), {"target_user_id": self.bob.id})
        self.assertEqual(response.status_code, 409)

    def test_start_needs_the_host_and_ready_players(self):
        room = self.create_room(self.ann)
        self.join(self.bob, room)
        start = reverse("world_multiplayer_start", args=[room.id])
        self.assertEqual(self.as_(self.ann).post(start).status_code, 409)  # only 2 players
        self.join(self.cat, room)
        self.assertEqual(self.as_(self.bob).post(start).status_code, 409)  # not the host
        self.assertEqual(self.as_(self.ann).post(start).status_code, 409)  # nobody is ready
        for user in (self.ann, self.bob, self.cat):
            self.as_(user).post(reverse("world_multiplayer_ready", args=[room.id]), {"ready": "1"})
        response = self.as_(self.ann).post(start)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotEqual(WorldMultiplayerRoom.objects.get(pk=room.pk).status, WorldMultiplayerRoom.STATUS_LOBBY)

    def test_leave_the_lobby_json_and_form(self):
        room = self.create_room(self.ann)
        self.join(self.bob, room)
        left = self.as_(self.bob).post(reverse("world_multiplayer_leave", args=[room.id]), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(left.json()["ok"], True)
        self.assertFalse(WorldMultiplayerSeat.objects.filter(room=room, user=self.bob, is_active=True).exists())
        form = self.as_(self.ann).post(reverse("world_multiplayer_leave", args=[room.id]), HTTP_ACCEPT="text/html")
        self.assertRedirects(form, reverse("world_multiplayer_home"), fetch_redirect_response=False)

    def test_teachers_are_kept_out_of_world_actions(self):
        from django.contrib.auth.models import Group
        teacher = student("wv_teacher")
        teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        for name in ("world_queue_join", "world_multiplayer_public_join", "world_multiplayer_create"):
            self.assertEqual(self.as_(teacher).post(reverse(name), {"subject": "math"}).status_code, 403, name)

    # ---------------------------------------------------------------- rematch offer page / decline
    def finished_match(self):
        from django.utils import timezone
        from apps.world.services import join_queue
        join_queue(self.ann, subject="math", mode="quick")
        match, _ = join_queue(self.bob, subject="math", mode="quick")
        WorldMatch.objects.filter(pk=match.pk).update(status=WorldMatch.STATUS_COMPLETED, completed_at=timezone.now())
        return match

    def test_rematch_offer_page_and_decline(self):
        source = self.finished_match()
        invite_id = self.as_(self.ann).post(reverse("world_rematch_request", args=[source.pk])).json()["invite_id"]
        self.assertEqual(self.as_(self.cat).get(reverse("world_rematch_offer", args=[invite_id])).status_code, 404)
        self.assertEqual(self.as_(self.bob).get(reverse("world_rematch_offer", args=[invite_id])).status_code, 200)
        self.assertEqual(self.as_(self.cat).post(reverse("world_rematch_decline", args=[invite_id])).status_code, 409)
        declined = self.as_(self.bob).post(reverse("world_rematch_decline", args=[invite_id]))
        self.assertEqual(declined.status_code, 200)
        self.assertEqual(WorldMatch.objects.get(pk=invite_id).status, WorldMatch.STATUS_CANCELLED)
        # declining twice, or accepting after a decline, does nothing
        self.assertEqual(self.as_(self.bob).post(reverse("world_rematch_decline", args=[invite_id])).status_code, 409)
        self.assertEqual(self.as_(self.bob).post(reverse("world_rematch_accept", args=[invite_id])).status_code, 409)
