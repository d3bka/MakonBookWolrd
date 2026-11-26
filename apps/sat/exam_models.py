"""V117: Mid-term and Final exams (paper first, the MakonBook desktop app later).

TermExam (Mid-term / Final, academic year, classes)
  └ ExamSession (one subject, one test variant, date and time, room; main or retake)
      └ ExamSeat (one student: answers, score, the teacher's check status)
          ├ ExamAnswerChange (who changed which answer or status, when, from what to what)
          └ ExamAppeal (a re-check request within 3 days of publication)

Agreed rules (owner, 22.11 and 26.11.2026):
* Math and English are separate sessions, often on different days; an exam can have one subject.
* The main group is published at once; a retake uses a different test variant and is published
  separately.
* The main score is the percentage; the SAT score next to it is approximate.
* Mid/Final grades are stored per subject (TermGrade.subject).
* Students never get the exam questions: only the score and the right/wrong/skipped grid.
"""
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

SUBJECT_ENGLISH = "english"
SUBJECT_MATH = "math"
SUBJECT_CHOICES = [(SUBJECT_ENGLISH, "Reading and Writing"), (SUBJECT_MATH, "Math")]


def current_academic_year(day=None):
    day = day or timezone.localdate()
    start = day.year if day.month >= 8 else day.year - 1
    return f"{start}/{start + 1}"


class TermExam(models.Model):
    KIND_MIDTERM = "midterm"
    KIND_FINAL = "final"
    KIND_CHOICES = [(KIND_MIDTERM, "Mid-term"), (KIND_FINAL, "Final")]

    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    academic_year = models.CharField(max_length=16, default=current_academic_year, help_text="E.g. 2026/2027")
    title = models.CharField(max_length=160, blank=True, help_text="Optional; by default “Mid-term 2026/2027”.")
    classrooms = models.ManyToManyField("sat.Classroom", related_name="term_exams")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def display_title(self):
        return self.title or f"{self.get_kind_display()} {self.academic_year}"

    def __str__(self):
        return self.display_title


class ExamSession(models.Model):
    exam = models.ForeignKey(TermExam, on_delete=models.CASCADE, related_name="sessions")
    subject = models.CharField(max_length=10, choices=SUBJECT_CHOICES)
    test = models.ForeignKey("sat.Test", on_delete=models.PROTECT, related_name="exam_sessions",
                             help_text="The exam variant (a test of type Exam).")
    is_retake = models.BooleanField(default=False)
    starts_at = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField(default=70)
    room = models.CharField(max_length=120, blank=True)
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="exam_sessions",
                                help_text="Responsible teacher in the room.")
    publish_at = models.DateTimeField(null=True, blank=True, help_text="Scheduled publication of the results.")
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["starts_at", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["exam", "subject"], condition=models.Q(is_retake=False),
                                    name="exam_one_main_session_per_subject"),
        ]

    @property
    def ends_at(self):
        return self.starts_at + timezone.timedelta(minutes=self.duration_minutes)

    @property
    def is_published(self):
        return self.published_at is not None

    def __str__(self):
        return f"{self.exam} · {self.get_subject_display()}{' (retake)' if self.is_retake else ''}"


class ExamSeat(models.Model):
    STATUS_PENDING = "pending"
    STATUS_CHECKED = "checked"
    STATUS_ABSENT = "absent"
    STATUS_LATE = "late"
    STATUS_ANNULLED = "annulled"
    STATUS_MOVED = "moved"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Not checked yet"),
        (STATUS_CHECKED, "Checked"),
        (STATUS_ABSENT, "Absent (retake)"),
        (STATUS_LATE, "Late (retake)"),
        (STATUS_ANNULLED, "Annulled"),
        (STATUS_MOVED, "Moved to a retake"),
    ]

    session = models.ForeignKey(ExamSession, on_delete=models.CASCADE, related_name="seats")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="exam_seats")
    classroom = models.ForeignKey("sat.Classroom", on_delete=models.CASCADE, related_name="exam_seats")
    answers = models.JSONField(default=dict, blank=True, help_text='{"1": "A", "2": "", ...} by question number.')
    correct = models.PositiveSmallIntegerField(null=True, blank=True)
    total = models.PositiveSmallIntegerField(null=True, blank=True)
    percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    sat_score = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    status_reason = models.CharField(max_length=300, blank=True)
    entered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    entered_at = models.DateTimeField(null=True, blank=True)
    checked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["student__first_name", "student__last_name", "student__username"]
        constraints = [models.UniqueConstraint(fields=["session", "student"], name="exam_one_seat_per_session")]

    def __str__(self):
        return f"{self.student} · {self.session}"


class ExamAnswerChange(models.Model):
    seat = models.ForeignKey(ExamSeat, on_delete=models.CASCADE, related_name="changes")
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="+")
    changed_at = models.DateTimeField(auto_now_add=True)
    field = models.CharField(max_length=20, help_text="A question number, or “status”.")
    old_value = models.CharField(max_length=300, blank=True)
    new_value = models.CharField(max_length=300, blank=True)
    reason = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-changed_at", "-pk"]


class ExamAppeal(models.Model):
    STATUS_OPEN = "open"
    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [(STATUS_OPEN, "Waiting"), (STATUS_ACCEPTED, "Score changed"), (STATUS_REJECTED, "Score kept")]

    seat = models.ForeignKey(ExamSeat, on_delete=models.CASCADE, related_name="appeals")
    reason = models.TextField(max_length=1000)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)
    response = models.TextField(max_length=1000, blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
