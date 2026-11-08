from __future__ import annotations

import secrets
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.sat.models import Classroom


class RatingConfig(models.Model):
    alpha = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        default=Decimal("0.400"),
        validators=[MinValueValidator(Decimal("0.001")), MaxValueValidator(Decimal("1.000"))],
        help_text="Weight of the newest assessment in the monthly EWMA rating.",
    )
    min_assessments_per_classroom = models.PositiveSmallIntegerField(
        default=2,
        help_text="A classroom stream qualifies after this many assessments in the month.",
    )
    min_qualifying_classrooms = models.PositiveSmallIntegerField(
        default=2,
        help_text="Minimum qualifying classroom streams required for the public board.",
    )
    teacher_edit_window_days = models.PositiveSmallIntegerField(default=7)
    top_n = models.PositiveSmallIntegerField(default=30)
    public_board_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Rating configuration"
        verbose_name_plural = "Rating configuration"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return None

    def __str__(self):
        return "Rating configuration"


class RatingProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="rating_profile")
    public_visible = models.BooleanField(default=True)
    parent_access_code = models.CharField(max_length=16, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.parent_access_code:
            while True:
                code = secrets.token_hex(6).upper()
                if not RatingProfile.objects.filter(parent_access_code=code).exists():
                    self.parent_access_code = code
                    break
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Rating profile: {self.user.username}"


class RatingAssessment(models.Model):
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name="rating_assessments")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="rating_assessments_received")
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="rating_assessments_given")

    homework = models.DecimalField(max_digits=3, decimal_places=1, validators=[MinValueValidator(0), MaxValueValidator(10)])
    progress = models.DecimalField(max_digits=3, decimal_places=1, validators=[MinValueValidator(0), MaxValueValidator(10)])
    activity = models.DecimalField(max_digits=3, decimal_places=1, validators=[MinValueValidator(0), MaxValueValidator(10)])
    attendance = models.DecimalField(max_digits=3, decimal_places=1, validators=[MinValueValidator(0), MaxValueValidator(10)])
    behavior = models.DecimalField(max_digits=3, decimal_places=1, validators=[MinValueValidator(0), MaxValueValidator(10)])
    comment = models.CharField(max_length=500, blank=True)
    assessed_at = models.DateTimeField(default=timezone.now, db_index=True)
    lesson_date = models.DateField(null=True, blank=True, db_index=True, help_text="Lesson date for V61 teacher assessments; legacy history stays NULL.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-assessed_at", "-id"]
        constraints = [models.UniqueConstraint(fields=['classroom', 'teacher', 'student', 'lesson_date'], condition=models.Q(lesson_date__isnull=False), name='rating_one_assessment_per_lesson')]
        indexes = [
            models.Index(fields=["student", "assessed_at"], name="rating_student_date"),
            models.Index(fields=["classroom", "assessed_at"], name="rating_class_date"),
            models.Index(fields=["teacher", "assessed_at"], name="rating_teacher_date"),
        ]

    @property
    def mean_score(self):
        values = [self.homework, self.progress, self.activity, self.attendance, self.behavior]
        return sum(values, Decimal("0")) / Decimal("5")

    def clean(self):
        from django.core.exceptions import ValidationError
        from apps.sat.models import ClassroomMembership

        if self.classroom_id and self.teacher_id:
            assigned = ClassroomMembership.objects.filter(
                classroom_id=self.classroom_id, user_id=self.teacher_id,
                role='teacher', status='approved',
            ).exists()
            if self.teacher_id != self.classroom.teacher_id and not assigned and not (self.teacher.is_staff or self.teacher.is_superuser):
                raise ValidationError("Only an assigned classroom teacher or administrator can assess this classroom.")
        if self.lesson_date and self.teacher_id and not (self.teacher.is_staff or self.teacher.is_superuser):
            from .assessment_policy import today_assessment_state
            schedule, allowed, _ = today_assessment_state(self.classroom, self.teacher)
            if not allowed or self.lesson_date != timezone.localdate():
                raise ValidationError('Assessments are accepted only on a scheduled lesson date, before local midnight.')
        if self.classroom_id and self.student_id:
            valid = ClassroomMembership.objects.filter(
                classroom_id=self.classroom_id,
                user_id=self.student_id,
                role="student",
                status="approved",
            ).exists()
            if not valid:
                raise ValidationError("The selected student is not an approved member of this classroom.")

    def __str__(self):
        return f"{self.student.username} - {self.classroom.name} - {self.assessed_at:%Y-%m-%d}"

