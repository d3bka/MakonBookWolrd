from __future__ import annotations

import secrets
import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from apps.sat.models import English_Question, Math_Question


class WorldRating(models.Model):
    SUBJECT_MATH = "math"
    SUBJECT_RW = "rw"
    SUBJECT_CHOICES = (
        (SUBJECT_MATH, "Math"),
        (SUBJECT_RW, "Reading & Writing"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="world_ratings")
    subject = models.CharField(max_length=8, choices=SUBJECT_CHOICES)
    rating = models.PositiveIntegerField(default=1000, db_index=True)
    wins = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)
    draws = models.PositiveIntegerField(default=0)
    streak = models.IntegerField(default=0)
    ranked_played = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "subject"], name="world_unique_user_subject_rating"),
        ]
        indexes = [models.Index(fields=["subject", "-rating"], name="world_subject_rating_idx")]
        ordering = ["-rating", "user_id"]

    @property
    def tier(self):
        score = self.rating
        if score >= 2050:
            return "Pro"
        if score >= 1900:
            return "Master"
        if score >= 1750:
            return "Legendary"
        if score >= 1600:
            return "Mythical"
        if score >= 1450:
            return "Diamond"
        if score >= 1300:
            return "Gold"
        if score >= 1150:
            return "Silver"
        return "Bronze"

    def __str__(self):
        return f"{self.user.username} · {self.get_subject_display()} · {self.rating}"


class GameQuestionPool(models.Model):
    DIFFICULTY_EASY = "easy"
    DIFFICULTY_MEDIUM = "medium"
    DIFFICULTY_HARD = "hard"
    DIFFICULTY_CHOICES = (
        (DIFFICULTY_EASY, "Easy"),
        (DIFFICULTY_MEDIUM, "Medium"),
        (DIFFICULTY_HARD, "Hard"),
    )

    subject = models.CharField(max_length=8, choices=WorldRating.SUBJECT_CHOICES, db_index=True)
    math_question = models.OneToOneField(
        Math_Question,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="world_pool_entry",
    )
    english_question = models.OneToOneField(
        English_Question,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="world_pool_entry",
    )
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default=DIFFICULTY_MEDIUM, db_index=True)
    game_enabled = models.BooleanField(default=True, db_index=True)
    quality_verified = models.BooleanField(default=False, db_index=True)
    estimated_seconds = models.PositiveSmallIntegerField(default=60)
    times_used = models.PositiveIntegerField(default=0)
    answer_count = models.PositiveIntegerField(default=0)
    correct_count = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["subject", "game_enabled", "quality_verified", "difficulty"], name="world_pool_pick_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(subject=WorldRating.SUBJECT_MATH, math_question__isnull=False, english_question__isnull=True)
                    | models.Q(subject=WorldRating.SUBJECT_RW, math_question__isnull=True, english_question__isnull=False)
                ),
                name="world_pool_source_matches_subject",
            )
        ]

    @property
    def question(self):
        return self.math_question if self.subject == WorldRating.SUBJECT_MATH else self.english_question

    @property
    def correct_rate(self):
        if not self.answer_count:
            return None
        return round((self.correct_count / self.answer_count) * 100, 1)

    def __str__(self):
        source = self.math_question_id or self.english_question_id
        return f"{self.get_subject_display()} · Q{source} · {self.get_difficulty_display()}"


class WorldMatch(models.Model):
    MODE_QUICK = "quick"
    MODE_RANKED = "ranked"
    MODE_CHOICES = ((MODE_QUICK, "Quick Match"), (MODE_RANKED, "Ranked"))

    STATUS_WAITING = "waiting"
    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = (
        (STATUS_WAITING, "Waiting"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.CharField(max_length=8, choices=WorldRating.SUBJECT_CHOICES)
    mode = models.CharField(max_length=8, choices=MODE_CHOICES)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_WAITING, db_index=True)
    player1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="world_matches_as_player1")
    player2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="world_matches_as_player2", null=True, blank=True)
    invitee = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="world_match_invites", null=True, blank=True)
    rematch_of = models.ForeignKey("self", on_delete=models.SET_NULL, related_name="rematches", null=True, blank=True)
    winner = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="world_matches_won", null=True, blank=True)
    # Legacy SAT source IDs are retained for backward compatibility with already-created matches.
    question_ids = models.JSONField(default=list, blank=True)
    # New V50.3 competitive matches also pin the curated pool rows used for the match.
    question_pool_ids = models.JSONField(default=list, blank=True)
    player1_score = models.PositiveIntegerField(default=0)
    player2_score = models.PositiveIntegerField(default=0)
    player1_rating_before = models.PositiveIntegerField(default=1000)
    player2_rating_before = models.PositiveIntegerField(default=1000)
    player1_rating_after = models.PositiveIntegerField(default=1000)
    player2_rating_after = models.PositiveIntegerField(default=1000)
    mmr_weight = models.DecimalField(max_digits=4, decimal_places=2, default=1.00)
    player1_last_seen_at = models.DateTimeField(null=True, blank=True)
    player2_last_seen_at = models.DateTimeField(null=True, blank=True)
    disconnect_forfeit_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="world_disconnect_forfeits",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "subject", "mode", "created_at"], name="world_queue_lookup_idx")]

    @property
    def total_questions(self):
        return len(self.question_pool_ids or self.question_ids or [])

    def includes(self, user):
        return bool(user and user.is_authenticated and (self.player1_id == user.id or self.player2_id == user.id))

    def score_for(self, user):
        if not user:
            return 0
        if self.player1_id == user.id:
            return self.player1_score
        if self.player2_id == user.id:
            return self.player2_score
        return 0

    def opponent_for(self, user):
        if self.player1_id == user.id:
            return self.player2
        if self.player2_id == user.id:
            return self.player1
        return None

    def __str__(self):
        return f"{self.get_subject_display()} · {self.get_mode_display()} · {self.status} · {self.id}"


