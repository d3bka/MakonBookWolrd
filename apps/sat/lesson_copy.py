"""V102: copy units (ClassroomLesson) with their materials from any classroom into another.

The copy is independent: titles, summaries and materials are new rows, files are
new copies (deleting the source class never breaks the copy), SAT tests and
vocabulary units are shared references. Student attempts, scores, access codes
and scheduled score dates are never copied.
"""
from __future__ import annotations

import logging
import os

from django.core.files import File
from django.db import transaction
from django.db.models import Max

logger = logging.getLogger(__name__)


def source_label(classroom) -> str:
    teacher = classroom.teacher
    name = (teacher.get_full_name() or teacher.username) if teacher else ""
    return f"{classroom.name} · {name}" if name else classroom.name


def _bucket_copy(field_file, target_field_file) -> bool:
    """R2/S3: copy the object inside the bucket (no download), so big presentations are quick."""
    storage = field_file.storage
    if not hasattr(storage, "bucket") or type(target_field_file.storage) is not type(storage):
        return False
    from storages.utils import clean_name

    name = target_field_file.field.generate_filename(target_field_file.instance, os.path.basename(field_file.name))
    name = target_field_file.storage.get_available_name(name, max_length=target_field_file.field.max_length)
    source_key = storage._normalize_name(clean_name(field_file.name))
    target_key = storage._normalize_name(clean_name(name))
    storage.bucket.copy({"Bucket": storage.bucket_name, "Key": source_key}, target_key)
    target_field_file.name = name
    return True


def _copy_file(field_file, target_field_file) -> bool:
    """Write a new copy of ``field_file`` into ``target_field_file``. False when the source is gone."""
    if not field_file:
        return False
    try:
        if _bucket_copy(field_file, target_field_file):
            return True
    except Exception as exc:  # noqa: BLE001 - fall back to a normal download and upload
        logger.info("Bucket copy of %s failed (%s); copying through the server.", field_file.name, exc.__class__.__name__)
    try:
        field_file.open("rb")
        try:
            target_field_file.save(os.path.basename(field_file.name), File(field_file), save=False)
        finally:
            field_file.close()
        return True
    except Exception as exc:  # noqa: BLE001 - a missing source file must not abort the whole import
        logger.warning("Could not copy %s: %s", field_file.name, exc.__class__.__name__)
        return False


def _copy_resource(resource, lesson):
    from .models import ClassroomLessonResource as R

    copy = R(
        lesson=lesson,
        title=resource.title,
        resource_type=resource.resource_type,
        url=resource.url,
        test_id=resource.test_id,
        vocabulary_unit_id=resource.vocabulary_unit_id,
        vocabulary_question_count=resource.vocabulary_question_count,
        vocabulary_quiz_mode=resource.vocabulary_quiz_mode,
        access_code="",
        total_points=resource.total_points,
        score_visibility=R.SCORE_HIDDEN if resource.score_visibility == R.SCORE_SCHEDULED else resource.score_visibility,
        score_visible_at=None,
        description=resource.description,
        is_visible=resource.is_visible,
        order=resource.order,
    )
    if resource.file and not _copy_file(resource.file, copy.file):
        if not copy.url:
            return None  # a file material whose file is gone cannot be copied
    if copy.resource_type == R.RESOURCE_TEST and not copy.test_id:
        return None  # the SAT test was deleted
    if copy.resource_type == R.RESOURCE_VOCAB_QUIZ and not copy.vocabulary_unit_id:
        return None
    copy.save()
    return copy


def copy_units(target, lessons, *, user, insert_after=None, publish=False):
    """Copy ``lessons`` (in their order) into ``target``.

    ``insert_after`` is a unit order number in ``target`` (None = at the end).
    Returns ``(new_lessons, skipped_materials)``.
    """
    from .models import ClassroomLesson

    lessons = sorted(lessons, key=lambda lesson: (lesson.order, lesson.pk))
    if not lessons:
        return [], 0
    created, skipped = [], 0
    with transaction.atomic():
        existing = ClassroomLesson.objects.select_for_update().filter(classroom=target)
        last = existing.aggregate(value=Max("order"))["value"] or 0
        if insert_after is None or insert_after >= last:
            start = last + 1
        else:
            start = max(1, insert_after + 1)
            # Make room: highest first, so (classroom, order) stays unique at every step.
            for row in existing.filter(order__gte=start).order_by("-order"):
                row.order += len(lessons)
                row.save(update_fields=["order"])
        for offset, source in enumerate(lessons):
            new = ClassroomLesson.objects.create(
                classroom=target,
                title=source.title,
                summary=source.summary,
                order=start + offset,
                is_published=publish,
                created_by=user,
                copied_from=source,
                copied_from_label=source_label(source.classroom)[:300],
            )
            for resource in source.resources.all().order_by("order", "created_at"):
                if _copy_resource(resource, new) is None:
                    skipped += 1
            created.append(new)
    return created, skipped


def copy_homework(target, assignments, *, user):
    """Copy homework as hidden drafts without a deadline; the teacher sets dates later."""
    from .models import ClassroomHomeworkAssignment

    created = []
    for source in assignments:
        copy = ClassroomHomeworkAssignment(
            classroom=target,
            created_by=user,
            title=source.title,
            instructions=source.instructions,
            assignment_type=source.assignment_type,
            test_id=source.test_id,
            required_test_mode=source.required_test_mode,
            required_integrity_mode=source.required_integrity_mode,
            vocabulary_unit_id=source.vocabulary_unit_id,
            vocabulary_mode=source.vocabulary_mode,
            vocabulary_quiz_mode=source.vocabulary_quiz_mode,
            question_count=source.question_count,
            attachment_name=source.attachment_name,
            assign_all=True,
            due_at=None,
            is_active=False,
        )
        if source.attachment and not _copy_file(source.attachment, copy.attachment):
            continue
        if source.assignment_type == ClassroomHomeworkAssignment.TYPE_TEST and not copy.test_id:
            continue
        if source.assignment_type in {ClassroomHomeworkAssignment.TYPE_VOCAB, ClassroomHomeworkAssignment.TYPE_VOCAB_QUIZ} and not copy.vocabulary_unit_id:
            continue
        copy.save()
        created.append(copy)
    return created
