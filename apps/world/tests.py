from pathlib import Path
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.contrib.auth.models import Group, User
from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase
from django.utils import timezone
from django.urls import reverse

from apps.sat.models import English_Question, MakonNotification, Math_Question, Test

from apps.gamification.models import XPEvent

from .models import GameQuestionPool, WorldAnswer, WorldMatch, WorldQuestionTicket, WorldRating, WorldMultiplayerRoom, WorldMultiplayerSeat, WorldMultiplayerAnswer, WorldMultiplayerQuestionTicket, WorldMultiplayerSeatSwapRequest
from .services import (
    _finalize_locked,
    ensure_ratings,
    heartbeat,
    issue_question_ticket,
    join_queue,
    next_question_index,
    reconcile_waiting_match,
    submit_answer,
    submit_answer_by_token,
    sync_question_pool,
    create_multiplayer_room,
    join_multiplayer_room,
    set_multiplayer_ready,
    multiplayer_can_start,
    start_multiplayer_room,
    issue_multiplayer_question_ticket,
    submit_multiplayer_answer,
    multiplayer_play_payload,
    multiplayer_room_payload,
    kick_multiplayer_participant,
    join_public_multiplayer_room,
    set_multiplayer_access_type,
    leave_multiplayer_room,
    touch_multiplayer_presence,
    reconcile_multiplayer_presence,
    request_multiplayer_seat_swap,
    respond_multiplayer_seat_swap,
    cancel_multiplayer_seat_swap,
)


