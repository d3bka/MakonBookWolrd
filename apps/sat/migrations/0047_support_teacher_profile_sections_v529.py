from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('sat', '0046_chat_sticker_packs_v525'),
    ]

    operations = [
        migrations.CreateModel(
            name='SupportTeacherProfileSection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=120)),
                ('body', models.TextField(blank=True, max_length=2000)),
                ('url', models.URLField(blank=True)),
                ('order', models.PositiveSmallIntegerField(default=0)),
                ('is_visible', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='custom_sections', to='sat.supportteacherprofile')),
            ],
            options={
                'ordering': ['order', 'created_at', 'id'],
            },
        ),
    ]
