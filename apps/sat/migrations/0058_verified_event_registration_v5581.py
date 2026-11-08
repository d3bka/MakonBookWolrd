# Generated for MakonBook V5581 verified mock-event registration.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("sat", "0057_globalevent_event_type_v5563"),
    ]

    operations = [
        migrations.AddField(
            model_name="globalevent",
            name="registration_enabled",
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text="Require a verified event registration before this event can be started.",
            ),
        ),
        migrations.AddField(
            model_name="globalevent",
            name="show_on_landing",
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text="Show this registration-enabled event on the public landing page.",
            ),
        ),
        migrations.AddField(
            model_name="globalevent",
            name="branch",
            field=models.CharField(
                blank=True,
                max_length=160,
                help_text="Branch / venue shown to participants, e.g. NOVZA.",
            ),
        ),
        migrations.AddField(
            model_name="globalevent",
            name="capacity",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Maximum verified/reserved participants. 0 means unlimited for legacy events.",
            ),
        ),
        migrations.AddField(
            model_name="globalevent",
            name="registration_opens_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="globalevent",
            name="registration_closes_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="globalevent",
            name="verification_minutes",
            field=models.PositiveSmallIntegerField(
                default=10,
                help_text="How long an email verification code remains valid.",
            ),
        ),
        migrations.CreateModel(
            name="EventRegistration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("participant_type", models.CharField(choices=[("makonbook", "MakonBook student"), ("external", "External participant")], db_index=True, max_length=20)),
                ("full_name", models.CharField(max_length=255)),
                ("phone", models.CharField(blank=True, db_index=True, max_length=32)),
                ("email", models.EmailField(db_index=True, max_length=254)),
                ("telegram_username", models.CharField(blank=True, max_length=64)),
                ("status", models.CharField(choices=[("pending", "Pending verification"), ("confirmed", "Confirmed"), ("cancelled", "Cancelled"), ("attended", "Attended"), ("no_show", "No show"), ("expired", "Verification expired")], db_index=True, default="pending", max_length=20)),
                ("verification_code_hash", models.CharField(blank=True, max_length=128)),
                ("verification_expires_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("verification_sent_at", models.DateTimeField(blank=True, null=True)),
                ("verification_attempts", models.PositiveSmallIntegerField(default=0)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("registration_token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("source_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="registrations", to="sat.globalevent")),
                ("guest", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="event_registration", to="sat.guestparticipant")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="global_event_registrations", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="eventregistration",
            constraint=models.UniqueConstraint(condition=models.Q(user__isnull=False), fields=("event", "user"), name="unique_user_event_registration_v5581"),
        ),
        migrations.AddIndex(
            model_name="eventregistration",
            index=models.Index(fields=["event", "status"], name="eventreg_event_status_v5581"),
        ),
        migrations.AddIndex(
            model_name="eventregistration",
            index=models.Index(fields=["event", "email"], name="eventreg_event_email_v5581"),
        ),
        migrations.AddIndex(
            model_name="eventregistration",
            index=models.Index(fields=["event", "phone"], name="eventreg_event_phone_v5581"),
        ),
    ]
