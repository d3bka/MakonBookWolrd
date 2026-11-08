from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("sat", "0059_alter_globalevent_capacity"),
    ]

    operations = [
        migrations.CreateModel(
            name="PublicPlacementLead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("first_name", models.CharField(max_length=80)),
                ("last_name", models.CharField(max_length=80)),
                ("phone_number", models.CharField(db_index=True, max_length=32)),
                ("consent_to_contact", models.BooleanField(default=True)),
                ("started_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("attempt", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="public_placement_lead", to="sat.globaleventattempt")),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="public_placement_leads", to="sat.globalevent")),
                ("guest", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="public_placement_lead", to="sat.guestparticipant")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="publicplacementlead",
            index=models.Index(fields=["event", "-created_at"], name="sat_pubpl_event_created"),
        ),
        migrations.AddIndex(
            model_name="publicplacementlead",
            index=models.Index(fields=["phone_number", "-created_at"], name="sat_pubpl_phone_created"),
        ),
        migrations.CreateModel(
            name="PlacementTelegramNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("started", "Placement started"), ("completed", "Placement completed")], max_length=20)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed")], db_index=True, default="pending", max_length=20)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("next_attempt_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("last_error", models.TextField(blank=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("lead", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="telegram_notifications", to="sat.publicplacementlead")),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.AddConstraint(
            model_name="placementtelegramnotification",
            constraint=models.UniqueConstraint(fields=("lead", "kind"), name="unique_public_placement_notice_kind"),
        ),
    ]
