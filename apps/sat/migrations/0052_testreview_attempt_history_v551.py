from collections import defaultdict

from django.db import migrations, models


VALID_MODES = {
    'full_test',
    'rw_only',
    'math_only',
    'single_english_m1',
    'single_english_m2',
    'single_math_m1',
    'single_math_m2',
}


def _norm_section(value):
    value = str(value or '').strip().lower()
    if value in {'english', 'ebrw', 'reading', 'reading_writing', 'reading-and-writing'}:
        return 'english'
    if value in {'math', 'mathematics'}:
        return 'math'
    return value


def _norm_module(value):
    value = str(value or '').strip().lower()
    if value in {'module_1', 'module1', '1'}:
        return 'm1'
    if value in {'module_2', 'module2', '2'}:
        return 'm2'
    return value


def _infer_mode(slots):
    english = {module for section, module in slots if section == 'english'}
    math = {module for section, module in slots if section == 'math'}

    if english and math:
        return 'full_test'
    if english:
        if english == {'m1'}:
            return 'single_english_m1'
        if english == {'m2'}:
            return 'single_english_m2'
        return 'rw_only'
    if math:
        if math == {'m1'}:
            return 'single_math_m1'
        if math == {'m2'}:
            return 'single_math_m2'
        return 'math_only'
    return 'full_test'


def _flush_review_batch(TestReview, TestStage, TestModule, reviews):
    if not reviews:
        return

    attempt_ids = [review.attempt_id for review in reviews if review.attempt_id]
    if not attempt_ids:
        return

    stage_map = {}
    stage_rows = (
        TestStage.objects
        .filter(test_type='regular', attempt_id__in=attempt_ids)
        .values(
            'user_id',
            'test_id',
            'attempt_id',
            'mode',
            'integrity_mode',
            'integrity_violation_count',
            'integrity_fullscreen_required',
            'integrity_terminated_at',
            'updated_at',
            'id',
        )
        .order_by('updated_at', 'id')
    )
    for row in stage_rows.iterator(chunk_size=1000):
        key = (row['user_id'], row['test_id'], row['attempt_id'])
        # Ordered oldest -> newest, so the latest row wins.
        stage_map[key] = row

    slot_map = defaultdict(set)
    module_rows = (
        TestModule.objects
        .filter(test_type='regular', attempt_id__in=attempt_ids)
        .values('user_id', 'test_id', 'attempt_id', 'section', 'module')
    )
    for row in module_rows.iterator(chunk_size=2000):
        key = (row['user_id'], row['test_id'], row['attempt_id'])
        slot_map[key].add(
            (_norm_section(row['section']), _norm_module(row['module']))
        )

    for review in reviews:
        key = (review.user_id, review.test_id, review.attempt_id)
        stage = stage_map.get(key)
        slots = slot_map.get(key, set())

        run_mode = str((stage or {}).get('mode') or '').strip().lower()
        if run_mode not in VALID_MODES:
            run_mode = _infer_mode(slots)

        integrity_mode = str((stage or {}).get('integrity_mode') or '').strip().lower()
        if integrity_mode not in {'off', 'standard', 'strict'}:
            integrity_mode = 'unknown'

        review.run_mode = run_mode
        review.integrity_mode = integrity_mode
        review.integrity_violation_count = int(
            (stage or {}).get('integrity_violation_count') or 0
        )
        review.integrity_fullscreen_required = bool(
            (stage or {}).get('integrity_fullscreen_required') or False
        )
        review.integrity_terminated = bool(
            (stage or {}).get('integrity_terminated_at')
        )

    TestReview.objects.bulk_update(
        reviews,
        [
            'run_mode',
            'integrity_mode',
            'integrity_violation_count',
            'integrity_fullscreen_required',
            'integrity_terminated',
        ],
        batch_size=500,
    )


def backfill_attempt_metadata(apps, schema_editor):
    """
    Optimized Stage 2 backfill.

    The original V55.1 migration performed 3 DB operations for every historical
    TestReview (stage lookup + module lookup + UPDATE), which becomes very slow
    on a real PostgreSQL database.

    This version processes reviews in batches:
      - 1 stage query per batch
      - 1 module query per batch
      - 1 bulk UPDATE per batch
    """
    TestReview = apps.get_model('sat', 'TestReview')
    TestStage = apps.get_model('sat', 'TestStage')
    TestModule = apps.get_model('sat', 'TestModule')

    queryset = (
        TestReview.objects
        .filter(
            test__isnull=False,
            attempt_id__isnull=False,
            test_type='regular',
        )
        .only(
            'id',
            'user_id',
            'test_id',
            'attempt_id',
            'run_mode',
            'integrity_mode',
            'integrity_violation_count',
            'integrity_fullscreen_required',
            'integrity_terminated',
        )
        .order_by('id')
    )

    batch = []
    for review in queryset.iterator(chunk_size=500):
        batch.append(review)
        if len(batch) >= 500:
            _flush_review_batch(TestReview, TestStage, TestModule, batch)
            batch = []

    if batch:
        _flush_review_batch(TestReview, TestStage, TestModule, batch)


class Migration(migrations.Migration):
    dependencies = [
        ('sat', '0051_teststage_mode_v5411'),
    ]

    operations = [
        migrations.AddField(
            model_name='testreview',
            name='run_mode',
            field=models.CharField(default='full_test', max_length=50),
        ),
        migrations.AddField(
            model_name='testreview',
            name='integrity_mode',
            field=models.CharField(default='unknown', max_length=16),
        ),
        migrations.AddField(
            model_name='testreview',
            name='integrity_violation_count',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='testreview',
            name='integrity_fullscreen_required',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='testreview',
            name='integrity_terminated',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(backfill_attempt_metadata, migrations.RunPython.noop),
    ]