class TermGrade(models.Model):
    """Official manually entered term result; do not infer it from SAT practice scores."""
    MIDTERM = 'midterm'
    FINAL = 'final'
    KIND_CHOICES = [(MIDTERM, 'Mid-term'), (FINAL, 'Final-term')]

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='term_grades')
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='term_grades')
    academic_year = models.CharField(max_length=16, help_text='E.g. 2026/2027')
    term = models.CharField(max_length=15, choices=KIND_CHOICES)
    score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    maximum_score = models.PositiveSmallIntegerField(default=100, validators=[MinValueValidator(1), MaxValueValidator(100)])
    awarded_at = models.DateField(default=timezone.localdate)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-awarded_at', 'classroom__name', 'term']
        constraints = [models.UniqueConstraint(fields=['student', 'classroom', 'academic_year', 'term'], name='rating_unique_term_grade')]

    @property
    def percentage(self):
        return round(self.score * 100 / self.maximum_score) if self.maximum_score else 0

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.score is not None and self.maximum_score is not None and self.score > self.maximum_score:
            raise ValidationError({'score': 'Score cannot exceed the maximum.'})

    def __str__(self):
        return f'{self.student} {self.classroom} {self.term}: {self.score}/{self.maximum_score}'


class AssessmentSchedule(models.Model):
    """Manager-approved recurring lesson days; not inferred from delayed attendance."""
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='assessment_schedules')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assessment_schedules')
    weekdays = models.JSONField(default=list, help_text='ISO weekdays (Monday=1 to Sunday=7).')
    starts_on = models.DateField(default=timezone.localdate)
    ends_on = models.DateField(null=True, blank=True)
    enabled = models.BooleanField(default=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_assessment_schedules')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['classroom', 'teacher'], name='rating_schedule_class_teacher')]

    def clean(self):
        from django.core.exceptions import ValidationError
        from apps.sat.models import ClassroomMembership
        if not isinstance(self.weekdays, list) or not self.weekdays or any(type(d) is not int or d not in range(1, 8) for d in self.weekdays):
            raise ValidationError({'weekdays': 'Select at least one valid weekday.'})
        if self.ends_on and self.starts_on and self.ends_on < self.starts_on:
            raise ValidationError({'ends_on': 'End cannot precede start.'})
        if self.classroom_id and self.teacher_id and self.classroom.teacher_id != self.teacher_id:
            if not ClassroomMembership.objects.filter(classroom_id=self.classroom_id, user_id=self.teacher_id, role='teacher', status='approved').exists():
                raise ValidationError({'teacher': 'Teacher must own or be assigned to this classroom.'})

    def __str__(self):
        return f'{self.classroom} / {self.teacher} {self.weekdays}'


class AssessmentCalendarException(models.Model):
    CANCELLED = 'cancelled'
    ADDED = 'added'
    ACTIONS = [(CANCELLED, 'Cancelled / holiday'), (ADDED, 'Extra lesson')]
    schedule = models.ForeignKey(AssessmentSchedule, on_delete=models.CASCADE, related_name='exceptions')
    date = models.DateField()
    action = models.CharField(max_length=12, choices=ACTIONS)
    reason = models.CharField(max_length=220, blank=True)
    changed_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['schedule', 'date'], name='rating_schedule_day_exception')]


class AssessmentObligation(models.Model):
    """Immutable daily snapshot, never generated retroactively."""
    schedule = models.ForeignKey(AssessmentSchedule, on_delete=models.PROTECT, related_name='obligations')
    student = models.ForeignKey(User, on_delete=models.PROTECT, related_name='assessment_obligations')
    lesson_date = models.DateField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['schedule', 'student', 'lesson_date'], name='rating_obligation_student_day')]
        indexes = [models.Index(fields=['lesson_date', 'schedule'], name='rating_oblig_due_sch')]


class AssessmentPenalty(models.Model):
    OPEN = 'open'
    WAIVED = 'waived'
    STATUS_CHOICES = [(OPEN, 'Pending manager review'), (WAIVED, 'Waived')]
    obligation = models.OneToOneField(AssessmentObligation, on_delete=models.PROTECT, related_name='penalty')
    amount_uzs = models.PositiveIntegerField(default=5000)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=500, blank=True)


class TeacherAssessmentReminder(models.Model):
    """Unique audit marker for the 21:00 Asia/Tashkent reminder."""
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assessment_reminders')
    date = models.DateField()
    pending_count = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['teacher', 'date'], name='rating_unique_teacher_reminder')]


class UserActivityDay(models.Model):
    """Daily unique authenticated MakonBook users; no IP or PII tracking."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='makon_activity_days')
    date = models.DateField(db_index=True)
    first_seen_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'date'], name='rating_unique_user_activity_day')]
        indexes = [models.Index(fields=['date', 'user'], name='rating_activity_date_user')]


class AssessmentDailyReport(models.Model):
    """One persisted dispatch marker per closed lesson date (deduplicated)."""
    date = models.DateField(unique=True)
    expected = models.PositiveIntegerField(default=0)
    completed = models.PositiveIntegerField(default=0)
    missed = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(default=timezone.now)
