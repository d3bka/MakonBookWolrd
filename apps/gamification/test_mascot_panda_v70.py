"""V70 Mako the panda: where he appears and what he wears."""
from datetime import date

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.base.seasons import set_season_mode
from apps.sat.models import Classroom, ClassroomMembership, DreamUniversity, OfficialSatDate, StudentGoalProfile

EMOTION_PARTS = ("pd-lid-l", "pd-lid-r", "pd-pupil", "pd-brow-l", "pd-m-open", "pd-m-frown", "pd-m-o",
                 "pd-m-smirk", "pd-m-flat", "pd-m-wobble", "pd-fx-zzz", "pd-fx-anger", "pd-fx-tear")


class MascotPandaTests(TestCase):
    def setUp(self):
        cache.clear()
        teacher = User.objects.create_user("panda_teacher", password="x", first_name="T", last_name="One")
        teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        self.student = User.objects.create_user("panda_student", password="x", first_name="Aziz", last_name="K")
        classroom = Classroom.objects.create(teacher=teacher, name="Panda class", is_active=True)
        ClassroomMembership.objects.create(classroom=classroom, user=self.student, role="student",
                                           status="approved", approved_at=timezone.now())
        exam = OfficialSatDate.objects.filter(date__gte=date.today()).order_by("date").first()
        StudentGoalProfile.objects.create(user=self.student, dream_university=DreamUniversity.objects.filter(is_active=True).first(),
                                          target_sat_score=1450, exam_date=exam.date if exam else None)
        self.client.force_login(self.student)

    def test_corner_companion_on_student_pages(self):
        page = self.client.get(reverse("settings_page"))
        self.assertContains(page, "data-mako-companion")
        self.assertContains(page, 'data-name="Aziz"')
        self.assertContains(page, "assets/css/mascot-v70.css")
        self.assertContains(page, "assets/js/mascot-v70.js")
        for part in EMOTION_PARTS:
            self.assertContains(page, part)
        # template comments must never leak into the page
        self.assertNotContains(page, "#}")
        self.assertNotContains(page, "{% comment")

    def test_home_greets_from_the_header_not_the_corner(self):
        page = self.client.get(reverse("student_dashboard_root"))
        self.assertContains(page, "mk70-greet-row")
        self.assertContains(page, 'id="pdBodyh"')
        self.assertNotContains(page, "data-mako-companion")
        self.assertNotContains(page, "mk70-diorama")
        self.assertNotContains(page, "#}")

    def test_accessory_follows_the_season(self):
        for season in ("spring", "summer", "autumn", "winter"):
            set_season_mode(season)
            with self.subTest(season=season):
                page = self.client.get(reverse("settings_page"))
                self.assertContains(page, f"pd-acc-{season}")

    def test_staff_do_not_get_the_student_companion(self):
        manager = User.objects.create_user("panda_manager", password="x", first_name="M", last_name="One")
        manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.client.force_login(manager)
        page = self.client.get(reverse("manager_dashboard_root"))
        self.assertNotContains(page, "data-mako-companion")
