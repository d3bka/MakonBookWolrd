from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('sat', '0045_homework_vocabulary_quiz_v524'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserChatStickerPack',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=80)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_sticker_packs', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['created_at', 'id']},
        ),
        migrations.AddConstraint(
            model_name='userchatstickerpack',
            constraint=models.UniqueConstraint(fields=('user', 'title'), name='sat_chat_pack_user_title_uniq'),
        ),
        migrations.AddField(
            model_name='userchatsticker',
            name='pack',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stickers', to='sat.userchatstickerpack'),
        ),
    ]
