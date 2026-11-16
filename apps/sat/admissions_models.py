"""V80: Universities catalogue and the Admissions course (lessons, steps, videos, resources)."""
from django.contrib.auth.models import User
from django.db import models
from django.utils.text import slugify


class University(models.Model):
    """One university in the catalogue. Figures are public data for the year in `data_year`."""

    REGION_CHOICES = [
        ("north_america", "North America"),
        ("europe", "UK & Europe"),
        ("asia", "Asia"),
        ("middle_east", "Middle East"),
        ("oceania", "Oceania"),
    ]
    TYPE_CHOICES = [("public", "Public"), ("private", "Private")]
    TEST_POLICY_CHOICES = [
        ("required", "SAT required"),
        ("optional", "Test optional"),
        ("recommended", "SAT recommended"),
        ("accepted", "SAT accepted"),
        ("blind", "Test blind"),
    ]
    SAT_KIND_CHOICES = [("middle50", "Middle 50% of admitted"), ("minimum", "Typical minimum"), ("none", "Not used")]
    AID_CHOICES = [
        ("need_blind", "Need-blind, full need"),
        ("need_aware", "Need-based aid"),
        ("merit", "Merit scholarships"),
        ("limited", "Limited aid"),
        ("none", "No aid for internationals"),
    ]
    PLATFORM_CHOICES = [
        ("common_app", "Common App"),
        ("ucas", "UCAS"),
        ("direct", "University portal"),
        ("ouac", "OUAC"),
        ("coalition", "Coalition / own"),
        ("other", "Other"),
    ]
    RANK_CHOICES = [
        ("top10", "Top 10"), ("top50", "Top 50"), ("top100", "Top 100"),
        ("top200", "Top 200"), ("top500", "Top 500"), ("other", "500+"),
    ]

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    country = models.CharField(max_length=80, db_index=True)
    city = models.CharField(max_length=120, blank=True)
    region = models.CharField(max_length=20, choices=REGION_CHOICES, db_index=True)
    kind = models.CharField("type", max_length=10, choices=TYPE_CHOICES, default="private")
    rank_band = models.CharField(max_length=10, choices=RANK_CHOICES, default="other",
                                 help_text="World ranking band (QS World University Rankings).")
    acceptance_rate = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True,
                                          help_text="Overall acceptance rate, %.")
    sat_low = models.PositiveSmallIntegerField(null=True, blank=True)
    sat_high = models.PositiveSmallIntegerField(null=True, blank=True)
    sat_kind = models.CharField(max_length=10, choices=SAT_KIND_CHOICES, default="middle50")
    test_policy = models.CharField(max_length=12, choices=TEST_POLICY_CHOICES, default="optional")
    ielts_min = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True)
    toefl_min = models.PositiveSmallIntegerField(null=True, blank=True)
    tuition_usd = models.PositiveIntegerField(null=True, blank=True,
                                              help_text="International undergraduate tuition per year, USD.")
    aid = models.CharField(max_length=12, choices=AID_CHOICES, default="limited")
    platform = models.CharField(max_length=12, choices=PLATFORM_CHOICES, default="direct")
    deadlines = models.CharField(max_length=160, blank=True, help_text='For example "ED Nov 1 · RD Jan 1".')
    notes = models.TextField(blank=True)
    website = models.URLField(max_length=300, blank=True)
    data_year = models.CharField(max_length=20, default="2024–25")
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "universities"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:220]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.country})"


class AdmissionsLesson(models.Model):
    """A step-by-step Admissions lesson with an optional SATMakon YouTube video."""

    MODULE_CHOICES = [
        ("start", "Start here"),
        ("choose", "Choosing universities"),
        ("tests", "Tests"),
        ("profile", "Your profile"),
        ("essays", "Essays & letters"),
        ("apply", "Applying"),
        ("money", "Money"),
        ("after", "After you apply"),
    ]

    order = models.PositiveSmallIntegerField(default=1, db_index=True)
    slug = models.SlugField(max_length=120, unique=True)
    module = models.CharField(max_length=10, choices=MODULE_CHOICES, default="start")
    title = models.CharField(max_length=160)
    summary = models.CharField(max_length=300)
    minutes = models.PositiveSmallIntegerField(default=8)
    youtube_url = models.URLField(max_length=300, blank=True,
                                  help_text="SATMakon YouTube video for this lesson (watch, youtu.be or embed link).")
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.order}. {self.title}"

    @property
    def youtube_embed_url(self):
        """https://www.youtube-nocookie.com/embed/<id> for any common YouTube link, '' otherwise."""
        import re

        match = re.search(r"(?:youtu\.be/|v=|/embed/|/shorts/|/live/)([A-Za-z0-9_-]{11})", self.youtube_url or "")
        return f"https://www.youtube-nocookie.com/embed/{match.group(1)}" if match else ""


class AdmissionsStep(models.Model):
    lesson = models.ForeignKey(AdmissionsLesson, on_delete=models.CASCADE, related_name="steps")
    order = models.PositiveSmallIntegerField(default=1)
    title = models.CharField(max_length=160)
    body = models.TextField(help_text="Plain text. Lines starting with '- ' become a list.")

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.lesson_id}.{self.order} {self.title}"


class AdmissionsResource(models.Model):
    KIND_CHOICES = [
        ("official", "Official site"),
        ("tool", "Tool"),
        ("guide", "Guide"),
        ("video", "Video"),
        ("template", "Template"),
    ]

    lesson = models.ForeignKey(AdmissionsLesson, on_delete=models.CASCADE, related_name="resources")
    order = models.PositiveSmallIntegerField(default=1)
    title = models.CharField(max_length=160)
    url = models.URLField(max_length=400)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default="official")
    note = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class AdmissionsLessonProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    lesson = models.ForeignKey(AdmissionsLesson, on_delete=models.CASCADE, related_name="+")
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "lesson"], name="uniq_admissions_progress")]
