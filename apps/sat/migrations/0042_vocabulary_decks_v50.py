from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('sat', '0041_repair_hollihop_schema_drift'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='VocabularyDeck',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=180)),
                ('description', models.CharField(blank=True, max_length=500)),
                ('new_cards_per_day', models.PositiveSmallIntegerField(default=20)),
                ('max_reviews_per_day', models.PositiveSmallIntegerField(default=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vocabulary_decks', to=settings.AUTH_USER_MODEL)),
                ('source_unit', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cloned_decks', to='sat.vocabularyunit')),
            ],
            options={'ordering': ['-updated_at', '-id']},
        ),
        migrations.CreateModel(
            name='VocabularyDeckWord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('word', models.CharField(max_length=255)),
                ('meaning', models.TextField()),
                ('example', models.TextField(blank=True)),
                ('order', models.PositiveIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('deck', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='words', to='sat.vocabularydeck')),
            ],
            options={'ordering': ['order', 'id']},
        ),
        migrations.CreateModel(
            name='VocabularyDeckWordProgress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('new', 'New'), ('learning', 'Learning'), ('mastered', 'Mastered')], default='new', max_length=16)),
                ('times_seen', models.PositiveIntegerField(default=0)),
                ('correct_count', models.PositiveIntegerField(default=0)),
                ('incorrect_count', models.PositiveIntegerField(default=0)),
                ('consecutive_correct', models.PositiveIntegerField(default=0)),
                ('last_reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('mastered_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vocabulary_deck_progress', to=settings.AUTH_USER_MODEL)),
                ('word', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='progress', to='sat.vocabularydeckword')),
            ],
        ),
        migrations.AddIndex(model_name='vocabularydeck', index=models.Index(fields=['owner', '-updated_at'], name='vocab_deck_owner_updated')),
        migrations.AddConstraint(model_name='vocabularydeckword', constraint=models.UniqueConstraint(fields=('deck', 'word'), name='unique_vocab_deck_word')),
        migrations.AddConstraint(model_name='vocabularydeckwordprogress', constraint=models.UniqueConstraint(fields=('user', 'word'), name='unique_vocab_deck_progress')),
        migrations.AddIndex(model_name='vocabularydeckwordprogress', index=models.Index(fields=['user', 'status'], name='vocab_deck_prog_status')),
    ]
