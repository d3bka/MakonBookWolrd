# Generated for MakonBook V50.2 gamification core.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GamificationProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("xp_total", models.PositiveIntegerField(default=0)),
                ("current_streak", models.PositiveIntegerField(default=0)),
                ("best_streak", models.PositiveIntegerField(default=0)),
                ("last_active_date", models.DateField(blank=True, null=True)),
                ("bootstrap_version", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="gamification_profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="UserAchievement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=140)),
                ("description", models.CharField(max_length=300)),
                ("icon", models.CharField(default="bi-trophy", max_length=40)),
                ("unlocked_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="gamification_achievements", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-unlocked_at", "-id"]},
        ),
        migrations.CreateModel(
            name="XPEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("activity", "Activity"), ("quest", "Quest reward"), ("bootstrap", "Bootstrap")], default="activity", max_length=16)),
                ("source_key", models.CharField(max_length=160)),
                ("title", models.CharField(max_length=180)),
                ("amount", models.PositiveIntegerField(default=0)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="gamification_xp_events", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="QuestProgress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=180)),
                ("period_type", models.CharField(choices=[("daily", "Daily"), ("weekly", "Weekly")], max_length=12)),
                ("period_start", models.DateField(db_index=True)),
                ("progress", models.PositiveIntegerField(default=0)),
                ("target", models.PositiveIntegerField(default=1)),
                ("reward_xp", models.PositiveIntegerField(default=0)),
                ("seen_keys", models.JSONField(blank=True, default=list)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("rewarded_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="gamification_quests", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["period_type", "code"]},
        ),
        migrations.AddConstraint(
            model_name="userachievement",
            constraint=models.UniqueConstraint(fields=("user", "code"), name="unique_gamification_achievement"),
        ),
        migrations.AddConstraint(
            model_name="xpevent",
            constraint=models.UniqueConstraint(fields=("user", "source_key"), name="unique_gamification_xp_source"),
        ),
        migrations.AddIndex(
            model_name="xpevent",
            index=models.Index(fields=["user", "created_at"], name="gamification_xp_user_date"),
        ),
        migrations.AddConstraint(
            model_name="questprogress",
            constraint=models.UniqueConstraint(fields=("user", "code", "period_start"), name="unique_gamification_quest_period"),
        ),
        migrations.AddIndex(
            model_name="questprogress",
            index=models.Index(fields=["user", "period_type", "period_start"], name="gamification_quest_user_period"),
        ),
    ]
