from django.contrib import admin

from .models import (GameQuestionPool, WorldAnswer, WorldMatch, WorldQuestionTicket, WorldRating, WorldMultiplayerRoom, WorldMultiplayerSeat, WorldMultiplayerQuestionTicket, WorldMultiplayerAnswer)


@admin.register(WorldRating)
class WorldRatingAdmin(admin.ModelAdmin):
    list_display = ("user", "subject", "rating", "tier", "wins", "losses", "draws", "ranked_played", "updated_at")
    list_filter = ("subject",)
    search_fields = ("user__username", "user__first_name", "user__last_name")


@admin.register(GameQuestionPool)
class GameQuestionPoolAdmin(admin.ModelAdmin):
    list_display = ("id", "subject", "difficulty", "game_enabled", "quality_verified", "estimated_seconds", "times_used", "correct_rate", "last_used_at")
    list_filter = ("subject", "difficulty", "game_enabled", "quality_verified")
    list_editable = ("difficulty", "game_enabled", "quality_verified", "estimated_seconds")
    search_fields = ("math_question__question", "english_question__question")
    readonly_fields = ("times_used", "answer_count", "correct_count", "last_used_at", "created_at", "updated_at")


@admin.register(WorldMatch)
class WorldMatchAdmin(admin.ModelAdmin):
    list_display = ("id", "subject", "mode", "status", "player1", "player2", "player1_score", "player2_score", "mmr_weight", "created_at")
    list_filter = ("subject", "mode", "status")
    search_fields = ("player1__username", "player2__username")
    readonly_fields = ("question_ids", "question_pool_ids", "player1_last_seen_at", "player2_last_seen_at")


@admin.register(WorldQuestionTicket)
class WorldQuestionTicketAdmin(admin.ModelAdmin):
    list_display = ("match", "user", "question_index", "issued_at", "deadline_at", "consumed_at")
    search_fields = ("user__username", "match__id")
    readonly_fields = ("token", "issued_at", "deadline_at", "consumed_at")


@admin.register(WorldAnswer)
class WorldAnswerAdmin(admin.ModelAdmin):
    list_display = ("match", "user", "question_index", "selected_answer", "is_correct", "points", "response_ms", "integrity_flag", "answered_at")
    list_filter = ("is_correct", "integrity_flag")


@admin.register(WorldMultiplayerRoom)
class WorldMultiplayerRoomAdmin(admin.ModelAdmin):
    list_display = ("join_code", "subject", "capacity", "status", "host", "created_at", "started_at")
    list_filter = ("subject", "capacity", "status")
    search_fields = ("join_code", "host__username", "host__first_name", "host__last_name")
    readonly_fields = ("join_code", "question_pool_ids", "created_at", "started_at", "completed_at", "current_question_index", "question_started_at")


@admin.register(WorldMultiplayerSeat)
class WorldMultiplayerSeatAdmin(admin.ModelAdmin):
    list_display = ("room", "seat_number", "user", "is_ready", "score", "joined_at", "last_seen_at")
    list_filter = ("is_ready", "room__subject", "room__status")
    search_fields = ("room__join_code", "user__username", "user__first_name", "user__last_name")


@admin.register(WorldMultiplayerQuestionTicket)
class WorldMultiplayerQuestionTicketAdmin(admin.ModelAdmin):
    list_display = ("room", "user", "question_index", "issued_at", "deadline_at", "consumed_at")
    search_fields = ("room__join_code", "user__username")
    readonly_fields = ("token", "issued_at", "deadline_at", "consumed_at")


@admin.register(WorldMultiplayerAnswer)
class WorldMultiplayerAnswerAdmin(admin.ModelAdmin):
    list_display = ("room", "user", "question_index", "selected_answer", "is_correct", "points", "response_ms", "integrity_flag", "answered_at")
    list_filter = ("is_correct", "integrity_flag", "room__subject")
    search_fields = ("room__join_code", "user__username")
