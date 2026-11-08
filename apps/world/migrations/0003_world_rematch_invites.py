from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("world", "0002_world_competitive_core"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="worldmatch",
            name="invitee",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="world_match_invites", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="worldmatch",
            name="rematch_of",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="rematches", to="world.worldmatch"),
        ),
    ]
