"""V106: give every account a UserProfile.

A few old accounts had none, so Hollihop synchronization crashed on them
(RelatedObjectDoesNotExist, student 4145) and so would any code reading user.profile.
"""
from django.conf import settings
from django.db import migrations


def create_missing_profiles(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    UserProfile = apps.get_model("base", "UserProfile")
    missing = list(User.objects.filter(profile__isnull=True).values_list("id", flat=True))
    UserProfile.objects.bulk_create([UserProfile(user_id=user_id) for user_id in missing], batch_size=500, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0050_account_merge_v104"),
    ]

    operations = [
        migrations.RunPython(create_missing_profiles, migrations.RunPython.noop),
    ]
