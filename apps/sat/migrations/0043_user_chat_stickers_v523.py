from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import apps.sat.storages


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('sat', '0042_vocabulary_decks_v50'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserChatSticker',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(storage=apps.sat.storages.PublicStorage(), upload_to='classroom_chat_stickers/')),
                ('title', models.CharField(blank=True, max_length=80)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_stickers', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at', '-id']},
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='sticker',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='messages', to='sat.userchatsticker'),
        ),
    ]
