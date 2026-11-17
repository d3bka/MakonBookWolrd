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
        ("profile", "Your profile & activities"),
        ("essays", "Essays"),
        ("money", "Scholarships & financial aid"),
        ("apply", "Documents & letters"),
        ("countries", "Other countries"),
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


class AdmissionsVideo(models.Model):
    """V81: a premium SATMakon lesson video, stored as AES-128 encrypted HLS in the private
    premium folder (settings.MAKONBOOK_PREMIUM_ROOT), never in /media or R2.

    Created by `manage.py import_admissions_media` on the server or, since V86, by
    `manage.py upload_admissions_media` on the uploader's PC, which sends the key to the
    site's media API. The key is never served except through the access-checked key endpoint.
    """

    STORAGE_LOCAL = "local"
    STORAGE_R2 = "r2"
    STORAGE_CHOICES = [(STORAGE_LOCAL, "Server private volume"), (STORAGE_R2, "Private R2 bucket")]

    lesson = models.OneToOneField(AdmissionsLesson, on_delete=models.CASCADE, related_name="premium_video")
    asset = models.CharField(max_length=40, unique=True, editable=False)
    key_hex = models.CharField(max_length=32, editable=False)
    # V82: where the encrypted segments live. The playlist text is kept here, so the
    # player never needs a playlist file from storage.
    storage = models.CharField(max_length=8, choices=STORAGE_CHOICES, default=STORAGE_LOCAL, editable=False)
    playlist_text = models.TextField(blank=True, editable=False)
    duration_seconds = models.PositiveIntegerField(default=0)
    segment_count = models.PositiveIntegerField(default=0)
    source_name = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Admissions video (premium)"
        verbose_name_plural = "Admissions videos (premium)"

    def __str__(self):
        return f"Video for {self.lesson}"


class AdmissionsDocument(models.Model):
    """V81: a premium SATMakon PDF. Only page images exist on the server; every page is
    stamped with the viewer's watermark when it is served. The PDF itself is never served."""

    slug = models.SlugField(max_length=120, unique=True)
    title = models.CharField(max_length=200)
    description = models.CharField(max_length=300, blank=True)
    order = models.PositiveSmallIntegerField(default=1)
    source_name = models.CharField(max_length=200, blank=True,
                                   help_text="File name in the Lessons folder used by the import command.")
    asset = models.CharField(max_length=40, blank=True, editable=False)
    page_count = models.PositiveSmallIntegerField(default=0, editable=False)
    # V86: page images may live in the private R2 bucket (uploaded from a PC).
    storage = models.CharField(max_length=8, choices=AdmissionsVideo.STORAGE_CHOICES,
                               default=AdmissionsVideo.STORAGE_LOCAL, editable=False)
    lessons = models.ManyToManyField(AdmissionsLesson, related_name="documents", blank=True,
                                     help_text="Lessons that show this file. Students who can open one of "
                                               "these lessons can read it.")
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Admissions file (premium)"
        verbose_name_plural = "Admissions files (premium)"

    def __str__(self):
        return self.title

    @property
    def is_ready(self):
        return bool(self.asset and self.page_count)


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


class AdmissionsMediaSession(models.Model):
    """V82: a browser session that watched premium content. Only the newest
    MAKONBOOK_PREMIUM_MAX_DEVICES sessions per student may play videos or read files;
    opening premium content on another device switches off the oldest one."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    session_tag = models.CharField(max_length=32, db_index=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Admissions device session"
        verbose_name_plural = "Admissions device sessions"
        constraints = [models.UniqueConstraint(fields=["user", "session_tag"], name="uniq_admissions_media_session")]

    def __str__(self):
        return f"{self.user} · {self.session_tag[:6]}"


class AdmissionsKeyLog(models.Model):
    """V82: every time a decryption key was handed out (or refused by a limit)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    video = models.ForeignKey(AdmissionsVideo, on_delete=models.CASCADE, related_name="+")
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    session_tag = models.CharField(max_length=32, blank=True)
    allowed = models.BooleanField(default=True)
    note = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Admissions key log"
        verbose_name_plural = "Admissions key log"