class WorldQuestionTicket(models.Model):
    match = models.ForeignKey(WorldMatch, on_delete=models.CASCADE, related_name="question_tickets")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="world_question_tickets")
    question_index = models.PositiveSmallIntegerField()
    token = models.CharField(max_length=64, unique=True, db_index=True, default=secrets.token_urlsafe, editable=False)
    issued_at = models.DateTimeField(default=timezone.now)
    deadline_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["match", "user", "question_index"], name="world_unique_question_ticket"),
        ]
        ordering = ["question_index"]


class WorldAnswer(models.Model):
    INTEGRITY_OK = "ok"
    INTEGRITY_TOO_FAST = "too_fast"
    INTEGRITY_TIMEOUT = "timeout"
    INTEGRITY_CHOICES = (
        (INTEGRITY_OK, "OK"),
        (INTEGRITY_TOO_FAST, "Suspiciously fast"),
        (INTEGRITY_TIMEOUT, "Timed out"),
    )

    match = models.ForeignKey(WorldMatch, on_delete=models.CASCADE, related_name="answers")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="world_answers")
    question_index = models.PositiveSmallIntegerField()
    pool_entry = models.ForeignKey(GameQuestionPool, on_delete=models.SET_NULL, null=True, blank=True, related_name="answers")
    selected_answer = models.CharField(max_length=400, blank=True)
    is_correct = models.BooleanField(default=False)
    points = models.PositiveSmallIntegerField(default=0)
    response_ms = models.PositiveIntegerField(default=0)
    integrity_flag = models.CharField(max_length=16, choices=INTEGRITY_CHOICES, default=INTEGRITY_OK)
    answered_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["match", "user", "question_index"], name="world_unique_match_user_question")]
        ordering = ["question_index"]

    def __str__(self):
        return f"{self.match_id} · {self.user.username} · Q{self.question_index + 1}"


class WorldMultiplayerRoom(models.Model):
    STATUS_LOBBY = "lobby"
    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = (
        (STATUS_LOBBY, "Lobby"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    )

    CAPACITY_THREE = 3
    CAPACITY_FOUR = 4
    CAPACITY_CHOICES = ((CAPACITY_THREE, "3 players"), (CAPACITY_FOUR, "4 players"))

    QUESTION_COUNT_CHOICES = ((5, "5 questions"), (10, "10 questions"), (15, "15 questions"), (20, "20 questions"))

    ACCESS_PRIVATE = "private"
    ACCESS_PUBLIC = "public"
    ACCESS_TYPE_CHOICES = ((ACCESS_PRIVATE, "Private"), (ACCESS_PUBLIC, "Public"))

    GAME_MODE_FFA = "ffa"
    GAME_MODE_TEAM_2V2 = "team_2v2"
    GAME_MODE_SURVIVAL = "survival"
    GAME_MODE_CLASSROOM = "classroom"
    GAME_MODE_CHOICES = (
        (GAME_MODE_FFA, "Free for all"),
        (GAME_MODE_TEAM_2V2, "2v2"),
        (GAME_MODE_SURVIVAL, "Survival"),
        (GAME_MODE_CLASSROOM, "Classroom Battle"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name="world_multiplayer_rooms_hosted")
    subject = models.CharField(max_length=8, choices=WorldRating.SUBJECT_CHOICES)
    capacity = models.PositiveSmallIntegerField(choices=CAPACITY_CHOICES, default=CAPACITY_FOUR)
    question_count = models.PositiveSmallIntegerField(choices=QUESTION_COUNT_CHOICES, default=5)
    access_type = models.CharField(max_length=12, choices=ACCESS_TYPE_CHOICES, default=ACCESS_PRIVATE, db_index=True)
    game_mode = models.CharField(max_length=16, choices=GAME_MODE_CHOICES, default=GAME_MODE_FFA, db_index=True)
    join_code = models.CharField(max_length=8, unique=True, db_index=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_LOBBY, db_index=True)
    question_pool_ids = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    current_question_index = models.PositiveSmallIntegerField(default=0)
    question_started_at = models.DateTimeField(null=True, blank=True)
    state_version = models.PositiveBigIntegerField(default=1)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "subject", "created_at"], name="world_mp_room_lookup_idx"),
            models.Index(
                fields=["status", "access_type", "game_mode", "subject", "capacity", "question_count", "created_at"],
                name="world_mp_public_queue_idx",
            ),
        ]

    @property
    def occupied_seats(self):
        prefetched = getattr(self, "_prefetched_objects_cache", {}).get("seats")
        if prefetched is not None:
            return sum(1 for seat in prefetched if seat.is_active)
        return self.seats.filter(is_active=True).count()

    @property
    def ready_seats(self):
        prefetched = getattr(self, "_prefetched_objects_cache", {}).get("seats")
        if prefetched is not None:
            return sum(1 for seat in prefetched if seat.is_active and seat.is_ready)
        return self.seats.filter(is_active=True, is_ready=True).count()

    def includes(self, user):
        if not user or not getattr(user, "is_authenticated", False):
            return False
        return self.seats.filter(user=user, is_active=True).exists()

    def __str__(self):
        return f"Multiplayer {self.join_code} · {self.get_subject_display()} · {self.status}"