class WorldV503Tests(TestCase):
    def setUp(self):
        self.u1 = User.objects.create_user("world_a", password="x", first_name="Alpha")
        self.u2 = User.objects.create_user("world_b", password="x", first_name="Beta")
        self.u3 = User.objects.create_user("world_c", password="x", first_name="Gamma")
        self.test = Test.objects.create(name="WORLD-V503")
        for i in range(1, 7):
            Math_Question.objects.create(
                test=self.test, module="1", number=i, question=f"Math {i}",
                a="1", b="2", c="3", d="4", answer="A", written=False,
            )
            English_Question.objects.create(
                test=self.test, module="1", number=i, question=f"RW {i}",
                a="A1", b="B1", c="C1", d="D1", answer="A", response_type="multiple_choice",
            )

    def test_world_home_creates_both_ratings(self):
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Find match")
        self.assertEqual(WorldRating.objects.filter(user=self.u1).count(), 2)

    def test_world_shell_uses_student_workspace_sidebar(self):
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_home"))
        self.assertContains(response, 'data-student-workspace')
        self.assertContains(response, 'data-world-shell')
        self.assertContains(response, 'data-nav-key="world"')
        self.assertContains(response, 'mb50-world-link is-active')
        self.assertNotContains(response, 'class="mw503-topbar"')
        self.assertNotContains(response, 'class="mw503-dock"')

    def test_staff_account_is_redirected_out_of_world(self):
        teacher_group, _ = Group.objects.get_or_create(name="Teacher")
        self.u1.groups.add(teacher_group)
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_home"))
        self.assertRedirects(
            response,
            reverse("student_dashboard_root"),
            fetch_redirect_response=False,
        )

    def test_queue_pairs_two_different_students(self):
        first, _ = join_queue(self.u1, subject="math", mode="quick")
        self.assertEqual(first.status, WorldMatch.STATUS_WAITING)
        second, _ = join_queue(self.u2, subject="math", mode="quick")
        self.assertEqual(second.pk, first.pk)
        second.refresh_from_db()
        self.assertEqual(second.status, WorldMatch.STATUS_ACTIVE)
        self.assertEqual(second.player2, self.u2)
        self.assertEqual(len(second.question_ids), 5)

    def test_queue_never_matches_user_with_self(self):
        first, created = join_queue(self.u1, subject="math", mode="quick")
        again, created_again = join_queue(self.u1, subject="math", mode="quick")
        self.assertEqual(first.pk, again.pk)
        self.assertFalse(created_again)
        self.assertIsNone(again.player2)

    def test_quick_match_updates_record_but_not_rating(self):
        match, _ = join_queue(self.u1, subject="math", mode="quick")
        match, _ = join_queue(self.u2, subject="math", mode="quick")
        for i in range(5):
            submit_answer(match, self.u1, i, "A")
            submit_answer(match, self.u2, i, "B")
        match.refresh_from_db()
        r1 = WorldRating.objects.get(user=self.u1, subject="math")
        r2 = WorldRating.objects.get(user=self.u2, subject="math")
        self.assertEqual(match.status, WorldMatch.STATUS_COMPLETED)
        self.assertEqual(r1.rating, 1000)
        self.assertEqual(r2.rating, 1000)
        self.assertEqual(r1.wins, 1)
        self.assertEqual(r2.losses, 1)

    def test_ranked_match_changes_rating(self):
        match, _ = join_queue(self.u1, subject="rw", mode="ranked")
        match, _ = join_queue(self.u2, subject="rw", mode="ranked")
        for i in range(5):
            submit_answer(match, self.u1, i, "A")
            submit_answer(match, self.u2, i, "B")
        r1 = WorldRating.objects.get(user=self.u1, subject="rw")
        r2 = WorldRating.objects.get(user=self.u2, subject="rw")
        self.assertGreater(r1.rating, 1000)
        self.assertLess(r2.rating, 1000)
        self.assertEqual(r1.ranked_played, 1)
        self.assertEqual(r2.ranked_played, 1)

    def test_answer_cannot_be_submitted_twice(self):
        match, _ = join_queue(self.u1, subject="math", mode="quick")
        match, _ = join_queue(self.u2, subject="math", mode="quick")
        submit_answer(match, self.u1, 0, "A")
        with self.assertRaises(ValueError):
            submit_answer(match, self.u1, 0, "A")
        self.assertEqual(WorldAnswer.objects.filter(match=match, user=self.u1).count(), 1)

    def test_player_must_wait_for_opponent_before_advancing(self):
        match, _ = join_queue(self.u1, subject="math", mode="quick")
        match, _ = join_queue(self.u2, subject="math", mode="quick")
        submit_answer(match, self.u1, 0, "A")
        match.refresh_from_db()
        self.assertIsNone(next_question_index(match, self.u1))
        self.assertEqual(next_question_index(match, self.u2), 0)
        submit_answer(match, self.u2, 0, "A")
        match.refresh_from_db()
        self.assertEqual(next_question_index(match, self.u1), 1)
        self.assertEqual(next_question_index(match, self.u2), 1)


    def test_leaderboard_subjects_are_separate(self):
        ratings = ensure_ratings(self.u1)
        ratings["math"].rating = 1350
        ratings["math"].save(update_fields=["rating"])
        ratings["rw"].rating = 920
        ratings["rw"].save(update_fields=["rating"])
        self.client.force_login(self.u1)
        math = self.client.get(reverse("world_leaderboard"), {"subject": "math"})
        rw = self.client.get(reverse("world_leaderboard"), {"subject": "rw"})
        self.assertContains(math, "1350")
        self.assertContains(rw, "920")

    def test_sidebar_world_link_is_live_not_soon(self):
        self.client.force_login(self.u1)
        response = self.client.get(reverse("student_dashboard_root"))
        self.assertContains(response, reverse("world_home"))
        self.assertContains(response, "V50.3")


    def test_question_pool_is_curated_and_invalid_questions_are_disabled(self):
        broken = Math_Question.objects.create(
            test=self.test, module="1", number=99, question="Broken",
            a="1", b="2", c="", d="4", answer="A", written=False,
        )
        sync_question_pool(subject="math")
        good = GameQuestionPool.objects.filter(subject="math", game_enabled=True, quality_verified=True)
        self.assertGreaterEqual(good.count(), 5)
        broken_row = GameQuestionPool.objects.get(math_question=broken)
        self.assertFalse(broken_row.game_enabled)
        self.assertFalse(broken_row.quality_verified)

    def test_match_uses_curated_pool_and_opaque_question_token(self):
        match, _ = join_queue(self.u1, subject="math", mode="quick")
        match, _ = join_queue(self.u2, subject="math", mode="quick")
        self.assertEqual(len(match.question_pool_ids), 5)
        ticket = issue_question_ticket(match, self.u1, 0)
        self.assertGreater(len(ticket.token), 20)
        self.assertNotIn(ticket.token, {str(pk) for pk in match.question_ids})
        self.client.force_login(self.u1)
        # V50.3.8.1 client-gates the MATCH FOUND intro. The initial room
        # response intentionally contains no live question ticket; otherwise
        # a slow browser could burn question time behind the 3-2-1 animation.
        intro_page = self.client.get(reverse("world_match", args=[match.id]))
        self.assertContains(intro_page, "data-intro-required='1'")
        self.assertNotContains(intro_page, 'name="question_token"')

        # Once this client finishes its intro, the server may issue the opaque
        # ticket for question 1. This is the state the token test actually
        # needs to inspect.
        page = self.client.get(reverse("world_match", args=[match.id]), {"intro": "done"})
        self.assertContains(page, 'name="question_token"')
        self.assertNotContains(page, 'name="question_index"')

    def test_server_timer_turns_late_submission_into_timeout(self):
        match, _ = join_queue(self.u1, subject="math", mode="quick")
        match, _ = join_queue(self.u2, subject="math", mode="quick")
        ticket = issue_question_ticket(match, self.u1, 0)
        ticket.deadline_at = timezone.now() - timedelta(seconds=1)
        ticket.issued_at = timezone.now() - timedelta(seconds=80)
        ticket.save(update_fields=["deadline_at", "issued_at"])
        answer, _ = submit_answer_by_token(match, self.u1, ticket.token, "A")
        self.assertFalse(answer.is_correct)
        self.assertEqual(answer.points, 0)
        self.assertEqual(answer.integrity_flag, WorldAnswer.INTEGRITY_TIMEOUT)

    def test_suspiciously_fast_answer_gets_no_speed_bonus(self):
        match, _ = join_queue(self.u1, subject="math", mode="quick")
        match, _ = join_queue(self.u2, subject="math", mode="quick")
        ticket = issue_question_ticket(match, self.u1, 0)
        # Make the timing assertion deterministic even on slow Windows/SQLite
        # test runners. The test is about the <650 ms integrity branch, not
        # about how quickly the CI machine can execute ORM calls.
        now = timezone.now()
        ticket.issued_at = now + timedelta(seconds=1)
        ticket.deadline_at = now + timedelta(seconds=61)
        ticket.save(update_fields=["issued_at", "deadline_at"])
        answer, _ = submit_answer_by_token(match, self.u1, ticket.token, "A")
        pool = answer.pool_entry
        self.assertEqual(answer.integrity_flag, WorldAnswer.INTEGRITY_TOO_FAST)
        expected_base = {"easy": 80, "medium": 120, "hard": 180}[pool.difficulty]
        self.assertEqual(answer.points, expected_base)

    def test_ranked_queue_respects_rating_window_then_expands(self):
        r1 = ensure_ratings(self.u1)["math"]
        r3 = ensure_ratings(self.u3)["math"]
        r1.rating = 1000
        r3.rating = 1450
        r1.save(update_fields=["rating"])
        r3.save(update_fields=["rating"])
        waiting, _ = join_queue(self.u1, subject="math", mode="ranked")
        mine, _ = join_queue(self.u3, subject="math", mode="ranked")
        self.assertNotEqual(waiting.pk, mine.pk)
        mine.status = WorldMatch.STATUS_CANCELLED
        mine.save(update_fields=["status"])
        WorldMatch.objects.filter(pk=waiting.pk).update(created_at=timezone.now() - timedelta(seconds=50))
        matched, _ = join_queue(self.u3, subject="math", mode="ranked")
        self.assertEqual(matched.pk, waiting.pk)
        self.assertEqual(matched.status, WorldMatch.STATUS_ACTIVE)

    def test_repeat_ranked_pair_reduces_mmr_weight(self):
        WorldMatch.objects.create(
            subject="math", mode="ranked", status=WorldMatch.STATUS_COMPLETED,
            player1=self.u1, player2=self.u2, completed_at=timezone.now(),
        )
        first, _ = join_queue(self.u1, subject="math", mode="ranked")
        match, _ = join_queue(self.u2, subject="math", mode="ranked")
        self.assertEqual(first.pk, match.pk)
        self.assertLess(float(match.mmr_weight), 1.0)

    def test_disconnect_forfeit_finishes_match(self):
        match, _ = join_queue(self.u1, subject="math", mode="ranked")
        match, _ = join_queue(self.u2, subject="math", mode="ranked")
        old = timezone.now() - timedelta(seconds=90)
        WorldMatch.objects.filter(pk=match.pk).update(
            started_at=old,
            player1_last_seen_at=timezone.now(),
            player2_last_seen_at=old,
        )
        match.refresh_from_db()
        match = heartbeat(match, self.u1)
        self.assertEqual(match.status, WorldMatch.STATUS_COMPLETED)
        self.assertEqual(match.winner_id, self.u1.id)
        self.assertEqual(match.disconnect_forfeit_user_id, self.u2.id)

    def test_world_completion_awards_idempotent_xp(self):
        match, _ = join_queue(self.u1, subject="math", mode="quick")
        match, _ = join_queue(self.u2, subject="math", mode="quick")
        for i in range(5):
            submit_answer(match, self.u1, i, "A")
            submit_answer(match, self.u2, i, "B")
        self.assertEqual(XPEvent.objects.filter(user=self.u1, source_key=f"world-match:{match.pk}:{self.u1.pk}").count(), 1)
        self.assertEqual(XPEvent.objects.filter(user=self.u2, source_key=f"world-match:{match.pk}:{self.u2.pk}").count(), 1)

    def test_world_answer_endpoint_requires_opaque_token(self):
        match, _ = join_queue(self.u1, subject="math", mode="quick")
        match, _ = join_queue(self.u2, subject="math", mode="quick")
        self.client.force_login(self.u1)
        response = self.client.post(reverse("world_match_answer", args=[match.pk]), {"answer": "A"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Question token is required.")

    def test_waiting_queue_expires_after_hard_limit(self):
        waiting, _ = join_queue(self.u1, subject="math", mode="quick")
        WorldMatch.objects.filter(pk=waiting.pk).update(created_at=timezone.now() - timedelta(seconds=61))
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_queue_status", args=[waiting.pk]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["queue_timed_out"])
        self.assertEqual(payload["status"], WorldMatch.STATUS_CANCELLED)
        self.assertEqual(payload["queue_seconds_remaining"], 0)

    def test_stale_waiting_match_does_not_block_new_queue(self):
        waiting, _ = join_queue(self.u1, subject="math", mode="quick")
        WorldMatch.objects.filter(pk=waiting.pk).update(created_at=timezone.now() - timedelta(seconds=61))
        fresh, created = join_queue(self.u1, subject="math", mode="quick")
        self.assertTrue(created)
        self.assertNotEqual(fresh.pk, waiting.pk)
        waiting.refresh_from_db()
        self.assertEqual(waiting.status, WorldMatch.STATUS_CANCELLED)
        self.assertEqual(fresh.status, WorldMatch.STATUS_WAITING)

    def test_duplicate_waiting_rows_are_reconciled_for_queue_status(self):
        first, _ = join_queue(self.u1, subject="math", mode="quick")
        second = WorldMatch.objects.create(
            subject="math",
            mode="quick",
            status=WorldMatch.STATUS_WAITING,
            player1=self.u2,
        )
        self.client.force_login(self.u2)
        response = self.client.get(reverse("world_queue_status", args=[second.pk]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], WorldMatch.STATUS_ACTIVE)
        merged = WorldMatch.objects.filter(status=WorldMatch.STATUS_ACTIVE).get()
        self.assertIn(merged.player1_id, {self.u1.id, self.u2.id})
        self.assertIn(merged.player2_id, {self.u1.id, self.u2.id})
        second.refresh_from_db()
        self.assertEqual(second.status, WorldMatch.STATUS_CANCELLED)

    def test_rating_tier_ladder_uses_new_world_labels(self):
        rating = ensure_ratings(self.u1)["math"]
        checkpoints = [
            (1000, "Bronze"),
            (1150, "Silver"),
            (1300, "Gold"),
            (1450, "Diamond"),
            (1600, "Mythical"),
            (1750, "Legendary"),
            (1900, "Master"),
            (2050, "Pro"),
        ]
        for value, expected in checkpoints:
            rating.rating = value
            self.assertEqual(rating.tier, expected)

    def test_leaderboard_search_api_filters_automatically(self):
        ensure_ratings(self.u1)
        ensure_ratings(self.u2)
        self.u2.first_name = "BetaSearch"
        self.u2.save(update_fields=["first_name"])
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_leaderboard_search"), {"subject": "math", "q": "BetaSearch"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["rows"]), 1)
        self.assertEqual(payload["rows"][0]["username"], self.u2.username)
        self.assertIn("rank", payload["rows"][0])
        self.assertIn("profile_url", payload["rows"][0])

    def test_world_profile_page_is_accessible_for_other_student(self):
        ensure_ratings(self.u1)
        ensure_ratings(self.u2)
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_profile", args=[self.u2.username]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.u2.username)
        self.assertContains(response, "PLAYER PROFILE")

    def test_world_home_embeds_both_subject_rating_snapshots_for_live_switch(self):
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_home"))
        self.assertContains(response, 'data-world-player-card')
        self.assertContains(response, 'data-world-rating-source')
        self.assertContains(response, 'data-subject="math"')
        self.assertContains(response, 'data-subject="rw"')
        self.assertContains(response, str(WorldRating.objects.get(user=self.u1, subject="math").rating))
        self.assertContains(response, str(WorldRating.objects.get(user=self.u1, subject="rw").rating))

    def test_world_js_switches_player_rating_card_with_subject(self):
        js = (settings.BASE_DIR / "static" / "assets" / "js" / "world-v503.js").read_text(encoding="utf-8")
        self.assertIn("syncWorldPlayerRating", js)
        self.assertIn('input[name="subject"]', js)
        self.assertIn('data-world-rating-source', js)

    def test_world_mode_switch_is_in_page_and_swipeable(self):
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_home"))
        self.assertContains(response, 'data-world-mode-switch')
        self.assertContains(response, 'data-world-mode="duel"')
        self.assertContains(response, 'data-world-mode="multiplayer"')
        self.assertContains(response, 'data-world-mode-panel="multiplayer"')
        js = (settings.BASE_DIR / "static" / "assets" / "js" / "world-multiplayer-v504.js").read_text(encoding="utf-8")
        self.assertIn("history.replaceState", js)
        self.assertIn("pointerup", js)

    def test_world_ui_has_live_search_countup_and_no_future_mode_clutter(self):
        self.client.force_login(self.u1)
        home = self.client.get(reverse("world_home"))
        ranks = self.client.get(reverse("world_leaderboard"))
        self.assertContains(home, 'data-queue-limit="60"')
        self.assertContains(home, 'data-world-count-to="1000"')
        self.assertContains(home, 'mw503-lobby-hero')
        self.assertNotContains(home, 'mw503-compact-links')
        self.assertNotContains(home, 'mw503-rating-switch')
        self.assertNotContains(home, ">Cups<")
        self.assertNotContains(home, ">Friends<")
        self.assertContains(ranks, 'data-world-rank-search')
        self.assertContains(ranks, reverse("world_leaderboard_search"))

    def test_world_match_hides_play_and_leaderboard_tabs(self):
        match, _ = join_queue(self.u1, subject="math", mode="quick")
        match, _ = join_queue(self.u2, subject="math", mode="quick")
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_match", args=[match.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'aria-label="World navigation"')
        self.assertNotContains(response, '>Leaderboard<', html=False)
        self.assertContains(response, 'mw503-worldbar is-compact')

    def test_world_match_uses_name_score_vs_score_name_and_katex(self):
        match, _ = join_queue(self.u1, subject="math", mode="quick")
        match, _ = join_queue(self.u2, subject="math", mode="quick")
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_match", args=[match.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'mw503-scoreboard-player is-me')
        self.assertContains(response, 'mw503-scoreboard-player is-opponent')
        self.assertContains(response, 'data-world-my-score')
        self.assertContains(response, 'data-world-opponent-score')
        self.assertContains(response, 'katex@0.16.10')

    def test_world_radar_js_moves_primary_contact_to_random_points(self):
        js_path = settings.BASE_DIR / 'static' / 'assets' / 'js' / 'world-v503.js'
        js = js_path.read_text(encoding='utf-8')
        self.assertIn("const movingDot=qs('b',radar)", js)
        self.assertIn('blinkAtRandomPoint(movingDot,{primary:true})', js)
        self.assertIn("node.style.animation='none'", js)
        self.assertIn('void node.offsetWidth', js)
        self.assertIn('mwRadarContactBlink', js)
        self.assertIn('renderWorldMath(document)', js)

    def test_world_match_intro_poll_cannot_restart_countdown(self):
        js_path = settings.BASE_DIR / 'static' / 'assets' / 'js' / 'world-v503.js'
        js = js_path.read_text(encoding='utf-8')
        self.assertIn("const introRequired=!!introNode&&introNode.dataset.introRequired==='1'", js)
        self.assertIn("else if(!introRequired&&qs('.mw503-duel-stage',room))", js)
        self.assertIn("if(!introRequired&&qs('.mw503-wait-room',room)", js)

    def test_world_result_page_does_not_heartbeat_reload_forever(self):
        js_path = settings.BASE_DIR / 'static' / 'assets' / 'js' / 'world-v503.js'
        js = js_path.read_text(encoding='utf-8')
        self.assertIn("const resultView=!!qs('.mw503-result-card',room)", js)
        self.assertIn('if(!heartbeatUrl||resultView)return;', js)
        self.assertIn('if(heartbeatUrl&&!resultView)', js)

    def test_world_katex_does_not_use_single_dollar_currency_delimiter(self):
        js_path = settings.BASE_DIR / 'static' / 'assets' / 'js' / 'world-v503.js'
        js = js_path.read_text(encoding='utf-8')
        self.assertIn("{left:'\\\\(',right:'\\\\)',display:false}", js)
        self.assertIn("{left:'$$',right:'$$',display:true}", js)
        self.assertNotIn("{left:'$',right:'$',display:false}", js)

    def test_world_match_intro_is_required_before_first_question(self):
        match, _ = join_queue(self.u1, subject="math", mode="quick")
        match, _ = join_queue(self.u2, subject="math", mode="quick")
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_match", args=[match.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-intro-required='1'")
        self.assertContains(response, 'MATCH FOUND')
        self.assertContains(response, 'data-world-intro-count')

    def test_world_match_intro_is_client_gated_not_wall_clock_gated(self):
        match, _ = join_queue(self.u1, subject="math", mode="quick")
        match, _ = join_queue(self.u2, subject="math", mode="quick")
        WorldMatch.objects.filter(pk=match.pk).update(started_at=timezone.now() - timedelta(seconds=30))
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_match", args=[match.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-intro-required='1'")
        self.assertNotContains(response, 'data-world-question-card')
        response = self.client.get(reverse("world_match", args=[match.pk]) + '?intro=done')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-intro-required='0'")
        self.assertContains(response, 'data-world-question-card')


    def test_world_js_uses_xhr_for_mutating_requests_and_recovers_waiting_player(self):
        js_path = settings.BASE_DIR / 'static' / 'assets' / 'js' / 'world-v503.js'
        js = js_path.read_text(encoding='utf-8')
        self.assertIn('function xhrJson(url,opts={})', js)
        self.assertIn("if(method!=='GET'&&method!=='HEAD')return xhrJson(url,opts)", js)
        self.assertIn("awaitingNextQuestion=!!qs('[data-world-between-questions]',room)", js)
        self.assertIn("(awaitingNextQuestion||!hasQuestionCard)", js)

    def test_equal_completed_scores_are_a_draw(self):
        match, _ = join_queue(self.u1, subject="math", mode="quick")
        match, _ = join_queue(self.u2, subject="math", mode="quick")
        match.player1_score = 1
        match.player2_score = 1
        match.save(update_fields=["player1_score", "player2_score"])
        _finalize_locked(match)
        match.refresh_from_db()
        self.assertIsNone(match.winner_id)
        r1 = WorldRating.objects.get(user=self.u1, subject="math")
        r2 = WorldRating.objects.get(user=self.u2, subject="math")
        self.assertEqual(r1.draws, 1)
        self.assertEqual(r2.draws, 1)
    def test_queue_status_recovers_canonical_active_room_from_stale_waiting_row(self):
        active, _ = join_queue(self.u1, subject="math", mode="quick")
        active, _ = join_queue(self.u2, subject="math", mode="quick")
        stale = WorldMatch.objects.create(subject="math", mode="quick", player1=self.u1, status=WorldMatch.STATUS_WAITING)
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_queue_status", args=[stale.pk]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], WorldMatch.STATUS_ACTIVE)
        self.assertEqual(payload["room_url"], reverse("world_match", args=[active.pk]))

    def test_world_heartbeat_js_uses_real_csrf_form_body(self):
        js_path = settings.BASE_DIR / "static" / "assets" / "js" / "world-v503.js"
        js = js_path.read_text(encoding="utf-8")
        self.assertIn("dataset?.csrfCookieName", js)
        self.assertIn("cookieValue(cookieName)", js)
        self.assertIn("body.append('csrfmiddlewaretoken',token)", js)
        self.assertIn("setInterval(pollQueueStatus,250)", js)
        self.assertIn("cache:'no-store'", js)
        self.assertIn("queuePollNow=pollQueueStatus", js)

    def test_completed_match_can_send_rematch_notification_and_accept(self):
        source, _ = join_queue(self.u1, subject="math", mode="quick")
        source, _ = join_queue(self.u2, subject="math", mode="quick")
        source.status = WorldMatch.STATUS_COMPLETED
        source.completed_at = timezone.now()
        source.save(update_fields=["status", "completed_at"])

        self.client.force_login(self.u1)
        response = self.client.post(reverse("world_rematch_request", args=[source.pk]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        invite = WorldMatch.objects.get(pk=payload["invite_id"])
        self.assertEqual(invite.invitee_id, self.u2.id)
        self.assertEqual(invite.rematch_of_id, source.id)
        notice = MakonNotification.objects.filter(user=self.u2, title__icontains="Rematch challenge").latest("id")
        self.assertEqual(notice.url, reverse("world_rematch_offer", args=[invite.pk]))

        self.client.force_login(self.u2)
        accepted = self.client.post(reverse("world_rematch_accept", args=[invite.pk]))
        self.assertEqual(accepted.status_code, 200)
        invite.refresh_from_db()
        self.assertEqual(invite.status, WorldMatch.STATUS_ACTIVE)
        self.assertEqual(invite.player2_id, self.u2.id)

    def test_private_rematch_invite_is_not_public_matchmaking_candidate(self):
        source, _ = join_queue(self.u1, subject="math", mode="quick")
        source, _ = join_queue(self.u2, subject="math", mode="quick")
        source.status = WorldMatch.STATUS_COMPLETED
        source.completed_at = timezone.now()
        source.save(update_fields=["status", "completed_at"])
        self.client.force_login(self.u1)
        payload = self.client.post(reverse("world_rematch_request", args=[source.pk])).json()
        invite = WorldMatch.objects.get(pk=payload["invite_id"])
        public, _ = join_queue(self.u3, subject="math", mode="quick")
        self.assertNotEqual(public.pk, invite.pk)
        self.assertIsNone(invite.player2_id)

    def test_queue_status_is_never_cached_for_cross_browser_matchmaking(self):
        waiting, _ = join_queue(self.u1, subject="math", mode="quick")
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_queue_status", args=[waiting.pk]))
        self.assertEqual(response.status_code, 200)
        cache_control = response.headers.get("Cache-Control", "")
        self.assertIn("no-cache", cache_control)
        self.assertIn("no-store", cache_control)

    def test_world_shell_exposes_configured_csrf_cookie_name(self):
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-csrf-cookie-name="{settings.CSRF_COOKIE_NAME}"')

    def test_rematch_result_renders_real_csrf_token_and_polished_actions(self):
        source, _ = join_queue(self.u1, subject="math", mode="quick")
        source, _ = join_queue(self.u2, subject="math", mode="quick")
        source.status = WorldMatch.STATUS_COMPLETED
        source.completed_at = timezone.now()
        source.save(update_fields=["status", "completed_at"])

        secure_client = Client(enforce_csrf_checks=True)
        secure_client.force_login(self.u1)
        page = secure_client.get(reverse("world_match", args=[source.pk]))
        self.assertEqual(page.status_code, 200)
        csrf_cookie_name = settings.CSRF_COOKIE_NAME
        self.assertIn(csrf_cookie_name, secure_client.cookies)
        self.assertContains(page, "data-world-rematch-form")
        self.assertContains(page, "mw503-result-action-secondary")
        self.assertContains(page, "New opponent")

        token = secure_client.cookies[csrf_cookie_name].value
        response = secure_client.post(
            reverse("world_rematch_request", args=[source.pk]),
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])


    def test_rematch_incoming_api_exposes_live_chess_style_challenge(self):
        source, _ = join_queue(self.u1, subject="math", mode="quick")
        source, _ = join_queue(self.u2, subject="math", mode="quick")
        source.status = WorldMatch.STATUS_COMPLETED
        source.completed_at = timezone.now()
        source.save(update_fields=["status", "completed_at"])

        self.client.force_login(self.u1)
        request_payload = self.client.post(reverse("world_rematch_request", args=[source.pk])).json()
        invite = WorldMatch.objects.get(pk=request_payload["invite_id"])

        self.client.force_login(self.u2)
        incoming = self.client.get(reverse("world_rematch_incoming"))
        self.assertEqual(incoming.status_code, 200)
        payload = incoming.json()["invite"]
        self.assertEqual(payload["id"], str(invite.id))
        self.assertEqual(payload["username"], self.u1.username)
        self.assertEqual(payload["accept_url"], reverse("world_rematch_accept", args=[invite.pk]))
        self.assertEqual(payload["decline_url"], reverse("world_rematch_decline", args=[invite.pk]))
        self.assertGreater(payload["seconds_remaining"], 0)

    def test_rematch_sender_can_cancel_pending_request(self):
        source, _ = join_queue(self.u1, subject="math", mode="quick")
        source, _ = join_queue(self.u2, subject="math", mode="quick")
        source.status = WorldMatch.STATUS_COMPLETED
        source.completed_at = timezone.now()
        source.save(update_fields=["status", "completed_at"])

        self.client.force_login(self.u1)
        payload = self.client.post(reverse("world_rematch_request", args=[source.pk])).json()
        invite = WorldMatch.objects.get(pk=payload["invite_id"])
        cancelled = self.client.post(reverse("world_rematch_cancel", args=[invite.pk]))
        self.assertEqual(cancelled.status_code, 200)
        invite.refresh_from_db()
        self.assertEqual(invite.status, WorldMatch.STATUS_CANCELLED)

        self.client.force_login(self.u2)
        self.assertIsNone(self.client.get(reverse("world_rematch_incoming")).json()["invite"])

    def test_reciprocal_rematch_requests_start_same_room_immediately(self):
        source, _ = join_queue(self.u1, subject="math", mode="quick")
        source, _ = join_queue(self.u2, subject="math", mode="quick")
        source.status = WorldMatch.STATUS_COMPLETED
        source.completed_at = timezone.now()
        source.save(update_fields=["status", "completed_at"])

        self.client.force_login(self.u1)
        first = self.client.post(reverse("world_rematch_request", args=[source.pk])).json()
        invite = WorldMatch.objects.get(pk=first["invite_id"])
        self.assertEqual(invite.status, WorldMatch.STATUS_WAITING)

        self.client.force_login(self.u2)
        second = self.client.post(reverse("world_rematch_request", args=[source.pk]))
        self.assertEqual(second.status_code, 200)
        payload = second.json()
        self.assertTrue(payload["activated"])
        self.assertEqual(payload["invite_id"], str(invite.id))
        invite.refresh_from_db()
        self.assertEqual(invite.status, WorldMatch.STATUS_ACTIVE)
        self.assertEqual(invite.player2_id, self.u2.id)
    def test_world_match_recovers_from_transient_question_ticket_race(self):
        match, _ = join_queue(self.u1, subject="math", mode="quick")
        match, _ = join_queue(self.u2, subject="math", mode="quick")
        self.client.force_login(self.u1)

        real_issue = issue_question_ticket
        calls = {"count": 0}

        def flaky_issue(current_match, user, question_index):
            calls["count"] += 1
            if calls["count"] == 1:
                raise ValueError("Question is no longer current.")
            return real_issue(current_match, user, question_index)

        with patch("apps.world.views.issue_question_ticket", side_effect=flaky_issue):
            page = self.client.get(reverse("world_match", args=[match.pk]) + "?intro=done")

        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'name="question_token"')
        self.assertGreaterEqual(calls["count"], 2)

    def test_world_match_never_500s_when_question_state_keeps_moving(self):
        match, _ = join_queue(self.u1, subject="math", mode="quick")
        match, _ = join_queue(self.u2, subject="math", mode="quick")
        self.client.force_login(self.u1)

        with patch(
            "apps.world.views.issue_question_ticket",
            side_effect=ValueError("Question is no longer current."),
        ):
            page = self.client.get(reverse("world_match", args=[match.pk]) + "?intro=done")

        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "Question is no longer current.")
        self.assertContains(page, "Preparing next step")


    def test_multiplayer_room_creates_host_seat_and_unique_code(self):
        room = create_multiplayer_room(self.u1, subject="math", capacity=4)
        self.assertEqual(room.status, WorldMultiplayerRoom.STATUS_LOBBY)
        self.assertEqual(room.capacity, 4)
        self.assertEqual(len(room.join_code), 6)
        seat = WorldMultiplayerSeat.objects.get(room=room, user=self.u1)
        self.assertEqual(seat.seat_number, 1)
        self.assertFalse(seat.is_ready)

    def test_multiplayer_join_fills_lowest_open_seat_and_blocks_overflow(self):
        u4 = User.objects.create_user("world_d", password="x", first_name="Delta")
        room = create_multiplayer_room(self.u1, subject="math", capacity=3)
        _, seat2, _ = join_multiplayer_room(self.u2, join_code=room.join_code.lower())
        _, seat3, _ = join_multiplayer_room(self.u3, join_code=room.join_code)
        self.assertEqual((seat2.seat_number, seat3.seat_number), (2, 3))
        with self.assertRaisesMessage(ValueError, "Room is full"):
            join_multiplayer_room(u4, join_code=room.join_code)

    def test_multiplayer_requires_three_players_and_everyone_ready(self):
        room = create_multiplayer_room(self.u1, subject="math", capacity=4)
        join_multiplayer_room(self.u2, join_code=room.join_code)
        self.assertFalse(multiplayer_can_start(room))
        set_multiplayer_ready(room, self.u1, True)
        set_multiplayer_ready(room, self.u2, True)
        self.assertFalse(multiplayer_can_start(room))
        join_multiplayer_room(self.u3, join_code=room.join_code)
        set_multiplayer_ready(room, self.u3, True)
        self.assertTrue(multiplayer_can_start(room))

    def test_multiplayer_start_is_host_only_and_pins_shared_questions(self):
        room = create_multiplayer_room(self.u1, subject="math", capacity=3)
        join_multiplayer_room(self.u2, join_code=room.join_code)
        join_multiplayer_room(self.u3, join_code=room.join_code)
        for user in (self.u1, self.u2, self.u3):
            set_multiplayer_ready(room, user, True)
        with self.assertRaisesMessage(ValueError, "Only the host"):
            start_multiplayer_room(room, self.u2)
        active = start_multiplayer_room(room, self.u1)
        self.assertEqual(active.status, WorldMultiplayerRoom.STATUS_ACTIVE)
        self.assertEqual(len(active.question_pool_ids), 5)
        self.assertIsNotNone(active.started_at)

    def test_multiplayer_api_create_join_ready_and_status(self):
        self.client.force_login(self.u1)
        created = self.client.post(reverse("world_multiplayer_create"), {"subject": "math", "capacity": "4"})
        self.assertEqual(created.status_code, 200)
        room = WorldMultiplayerRoom.objects.get(pk=created.json()["room_id"])
        self.client.force_login(self.u2)
        joined = self.client.post(reverse("world_multiplayer_join"), {"join_code": room.join_code})
        self.assertEqual(joined.status_code, 200)
        ready = self.client.post(reverse("world_multiplayer_ready", args=[room.pk]), {"ready": "1"})
        self.assertEqual(ready.status_code, 200)
        self.assertTrue(ready.json()["my_ready"])
        status = self.client.get(reverse("world_multiplayer_status", args=[room.pk]))
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["occupied"], 2)

    def test_multiplayer_room_is_private_to_seated_players(self):
        room = create_multiplayer_room(self.u1, subject="math", capacity=4)
        self.client.force_login(self.u3)
        response = self.client.get(reverse("world_multiplayer_room", args=[room.pk]))
        self.assertEqual(response.status_code, 404)

    def test_world_navigation_exposes_live_multiplayer_entry(self):
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("world_multiplayer_home"))
        self.assertContains(response, "Multiplayer")

    def test_multiplayer_room_template_has_ready_start_and_live_status_hooks(self):
        room = create_multiplayer_room(self.u1, subject="rw", capacity=4)
        join_multiplayer_room(self.u2, join_code=room.join_code)
        join_multiplayer_room(self.u3, join_code=room.join_code)
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_multiplayer_room", args=[room.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-mp-room")
        self.assertContains(response, "data-mp-ready")
        self.assertContains(response, "data-mp-start")
        self.assertContains(response, room.join_code)

    def _started_multiplayer_room(self, capacity=3):
        room = create_multiplayer_room(self.u1, subject="math", capacity=capacity)
        join_multiplayer_room(self.u2, join_code=room.join_code)
        join_multiplayer_room(self.u3, join_code=room.join_code)
        if capacity == 4:
            u4 = User.objects.create_user("world_d2", password="x", first_name="Delta")
            join_multiplayer_room(u4, join_code=room.join_code)
            users = (self.u1, self.u2, self.u3, u4)
        else:
            users = (self.u1, self.u2, self.u3)
        for user in users:
            set_multiplayer_ready(room, user, True)
        room = start_multiplayer_room(room, self.u1)
        # Helper represents an already-live first round. V50.4.18 itself adds a
        # short shared launch countdown before Q1 so real browsers do not lose
        # question time while leaving the lobby.
        room.question_started_at = timezone.now() - timedelta(seconds=1)
        room.save(update_fields=["question_started_at"])
        return room, users

    def test_world_home_exposes_duel_and_multiplayer_game_type_selector(self):
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_home"))
        # V50.4.4 replaced the old two-card game type switch with an
        # in-page swipe/pill control. Keep this regression aligned with
        # the current UX instead of requiring removed markup/copy.
        self.assertContains(response, "mw504-swipe-toggle")
        self.assertContains(response, 'data-world-mode="duel"')
        self.assertContains(response, 'data-world-mode="multiplayer"')
        self.assertContains(response, ">1v1<")
        self.assertContains(response, ">Multiplayer<")


    def test_multiplayer_create_supports_private_and_public_room_types(self):
        private = create_multiplayer_room(self.u1, subject="math", capacity=4, access_type=WorldMultiplayerRoom.ACCESS_PRIVATE)
        public = create_multiplayer_room(self.u2, subject="rw", capacity=3, access_type=WorldMultiplayerRoom.ACCESS_PUBLIC)
        self.assertEqual(private.access_type, WorldMultiplayerRoom.ACCESS_PRIVATE)
        self.assertEqual(public.access_type, WorldMultiplayerRoom.ACCESS_PUBLIC)

    def test_multiplayer_host_can_switch_private_room_to_public(self):
        room = create_multiplayer_room(
            self.u1,
            subject="math",
            capacity=4,
            question_count=10,
            access_type=WorldMultiplayerRoom.ACCESS_PRIVATE,
        )
        updated = set_multiplayer_access_type(room, self.u1, WorldMultiplayerRoom.ACCESS_PUBLIC)
        self.assertEqual(updated.access_type, WorldMultiplayerRoom.ACCESS_PUBLIC)
        joined_room, _seat, created = join_public_multiplayer_room(
            self.u2, subject="math", capacity=4, question_count=10
        )
        self.assertFalse(created)
        self.assertEqual(joined_room.pk, room.pk)

    def test_multiplayer_access_switch_is_host_only_and_lobby_only(self):
        room = create_multiplayer_room(self.u1, subject="math", capacity=3)
        join_multiplayer_room(self.u2, join_code=room.join_code)
        join_multiplayer_room(self.u3, join_code=room.join_code)
        with self.assertRaisesMessage(ValueError, "Only the host"):
            set_multiplayer_access_type(room, self.u2, WorldMultiplayerRoom.ACCESS_PUBLIC)
        for user in (self.u1, self.u2, self.u3):
            set_multiplayer_ready(room, user, True)
        room = start_multiplayer_room(room, self.u1)
        with self.assertRaisesMessage(ValueError, "before the battle starts"):
            set_multiplayer_access_type(room, self.u1, WorldMultiplayerRoom.ACCESS_PUBLIC)

    def test_multiplayer_access_api_and_room_ui_toggle_without_reload(self):
        room = create_multiplayer_room(self.u1, subject="rw", capacity=4)
        self.client.force_login(self.u1)
        page = self.client.get(reverse("world_multiplayer_room", args=[room.pk]))
        self.assertContains(page, "data-mp-access-toggle")
        self.assertContains(page, "data-access-url")
        response = self.client.post(
            reverse("world_multiplayer_access", args=[room.pk]),
            {"access_type": "public"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_public"])
        room.refresh_from_db()
        self.assertEqual(room.access_type, WorldMultiplayerRoom.ACCESS_PUBLIC)
        js = (settings.BASE_DIR / "static" / "assets" / "js" / "world-multiplayer-v504.js").read_text(encoding="utf-8")
        self.assertIn("data-mp-access-toggle", js)
        self.assertIn("room.dataset.accessUrl", js)

    def test_multiplayer_access_switch_has_native_form_fallback(self):
        room = create_multiplayer_room(self.u1, subject="math", capacity=4)
        self.client.force_login(self.u1)
        page = self.client.get(reverse("world_multiplayer_room", args=[room.pk]))
        self.assertContains(page, "data-mp-access-form")
        response = self.client.post(
            reverse("world_multiplayer_access", args=[room.pk]),
            {"access_type": "public"},
            HTTP_ACCEPT="text/html,application/xhtml+xml",
        )
        self.assertRedirects(
            response,
            reverse("world_multiplayer_room", args=[room.pk]),
            fetch_redirect_response=False,
        )
        room.refresh_from_db()
        self.assertEqual(room.access_type, WorldMultiplayerRoom.ACCESS_PUBLIC)

    def test_multiplayer_access_switch_is_optimistic_and_pauses_stale_polling(self):
        js = (settings.BASE_DIR / "static" / "assets" / "js" / "world-multiplayer-v504.js").read_text(encoding="utf-8")
        self.assertIn("let accessPending=false", js)
        self.assertIn("applyAccessVisual(target)", js)
        # V50.4.18 also prevents overlapping status requests; the previous
        # exact-string assertion expected the obsolete two-condition guard.
        self.assertIn("if(navigating||accessPending||pollBusy)", js)
        self.assertIn("if(!accessPending)applyAccessVisual(p.access_type)", js)
        self.assertIn("data-mp-access-form", js)

    def test_multiplayer_leave_uses_keepalive_and_immediate_navigation(self):
        room = create_multiplayer_room(self.u1, subject="math", capacity=4)
        self.client.force_login(self.u1)
        page = self.client.get(reverse("world_multiplayer_room", args=[room.pk]))
        self.assertContains(page, "data-mp-leave-form")
        self.assertContains(page, "data-leave-redirect-url")
        js = (settings.BASE_DIR / "static" / "assets" / "js" / "world-multiplayer-v504.js").read_text(encoding="utf-8")
        self.assertIn("keepalive:true", js)
        self.assertIn("postKeepalive(room.dataset.leaveUrl)", js)
        self.assertIn("window.location.replace(room.dataset.leaveRedirectUrl", js)

    def test_multiplayer_home_hides_room_during_optimistic_leave_redirect(self):
        room = create_multiplayer_room(self.u1, subject="math", capacity=4)
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_multiplayer_home") + f"?leaving={room.id}")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "ACTIVE PRIVATE ROOM")


    def test_public_multiplayer_room_uses_same_invite_card_design_as_private(self):
        room = create_multiplayer_room(
            self.u1,
            subject="rw",
            capacity=3,
            question_count=5,
            access_type=WorldMultiplayerRoom.ACCESS_PUBLIC,
        )
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_multiplayer_room", args=[room.pk]))
        self.assertContains(response, "mw504-invite-panel mw504-public-invite-panel")
        self.assertContains(response, "Open multiplayer lobby")
        self.assertContains(response, "Copy link")
        self.assertContains(response, "Invite friends")
        self.assertContains(response, "Make private")
        self.assertNotContains(response, "mw504-room-banner-public")

    def test_public_multiplayer_join_matches_existing_room_or_creates_one(self):
        room = create_multiplayer_room(
            self.u1,
            subject="math",
            capacity=4,
            question_count=10,
            access_type=WorldMultiplayerRoom.ACCESS_PUBLIC,
        )
        joined_room, _seat, created = join_public_multiplayer_room(self.u2, subject="math", capacity=4, question_count=10)
        self.assertFalse(created)
        self.assertEqual(joined_room.pk, room.pk)
        fresh_room, _fresh_seat, created_room = join_public_multiplayer_room(self.u3, subject="rw", capacity=3, question_count=5)
        self.assertTrue(created_room)
        self.assertEqual(fresh_room.access_type, WorldMultiplayerRoom.ACCESS_PUBLIC)

    def test_world_home_multiplayer_panel_exposes_public_and_private_entry_points(self):
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_home"))
        self.assertContains(response, "Join public room")
        self.assertContains(response, "Join private room")
        self.assertContains(response, "Private")
        self.assertContains(response, "Public")

    def test_multiplayer_start_initializes_shared_question_clock(self):
        room, _users = self._started_multiplayer_room()
        room.refresh_from_db()
        self.assertEqual(room.current_question_index, 0)
        self.assertIsNotNone(room.question_started_at)
        self.assertEqual(len(room.question_pool_ids), 5)

    def test_multiplayer_every_player_gets_same_current_question(self):
        room, users = self._started_multiplayer_room()
        tickets = [issue_multiplayer_question_ticket(room, user) for user in users]
        self.assertTrue(all(ticket.question_index == 0 for ticket in tickets))
        self.assertEqual(len({ticket.deadline_at for ticket in tickets}), 1)

    def test_multiplayer_barrier_advances_only_after_everyone_answers(self):
        room, users = self._started_multiplayer_room()
        t1 = issue_multiplayer_question_ticket(room, users[0])
        t2 = issue_multiplayer_question_ticket(room, users[1])
        t3 = issue_multiplayer_question_ticket(room, users[2])
        submit_multiplayer_answer(room, users[0], t1.token, "A")
        room.refresh_from_db()
        self.assertEqual(room.current_question_index, 0)
        submit_multiplayer_answer(room, users[1], t2.token, "A")
        room.refresh_from_db()
        self.assertEqual(room.current_question_index, 0)
        submit_multiplayer_answer(room, users[2], t3.token, "A")
        room.refresh_from_db()
        self.assertEqual(room.current_question_index, 1)

    def test_multiplayer_answer_token_cannot_be_reused(self):
        room, users = self._started_multiplayer_room()
        ticket = issue_multiplayer_question_ticket(room, users[0])
        submit_multiplayer_answer(room, users[0], ticket.token, "A")
        with self.assertRaises(ValueError):
            submit_multiplayer_answer(room, users[0], ticket.token, "A")
        self.assertEqual(WorldMultiplayerAnswer.objects.filter(room=room, user=users[0], question_index=0).count(), 1)

    def test_multiplayer_play_page_and_answer_api_are_live(self):
        room, _users = self._started_multiplayer_room()
        self.client.force_login(self.u1)
        page = self.client.get(reverse("world_multiplayer_play", args=[room.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "data-mp-play")
        self.assertContains(page, 'name="question_token"')
        ticket = WorldMultiplayerQuestionTicket.objects.get(room=room, user=self.u1, question_index=0)
        answer = self.client.post(reverse("world_multiplayer_answer", args=[room.pk]), {"question_token": ticket.token, "answer": "A"})
        self.assertEqual(answer.status_code, 200)
        self.assertTrue(answer.json()["ok"])
        self.assertIn("play_url", answer.json())
    def test_multiplayer_progress_fields_do_not_leak_into_duel_model(self):
        with self.assertRaises(FieldDoesNotExist):
            WorldMatch._meta.get_field("current_question_index")
        with self.assertRaises(FieldDoesNotExist):
            WorldMatch._meta.get_field("question_started_at")
        self.assertEqual(WorldMultiplayerRoom._meta.get_field("current_question_index").name, "current_question_index")
        self.assertEqual(WorldMultiplayerRoom._meta.get_field("question_started_at").name, "question_started_at")



    def test_multiplayer_host_can_choose_question_count(self):
        for count in (5, 10, 15, 20):
            user = User.objects.create_user(f"qcount_{count}", password="x")
            room = create_multiplayer_room(user, subject="math", capacity=4, question_count=count)
            self.assertEqual(room.question_count, count)
        with self.assertRaisesMessage(ValueError, "Question count must be 5, 10, 15, or 20"):
            create_multiplayer_room(User.objects.create_user("bad_count", password="x"), subject="math", capacity=4, question_count=7)

    def test_multiplayer_invite_link_joins_player_directly(self):
        room = create_multiplayer_room(self.u1, subject="math", capacity=4, question_count=10)
        self.client.force_login(self.u2)
        response = self.client.get(reverse("world_multiplayer_invite", args=[room.join_code]))
        self.assertRedirects(response, reverse("world_multiplayer_room", args=[room.id]), fetch_redirect_response=False)
        self.assertTrue(WorldMultiplayerSeat.objects.filter(room=room, user=self.u2).exists())

    def test_multiplayer_host_can_kick_participant_before_start(self):
        room = create_multiplayer_room(self.u1, subject="math", capacity=4)
        join_multiplayer_room(self.u2, join_code=room.join_code)
        self.assertTrue(kick_multiplayer_participant(room, self.u1, self.u2.id))
        self.assertFalse(WorldMultiplayerSeat.objects.filter(room=room, user=self.u2).exists())
        with self.assertRaisesMessage(ValueError, "Only the host"):
            kick_multiplayer_participant(room, self.u2, self.u1.id)

    def test_kicked_multiplayer_player_status_redirects_home_with_notice(self):
        room = create_multiplayer_room(self.u1, subject="math", capacity=4)
        join_multiplayer_room(self.u2, join_code=room.join_code)
        kick_multiplayer_participant(room, self.u1, self.u2.id)
        self.client.force_login(self.u2)
        response = self.client.get(reverse("world_multiplayer_status", args=[room.id]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["removed"])
        self.assertEqual(payload["reason"], "kicked")
        self.assertIn("notice=kicked", payload["redirect_url"])

    def test_multiplayer_home_shows_kicked_notice_dialog(self):
        self.client.force_login(self.u2)
        response = self.client.get(reverse("world_multiplayer_home") + "?notice=kicked")
        self.assertContains(response, "data-mp-kicked-notice")
        self.assertContains(response, "Removed from room")
        self.assertContains(response, "data-mp-kicked-close")

    def test_multiplayer_round_reveal_appears_after_everyone_answers(self):
        room, users = self._started_multiplayer_room()
        tickets = [issue_multiplayer_question_ticket(room, user) for user in users]
        for user, ticket in zip(users, tickets):
            submit_multiplayer_answer(room, user, ticket.token, "A")
        room.refresh_from_db()
        self.assertEqual(room.current_question_index, 1)
        self.assertGreater(room.question_started_at, timezone.now())
        payload = multiplayer_play_payload(room, viewer=users[0], include_question=True)
        self.assertTrue(payload["round_reveal"])
        self.assertEqual(len(payload["reveal_ranking"]), 3)
        self.assertIsNone(payload.get("question"))
        self.assertTrue(any(row.get("is_me") for row in payload["reveal_ranking"]))

    def test_multiplayer_round_reveal_template_exposes_rank_animation_state(self):
        room, users = self._started_multiplayer_room()
        tickets = [issue_multiplayer_question_ticket(room, user) for user in users]
        for user, ticket in zip(users, tickets):
            submit_multiplayer_answer(room, user, ticket.token, "A")
        # Keep this template regression deterministic even when the test database
        # is remote/slow. The production reveal remains server-timed, but the
        # assertion should not randomly miss a five-second window because rendering
        # the next request itself took several seconds.
        room.refresh_from_db()
        room.question_started_at = timezone.now() + timedelta(seconds=30)
        room.save(update_fields=["question_started_at"])
        self.client.force_login(users[0])
        response = self.client.get(reverse("world_multiplayer_play", args=[room.id]))
        self.assertContains(response, "data-mp-rank-reveal")
        self.assertContains(response, "data-previous-rank=")
        self.assertContains(response, "data-final-rank=")
        self.assertContains(response, "data-mp-animated-score")
        self.assertContains(response, "LIVE RANKING")

    def test_multiplayer_js_animates_rank_movement_and_score_countup(self):
        js = Path(settings.BASE_DIR, "static/assets/js/world-multiplayer-v504.js").read_text(encoding="utf-8")
        self.assertIn("--rank-shift", js)
        self.assertIn("data-mp-animated-score", js)
        self.assertIn("animateNumber", js)
        self.assertIn("previousRank", js)
    def test_multiplayer_v50415_ruleset_and_team_schema_are_ready(self):
        host = User.objects.create_user("world_team_host", password="x")
        guest = User.objects.create_user("world_team_guest", password="x")
        room = create_multiplayer_room(
            host,
            subject="math",
            capacity=4,
            game_mode=WorldMultiplayerRoom.GAME_MODE_TEAM_2V2,
        )
        self.assertEqual(room.game_mode, WorldMultiplayerRoom.GAME_MODE_TEAM_2V2)
        self.assertGreaterEqual(room.state_version, 1)
        host_seat = WorldMultiplayerSeat.objects.get(room=room, user=host)
        self.assertEqual(host_seat.team, WorldMultiplayerSeat.TEAM_A)
        joined_room, guest_seat, _ = join_multiplayer_room(guest, join_code=room.join_code)
        self.assertEqual(joined_room.pk, room.pk)
        self.assertEqual(guest_seat.team, WorldMultiplayerSeat.TEAM_B)
        self.assertTrue(guest_seat.is_active)
        self.assertTrue(guest_seat.is_connected)

    def test_multiplayer_v50415_host_leave_transfers_lobby_instead_of_cancelling(self):
        room = create_multiplayer_room(self.u1, subject="math", capacity=4)
        join_multiplayer_room(self.u2, join_code=room.join_code)
        join_multiplayer_room(self.u3, join_code=room.join_code)
        before_version = room.state_version
        self.assertTrue(leave_multiplayer_room(room, self.u1))
        room.refresh_from_db()
        self.assertEqual(room.status, WorldMultiplayerRoom.STATUS_LOBBY)
        self.assertEqual(room.host_id, self.u2.id)
        self.assertGreater(room.state_version, before_version)
        self.assertFalse(WorldMultiplayerSeat.objects.filter(room=room, user=self.u1).exists())
        self.assertTrue(room.includes(self.u2))

    def test_multiplayer_v50415_active_player_leave_does_not_cancel_room(self):
        room, users = self._started_multiplayer_room()
        before_version = room.state_version
        self.assertTrue(leave_multiplayer_room(room, users[0]))
        room.refresh_from_db()
        seat = WorldMultiplayerSeat.objects.get(room=room, user=users[0])
        self.assertEqual(room.status, WorldMultiplayerRoom.STATUS_ACTIVE)
        self.assertFalse(seat.is_active)
        self.assertFalse(seat.is_connected)
        self.assertIsNotNone(seat.left_at)
        self.assertEqual(room.host_id, users[1].id)
        self.assertGreater(room.state_version, before_version)
        self.assertFalse(room.includes(users[0]))
        self.assertTrue(room.includes(users[1]))

    def test_multiplayer_v50415_remaining_players_can_advance_after_departure(self):
        room, users = self._started_multiplayer_room()
        leave_multiplayer_room(room, users[0])
        room.refresh_from_db()
        t2 = issue_multiplayer_question_ticket(room, users[1])
        t3 = issue_multiplayer_question_ticket(room, users[2])
        submit_multiplayer_answer(room, users[1], t2.token, "A")
        room.refresh_from_db()
        self.assertEqual(room.current_question_index, 0)
        submit_multiplayer_answer(room, users[2], t3.token, "A")
        room.refresh_from_db()
        self.assertEqual(room.current_question_index, 1)

    def test_multiplayer_v50415_presence_disconnect_and_reconnect(self):
        room = create_multiplayer_room(self.u1, subject="math", capacity=3)
        _room, seat, _ = join_multiplayer_room(self.u2, join_code=room.join_code)
        now = timezone.now()
        seat.last_seen_at = now - timedelta(seconds=45)
        seat.save(update_fields=["last_seen_at"])
        before_version = room.state_version
        room = reconcile_multiplayer_presence(room, now=now)
        seat.refresh_from_db()
        room.refresh_from_db()
        self.assertFalse(seat.is_connected)
        self.assertIsNotNone(seat.disconnected_at)
        self.assertGreater(room.state_version, before_version)
        disconnected_version = room.state_version
        room, seat = touch_multiplayer_presence(room, self.u2)
        seat.refresh_from_db()
        room.refresh_from_db()
        self.assertTrue(seat.is_connected)
        self.assertIsNone(seat.disconnected_at)
        self.assertGreater(room.state_version, disconnected_version)

    def test_multiplayer_v50415_reconnect_grace_expires_one_player_not_room(self):
        room, users = self._started_multiplayer_room()
        seat = WorldMultiplayerSeat.objects.get(room=room, user=users[2])
        now = timezone.now()
        seat.is_connected = False
        seat.disconnected_at = now - timedelta(seconds=130)
        seat.last_seen_at = now - timedelta(seconds=160)
        seat.save(update_fields=["is_connected", "disconnected_at", "last_seen_at"])
        room = reconcile_multiplayer_presence(room, now=now)
        room.refresh_from_db()
        seat.refresh_from_db()
        self.assertEqual(room.status, WorldMultiplayerRoom.STATUS_ACTIVE)
        self.assertFalse(seat.is_active)
        self.assertIsNotNone(seat.left_at)
        self.assertEqual(WorldMultiplayerSeat.objects.filter(room=room, is_active=True).count(), 2)

    def test_multiplayer_v50415_heartbeat_api_and_state_version(self):
        room = create_multiplayer_room(self.u1, subject="rw", capacity=3)
        self.client.force_login(self.u1)
        response = self.client.post(reverse("world_multiplayer_heartbeat", args=[room.id]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["connected"])
        self.assertGreaterEqual(payload["state_version"], 1)

    def test_multiplayer_v50415_client_rejects_stale_status_and_sends_presence_heartbeat(self):
        js = Path(settings.BASE_DIR, "static/assets/js/world-multiplayer-v504.js").read_text(encoding="utf-8")
        self.assertIn("stateVersion", js)
        self.assertIn("next<stateVersion", js)
        self.assertIn("heartbeat/", js)
        # Presence heartbeats now reschedule *after* their requests finish,
        # rather than piling up via the old overlapping setInterval loops.
        self.assertIn("setTimeout(pulse,delay)", js)
        self.assertIn("setTimeout(pulsePlay,delay)", js)
        self.assertIn("schedulePulse()", js)
        self.assertIn("schedulePlayPulse()", js)
        self.assertNotIn("setInterval(pulse,5000)", js)
        self.assertNotIn("setInterval(pulsePlay,5000)", js)

    def test_multiplayer_v50415_public_queue_index_and_default_ffa(self):
        room = create_multiplayer_room(self.u1, subject="math", capacity=4)
        self.assertEqual(room.game_mode, WorldMultiplayerRoom.GAME_MODE_FFA)
        index_names = {index.name for index in WorldMultiplayerRoom._meta.indexes}
        self.assertIn("world_mp_public_queue_idx", index_names)

    def test_multiplayer_v50415_completed_results_do_not_self_reload(self):
        js = Path(settings.BASE_DIR, "static/assets/js/world-multiplayer-v504.js").read_text(encoding="utf-8")
        self.assertIn("done=play.dataset.roomStatus==='completed'", js)
        self.assertIn("if(done||pollBusy)return", js)


    def test_multiplayer_v50417_team_2v2_assigns_alternating_teams(self):
        u4 = User.objects.create_user("world_team_d", password="x", first_name="Delta")
        room = create_multiplayer_room(
            self.u1,
            subject="math",
            capacity=4,
            game_mode=WorldMultiplayerRoom.GAME_MODE_TEAM_2V2,
        )
        join_multiplayer_room(self.u2, join_code=room.join_code)
        join_multiplayer_room(self.u3, join_code=room.join_code)
        join_multiplayer_room(u4, join_code=room.join_code)
        teams = list(room.seats.order_by("seat_number").values_list("team", flat=True))
        self.assertEqual(teams, [WorldMultiplayerSeat.TEAM_A, WorldMultiplayerSeat.TEAM_B, WorldMultiplayerSeat.TEAM_A, WorldMultiplayerSeat.TEAM_B])

    def test_multiplayer_v50417_team_2v2_requires_all_four_players(self):
        room = create_multiplayer_room(
            self.u1,
            subject="math",
            capacity=4,
            game_mode=WorldMultiplayerRoom.GAME_MODE_TEAM_2V2,
        )
        join_multiplayer_room(self.u2, join_code=room.join_code)
        join_multiplayer_room(self.u3, join_code=room.join_code)
        for user in (self.u1, self.u2, self.u3):
            set_multiplayer_ready(room, user, True)
        self.assertFalse(multiplayer_can_start(room))

    def test_multiplayer_v50417_team_2v2_starts_and_exposes_team_scores(self):
        u4 = User.objects.create_user("world_team_start_d", password="x", first_name="Delta")
        room = create_multiplayer_room(
            self.u1,
            subject="math",
            capacity=4,
            game_mode=WorldMultiplayerRoom.GAME_MODE_TEAM_2V2,
        )
        for user in (self.u2, self.u3, u4):
            join_multiplayer_room(user, join_code=room.join_code)
        for user in (self.u1, self.u2, self.u3, u4):
            set_multiplayer_ready(room, user, True)
        room = start_multiplayer_room(room, self.u1)
        self.assertEqual(room.status, WorldMultiplayerRoom.STATUS_ACTIVE)
        WorldMultiplayerSeat.objects.filter(room=room, user=self.u1).update(score=120)
        WorldMultiplayerSeat.objects.filter(room=room, user=self.u3).update(score=80)
        WorldMultiplayerSeat.objects.filter(room=room, user=self.u2).update(score=90)
        WorldMultiplayerSeat.objects.filter(room=room, user=u4).update(score=70)
        payload = multiplayer_play_payload(room, viewer=self.u1, include_question=False)
        self.assertTrue(payload["is_team_mode"])
        scores = {row["team"]: row["score"] for row in payload["team_standings"]}
        self.assertEqual(scores[WorldMultiplayerSeat.TEAM_A], 200)
        self.assertEqual(scores[WorldMultiplayerSeat.TEAM_B], 160)
        self.assertEqual(payload["my_team"], WorldMultiplayerSeat.TEAM_A)

    def test_multiplayer_v50417_public_queue_separates_ffa_and_2v2(self):
        ffa = create_multiplayer_room(
            self.u1,
            subject="math",
            capacity=4,
            access_type=WorldMultiplayerRoom.ACCESS_PUBLIC,
            game_mode=WorldMultiplayerRoom.GAME_MODE_FFA,
        )
        team_room, _seat, created = join_public_multiplayer_room(
            self.u2,
            subject="math",
            capacity=4,
            question_count=5,
            game_mode=WorldMultiplayerRoom.GAME_MODE_TEAM_2V2,
        )
        self.assertTrue(created)
        self.assertNotEqual(team_room.id, ffa.id)
        self.assertEqual(team_room.game_mode, WorldMultiplayerRoom.GAME_MODE_TEAM_2V2)

    def test_multiplayer_v50417_home_exposes_ffa_and_2v2_without_new_page(self):
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_home"))
        self.assertContains(response, 'name="game_mode" value="ffa"')
        self.assertContains(response, 'name="game_mode" value="team_2v2"')
        self.assertContains(response, '>2v2<')
        js = Path(settings.BASE_DIR, "static/assets/js/world-multiplayer-v504.js").read_text(encoding="utf-8")
        self.assertIn("wireMultiplayerRulesets", js)
        self.assertIn("mode==='team_2v2'", js)
        self.assertIn("cap3.disabled=team", js)

    def test_multiplayer_v50417_team_room_renders_team_lobby(self):
        room = create_multiplayer_room(
            self.u1,
            subject="rw",
            capacity=4,
            game_mode=WorldMultiplayerRoom.GAME_MODE_TEAM_2V2,
        )
        join_multiplayer_room(self.u2, join_code=room.join_code)
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_multiplayer_room", args=[room.id]))
        self.assertContains(response, "2v2 Team Battle")
        self.assertContains(response, "data-mp-team-board")
        self.assertContains(response, "TEAM A")
        self.assertContains(response, "TEAM B")

    def test_multiplayer_v50417_team_play_template_has_team_score_and_reveal_hooks(self):
        template = Path(settings.BASE_DIR, "templates/world/multiplayer_play.html").read_text(encoding="utf-8")
        self.assertIn("data-mp-team-scoreboard", template)
        self.assertIn("data-mp-team-score=", template)
        self.assertIn("mw504-team-reveal", template)
        self.assertIn("team_result", template)
        js = Path(settings.BASE_DIR, "static/assets/js/world-multiplayer-v504.js").read_text(encoding="utf-8")
        self.assertIn("p.team_standings?.forEach", js)

    def test_multiplayer_v504182_stale_lobby_cannot_change_ready_after_start(self):
        room = create_multiplayer_room(self.u1, subject="math", capacity=3)
        join_multiplayer_room(self.u2, join_code=room.join_code)
        join_multiplayer_room(self.u3, join_code=room.join_code)
        for user in (self.u1, self.u2, self.u3):
            set_multiplayer_ready(room, user, True)
        start_multiplayer_room(room, self.u1)
        # `room` is intentionally stale: its in-memory status is still lobby.
        with self.assertRaisesMessage(ValueError, "Ready state can only change in the lobby"):
            set_multiplayer_ready(room, self.u1, False)
        self.assertTrue(WorldMultiplayerSeat.objects.get(room=room, user=self.u1).is_ready)

    def test_multiplayer_v504182_old_host_cannot_start_after_transfer(self):
        room = create_multiplayer_room(self.u1, subject="math", capacity=4)
        join_multiplayer_room(self.u2, join_code=room.join_code)
        join_multiplayer_room(self.u3, join_code=room.join_code)
        leave_multiplayer_room(room, self.u1)
        # A stale room reference still believes u1 is host.
        with self.assertRaisesMessage(ValueError, "Only the host"):
            start_multiplayer_room(room, self.u1)

    def test_multiplayer_v504182_old_host_cannot_kick_after_transfer(self):
        room = create_multiplayer_room(self.u1, subject="math", capacity=4)
        join_multiplayer_room(self.u2, join_code=room.join_code)
        join_multiplayer_room(self.u3, join_code=room.join_code)
        leave_multiplayer_room(room, self.u1)
        with self.assertRaisesMessage(ValueError, "Only the host"):
            kick_multiplayer_participant(room, self.u1, self.u3.id)
        self.assertTrue(WorldMultiplayerSeat.objects.filter(room=room, user=self.u3).exists())

    def test_multiplayer_v504182_heartbeat_focus_cannot_overlap(self):
        js = Path(settings.BASE_DIR, "static/assets/js/world-multiplayer-v504.js").read_text(encoding="utf-8")
        self.assertEqual(js.count("let pulseBusy=false"), 2)
        self.assertIn("if(navigating||pulseBusy||!heartbeatUrl)return", js)
        self.assertIn("if(done||pulseBusy||!playHeartbeatUrl)return", js)
        self.assertIn("finally{pulseBusy=false;if(!navigating)schedulePulse();}", js)
        self.assertIn("finally{pulseBusy=false;if(!done)schedulePlayPulse();}", js)

    def test_multiplayer_v50418_host_ready_works_in_2v2(self):
        room = create_multiplayer_room(
            self.u1,
            subject="math",
            capacity=4,
            game_mode=WorldMultiplayerRoom.GAME_MODE_TEAM_2V2,
        )
        self.client.force_login(self.u1)
        response = self.client.post(
            reverse("world_multiplayer_ready", args=[room.id]),
            {"ready": "1"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["my_ready"])
        self.assertTrue(WorldMultiplayerSeat.objects.get(room=room, user=self.u1).is_ready)

    def test_multiplayer_v50418_first_question_waits_for_visible_launch_countdown(self):
        room = create_multiplayer_room(self.u1, subject="math", capacity=3)
        join_multiplayer_room(self.u2, join_code=room.join_code)
        join_multiplayer_room(self.u3, join_code=room.join_code)
        users = (self.u1, self.u2, self.u3)
        for user in users:
            set_multiplayer_ready(room, user, True)
        room = start_multiplayer_room(room, self.u1)
        self.assertIsNone(room.question_started_at)
        payload = multiplayer_play_payload(room, viewer=self.u1, include_question=True)
        self.assertTrue(payload["launch_waiting"])
        self.assertFalse(payload["opening_countdown"])
        self.assertIsNone(payload.get("question"))
        self.assertFalse(WorldMultiplayerQuestionTicket.objects.filter(room=room).exists())

        # Lobby presence must not arm Q1. Only the play page sends arena=1.
        touch_multiplayer_presence(room, users[0])
        room.refresh_from_db()
        self.assertIsNone(WorldMultiplayerSeat.objects.get(room=room, user=users[0]).arena_ready_at)
        self.assertIsNone(room.question_started_at)

        touch_multiplayer_presence(room, users[0], arena_ready=True)
        touch_multiplayer_presence(room, users[1], arena_ready=True)
        room.refresh_from_db()
        self.assertIsNone(room.question_started_at)
        touch_multiplayer_presence(room, users[2], arena_ready=True)
        room.refresh_from_db()
        self.assertGreater(room.question_started_at, timezone.now())
        payload = multiplayer_play_payload(room, viewer=self.u1, include_question=True)
        self.assertFalse(payload["launch_waiting"])
        self.assertTrue(payload["opening_countdown"])
        self.assertGreaterEqual(payload["start_seconds_remaining"], 1)
        self.assertIsNone(payload.get("question"))

        room.question_started_at = timezone.now() - timedelta(milliseconds=50)
        room.save(update_fields=["question_started_at"])
        payload = multiplayer_play_payload(room, viewer=self.u1, include_question=True)
        self.assertFalse(payload["opening_countdown"])
        self.assertIsNotNone(payload.get("question"))

    def test_multiplayer_v50418_2v2_seat_swap_request_accepts_and_resets_ready(self):
        u4 = User.objects.create_user("world_swap_d", password="x", first_name="Delta")
        room = create_multiplayer_room(
            self.u1,
            subject="math",
            capacity=4,
            game_mode=WorldMultiplayerRoom.GAME_MODE_TEAM_2V2,
        )
        for user in (self.u2, self.u3, u4):
            join_multiplayer_room(user, join_code=room.join_code)
        set_multiplayer_ready(room, self.u1, True)
        set_multiplayer_ready(room, self.u2, True)
        before_a = WorldMultiplayerSeat.objects.get(room=room, user=self.u1)
        before_b = WorldMultiplayerSeat.objects.get(room=room, user=self.u2)
        self.assertEqual((before_a.seat_number, before_b.seat_number), (1, 2))
        swap = request_multiplayer_seat_swap(room, self.u1, self.u2.id)
        self.assertEqual(swap.status, WorldMultiplayerSeatSwapRequest.STATUS_PENDING)
        respond_multiplayer_seat_swap(room, self.u2, swap.id, accept=True)
        after_a = WorldMultiplayerSeat.objects.get(room=room, user=self.u1)
        after_b = WorldMultiplayerSeat.objects.get(room=room, user=self.u2)
        self.assertEqual((after_a.seat_number, after_b.seat_number), (2, 1))
        self.assertEqual(after_a.team, WorldMultiplayerSeat.TEAM_B)
        self.assertEqual(after_b.team, WorldMultiplayerSeat.TEAM_A)
        self.assertFalse(after_a.is_ready)
        self.assertFalse(after_b.is_ready)

    def test_multiplayer_v50418_only_target_can_accept_seat_swap(self):
        room = create_multiplayer_room(
            self.u1,
            subject="math",
            capacity=4,
            game_mode=WorldMultiplayerRoom.GAME_MODE_TEAM_2V2,
        )
        join_multiplayer_room(self.u2, join_code=room.join_code)
        join_multiplayer_room(self.u3, join_code=room.join_code)
        swap = request_multiplayer_seat_swap(room, self.u1, self.u2.id)
        with self.assertRaisesMessage(ValueError, "Only the invited player"):
            respond_multiplayer_seat_swap(room, self.u3, swap.id, accept=True)
        cancel_multiplayer_seat_swap(room, self.u1, swap.id)
        swap.refresh_from_db()
        self.assertEqual(swap.status, WorldMultiplayerSeatSwapRequest.STATUS_CANCELLED)

    def test_multiplayer_v50418_room_payload_exposes_swap_state(self):
        room = create_multiplayer_room(
            self.u1,
            subject="rw",
            capacity=4,
            game_mode=WorldMultiplayerRoom.GAME_MODE_TEAM_2V2,
        )
        join_multiplayer_room(self.u2, join_code=room.join_code)
        swap = request_multiplayer_seat_swap(room, self.u1, self.u2.id)
        sender = multiplayer_room_payload(room, viewer=self.u1)
        target = multiplayer_room_payload(room, viewer=self.u2)
        self.assertEqual(sender["swap_outgoing"]["id"], str(swap.id))
        self.assertIsNone(sender["swap_incoming"])
        self.assertEqual(target["swap_incoming"]["id"], str(swap.id))

    def test_multiplayer_v50418_room_ui_has_swap_and_reliable_ready_hooks(self):
        room = create_multiplayer_room(
            self.u1,
            subject="math",
            capacity=4,
            game_mode=WorldMultiplayerRoom.GAME_MODE_TEAM_2V2,
        )
        join_multiplayer_room(self.u2, join_code=room.join_code)
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_multiplayer_room", args=[room.id]))
        self.assertContains(response, "data-mp-swap-request")
        self.assertContains(response, "data-mp-swap-popover")
        self.assertContains(response, "data-swap-request-url")
        self.assertContains(response, "data-my-ready=")

    def test_multiplayer_v50418_play_page_renders_shared_launch_countdown(self):
        room = create_multiplayer_room(self.u1, subject="math", capacity=3)
        join_multiplayer_room(self.u2, join_code=room.join_code)
        join_multiplayer_room(self.u3, join_code=room.join_code)
        users = (self.u1, self.u2, self.u3)
        for user in users:
            set_multiplayer_ready(room, user, True)
        room = start_multiplayer_room(room, self.u1)
        self.client.force_login(self.u1)
        response = self.client.get(reverse("world_multiplayer_play", args=[room.id]))
        self.assertContains(response, "data-mp-launch-wait")
        self.assertContains(response, "timer is paused")
        self.assertNotContains(response, 'name="question_token"')

        for user in users:
            touch_multiplayer_presence(room, user, arena_ready=True)
        response = self.client.get(reverse("world_multiplayer_play", args=[room.id]))
        self.assertContains(response, "data-mp-opening-countdown")
        self.assertContains(response, "lobby loading time is not charged")
        self.assertNotContains(response, 'name="question_token"')

    def test_multiplayer_v50418_polling_is_non_overlapping_and_responsive_css_exists(self):
        js = Path(settings.BASE_DIR, "static/assets/js/world-multiplayer-v504.js").read_text(encoding="utf-8")
        world_js = Path(settings.BASE_DIR, "static/assets/js/world-v503.js").read_text(encoding="utf-8")
        css = Path(settings.BASE_DIR, "static/assets/css/world-v503.css").read_text(encoding="utf-8")
        self.assertIn("schedulePoll(1100)", js)
        self.assertIn("schedulePlayPoll(950)", js)
        self.assertIn("launchWaiting=play.dataset.launchWaiting==='1'", js)
        self.assertIn("post(playHeartbeatUrl,{arena:'1'})", js)
        self.assertNotIn("setInterval(poll,500)", js)
        self.assertNotIn("setInterval(pollPlay,500)", js)
        self.assertNotIn("setInterval(poll,800)", world_js)
        self.assertIn("schedule(activeIncomingInvite?2500:5000)", world_js)
        self.assertIn("@media (max-width:820px)", css)
        self.assertIn("@media (max-height:800px) and (min-width:821px)", css)
        self.assertIn("mw504-launch-countdown", css)
