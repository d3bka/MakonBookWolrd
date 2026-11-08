from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import apps.base.models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('base', '0041_hollihop_profile_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='generalissuereport',
            name='attachment',
            field=models.FileField(blank=True, null=True, upload_to='issue_reports/%Y/%m/'),
        ),
        migrations.CreateModel(
            name='ReferralInvite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(db_index=True, default=apps.base.models.referral_code_default, max_length=12, unique=True)),
                ('activated_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('referred_user', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referral_invite', to=settings.AUTH_USER_MODEL)),
                ('referrer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_referral_invites', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