class WorldMultiplayerSeat(models.Model):
    TEAM_NONE = ""
    TEAM_A = "a"
    TEAM_B = "b"
    TEAM_CHOICES = ((TEAM_NONE, "No team"), (TEAM_A, "Team A"), (TEAM_B, "Team B"))

    room = models.ForeignKey(WorldMultiplayerRoom, on_delete=models.CASCADE, related_name="seats")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="world_multiplayer_seats")
    seat_number = models.PositiveSmallIntegerField()
    is_ready = models.BooleanField(default=False, db_index=True)
    score = models.PositiveIntegerField(default=0)
    team = models.CharField(max_length=8, choices=TEAM_CHOICES, default=TEAM_NONE, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    is_connected = models.BooleanField(default=True, db_index=True)
    disconnected_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)
    arena_ready_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["seat_number"]
        constraints = [
            models.UniqueConstraint(fields=["room", "user"], name="world_mp_unique_room_user"),
            models.UniqueConstraint(
                fields=["room", "seat_number"],
                name="world_mp_unique_room_seat",
                deferrable=models.Deferrable.DEFERRED,
            ),
            models.CheckConstraint(condition=models.Q(seat_number__gte=1, seat_number__lte=4), name="world_mp_seat_range_1_4"),
        ]

    def __str__(self):
        return f"{self.room.join_code} · seat {self.seat_number} · {self.user.username}"


class WorldMultiplayerSeatSwapRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_DECLINED = "declined"
    STATUS_CANCELLED = "cancelled"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_DECLINED, "Declined"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_EXPIRED, "Expired"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(WorldMultiplayerRoom, on_delete=models.CASCADE, related_name="seat_swap_requests")
    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name="world_multiplayer_swap_requests_sent")
    target = models.ForeignKey(User, on_delete=models.CASCADE, related_name="world_multiplayer_swap_requests_received")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["room", "status", "created_at"], name="world_mp_swap_room_idx"),
            models.Index(fields=["target", "status", "created_at"], name="world_mp_swap_target_idx"),
        ]

    def __str__(self):
        return f"{self.room.join_code} · {self.requester.username} -> {self.target.username} · {self.status}"


class WorldMultiplayerQuestionTicket(models.Model):
    room = models.ForeignKey(WorldMultiplayerRoom, on_delete=models.CASCADE, related_name="question_tickets")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="world_multiplayer_question_tickets")
    question_index = models.PositiveSmallIntegerField()
    token = models.CharField(max_length=64, unique=True, db_index=True, default=secrets.token_urlsafe, editable=False)
    issued_at = models.DateTimeField(default=timezone.now)
    deadline_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["room", "user", "question_index"], name="world_mp_unique_question_ticket"),
        ]
        ordering = ["question_index"]


class WorldMultiplayerAnswer(models.Model):
    INTEGRITY_OK = "ok"
    INTEGRITY_TOO_FAST = "too_fast"
    INTEGRITY_TIMEOUT = "timeout"
    INTEGRITY_CHOICES = (
        (INTEGRITY_OK, "OK"),
        (INTEGRITY_TOO_FAST, "Suspiciously fast"),
        (INTEGRITY_TIMEOUT, "Timed out"),
    )

    room = models.ForeignKey(WorldMultiplayerRoom, on_delete=models.CASCADE, related_name="answers")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="world_multiplayer_answers")
    question_index = models.PositiveSmallIntegerField()
    pool_entry = models.ForeignKey(GameQuestionPool, on_delete=models.SET_NULL, null=True, blank=True, related_name="multiplayer_answers")
    selected_answer = models.CharField(max_length=400, blank=True)
    is_correct = models.BooleanField(default=False)
    points = models.PositiveSmallIntegerField(default=0)
    response_ms = models.PositiveIntegerField(default=0)
    integrity_flag = models.CharField(max_length=16, choices=INTEGRITY_CHOICES, default=INTEGRITY_OK)
    answered_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["room", "user", "question_index"], name="world_mp_unique_room_user_question"),
        ]
        ordering = ["question_index", "answered_at"]
