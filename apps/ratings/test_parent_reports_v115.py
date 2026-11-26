"""V115: weekly report to parents in the MakonBook parents' Telegram bot."""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.base.models import UserProfile
from apps.integrations.models import HollihopAttendance
from apps.ratings import parent_reports as reports
from apps.ratings.models import (
    LessonHomeworkCheck, LessonHomeworkMiss, ParentTelegramLink, ParentTelegramSubscriber, ParentWeeklyReport,
    RatingAssessment, RatingProfile,
)
from apps.sat.models import Classroom, ClassroomMembership, StudentMistake, Test, TestReview
from apps.telegram_bot import parent_bot as bot

MONDAY = date(2026, 11, 23)
SUNDAY = MONDAY + timedelta(days=6)


class ParentBotBase(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("v115_teacher", password="x", first_name="Dilnoza", last_name="T")
        self.classroom = Classroom.objects.create(teacher=self.teacher, name="SAT Evening")
        self.aziz = self.student("v115_aziz", "Aziz", "+998 90 123 45 67")
        self.malika = self.student("v115_malika", "Malika", "8 90 123 45 67")       # same family number, other form
        self.other = self.student("v115_other", "Other", "+998 93 000 00 00")

    def student(self, username, first, phone, *, in_class=True):
        user = User.objects.create_user(username, password="x", first_name=first, last_name="Karimov")
        UserProfile.objects.filter(user=user).update(phone_number=phone)
        if in_class:
            ClassroomMembership.objects.create(classroom=self.classroom, user=user, role="student", status="approved")
        return user

    def subscribe(self, chat_id=501, lang="ru", phone="998901234567"):
        bot.on_start(chat_id, chat_id + 1000, "Mother", "mom")
        bot.on_language(chat_id, lang)
        return bot.on_contact(chat_id, chat_id + 1000, chat_id + 1000, phone)


class SubscribeTests(ParentBotBase):
    def test_own_contact_links_every_child_with_that_number(self):
        reply = self.subscribe()
        self.assertEqual(reply.keyboard, "main")
        self.assertIn("Aziz Karimov", reply.text)
        self.assertIn("Malika Karimov", reply.text)
        sub = ParentTelegramSubscriber.objects.get(chat_id=501)
        self.assertEqual(sub.phone, "+998901234567")
        self.assertEqual({s.pk for s in reports.linked_students(sub)}, {self.aziz.pk, self.malika.pk})

    def test_someone_elses_contact_is_not_accepted(self):
        bot.on_start(502, 1502)
        bot.on_language(502, "uz")
        reply = bot.on_contact(502, 1502, 9999, "998901234567")
        self.assertEqual(reply.keyboard, "contact")
        self.assertIn("o'z raqamingizni", reply.text)
        self.assertFalse(ParentTelegramLink.objects.exists())

    def test_students_not_in_an_active_class_are_not_found(self):
        Classroom.objects.filter(pk=self.classroom.pk).update(is_active=False)
        reply = self.subscribe()
        self.assertEqual(reply.keyboard, "contact")
        self.assertIn("учеников не нашлось", reply.text)

    def test_family_code_adds_a_child_and_attempts_are_limited(self):
        self.subscribe(phone="998977777777")
        code = RatingProfile.objects.get_or_create(user=self.other)[0].parent_access_code
        replies = bot.on_text(501, code.lower())
        self.assertIn("Добавлен(а): Other Karimov", replies[0].text)
        self.assertEqual(ParentTelegramLink.objects.get().via, ParentTelegramLink.VIA_CODE)
        for _ in range(4):
            self.assertIn("Код не подошёл", bot.on_text(501, "AAAAAAAAAAAA")[0].text)
        self.assertIn("Слишком много попыток", bot.on_text(501, code)[0].text)

    def test_children_unlink_and_stop(self):
        self.subscribe()
        reply = bot.on_text(501, "👨‍👩‍👧 Мои дети")[0]
        self.assertEqual(len(reply.inline), 2)
        reply = bot.on_unlink(501, self.aziz.pk)
        self.assertIn("Убрано: Aziz Karimov", reply.text)
        self.assertEqual([s.pk for s in reports.linked_students(ParentTelegramSubscriber.objects.get())], [self.malika.pk])
        with override_settings(TELEGRAM_PARENT_BOT_TOKEN="t"), mock.patch.object(reports, "send_message") as send:
            reports.send_weekly_reports(SUNDAY, pause=0)  # the phone does not bring Aziz back
        self.assertEqual(send.call_count, 1)
        code = RatingProfile.objects.get_or_create(user=self.aziz)[0].parent_access_code
        self.assertIn("Добавлен(а): Aziz Karimov", bot.on_text(501, code)[0].text)  # the code does
        self.assertEqual(len(reports.linked_students(ParentTelegramSubscriber.objects.get())), 2)
        self.assertIn("Отчёты отключены", bot.on_stop(501).text)
        self.assertFalse(ParentTelegramSubscriber.objects.get().is_active)
        bot.on_start(501, 1501)
        self.assertTrue(ParentTelegramSubscriber.objects.get().is_active)


class ReportTextTests(ParentBotBase):
    def week_data(self):
        for n, (day, status) in enumerate([(MONDAY, "present"), (MONDAY + timedelta(days=2), "absent"), (MONDAY + timedelta(days=4), "present")]):
            HollihopAttendance.objects.create(student=self.aziz, classroom=self.classroom, date=day, status=status, external_key=f"v115-{n}")
        HollihopAttendance.objects.create(student=self.aziz, classroom=self.classroom, date=MONDAY - timedelta(days=1),
                                          status="absent", external_key="v115-last-week")
        check = LessonHomeworkCheck.objects.create(classroom=self.classroom, teacher=self.teacher, lesson_date=MONDAY)
        LessonHomeworkCheck.objects.create(classroom=self.classroom, teacher=self.teacher, lesson_date=MONDAY + timedelta(days=4))
        LessonHomeworkMiss.objects.create(homework_check=check, student=self.aziz)
        for day, score, comment in ((MONDAY, 8, "Хорошо работал <на уроке>"), (MONDAY + timedelta(days=4), 9, "")):
            RatingAssessment.objects.create(classroom=self.classroom, student=self.aziz, teacher=self.teacher, lesson_date=day,
                                            homework=score, progress=score, activity=score, attendance=score, behavior=score,
                                            comment=comment)
        test = Test.objects.create(name="DAY12", is_available=True)
        when = timezone.make_aware(timezone.datetime(2026, 11, 25, 15, 0))
        for score in (1180, 1090):
            review = TestReview.objects.create(test=test, user=self.aziz, key=f"v115-{uuid.uuid4()}", attempt_id=uuid.uuid4(), score=score)
            TestReview.objects.filter(pk=review.pk).update(created_at=when)
        StudentMistake.objects.create(user=self.aziz, section="math", question_id=1, status="fixed", fixed_at=when)
        StudentMistake.objects.create(user=self.aziz, section="math", question_id=2, status="open")

    def test_russian_report(self):
        self.week_data()
        text = reports.report_text(self.aziz, MONDAY, SUNDAY, "ru")
        self.assertIn("<b>Aziz Karimov</b> · 23.11–29.11", text)
        self.assertIn("Посещаемость: 2 из 3 уроков (пропустил(а): ср 25.11)", text)
        self.assertIn("Домашние задания: сделано 1 из 2 (не сделано: пн 23.11)", text)
        self.assertIn("Оценки учителя: в среднем 8.5 / 10 (2 ур.)", text)
        self.assertIn("«Хорошо работал &lt;на уроке&gt;» — Dilnoza T", text)
        self.assertIn("Пробные тесты: 2 · лучший результат 1180 (DAY12)", text)
        self.assertIn("Исправлено ошибок: 1 · осталось исправить: 1", text)
        self.assertIn("/rating/parent/?lang=ru", text)

    def test_uzbek_report_and_an_empty_week(self):
        self.week_data()
        text = reports.report_text(self.aziz, MONDAY, SUNDAY, "uz")
        self.assertIn("Davomat: 3 ta darsdan 2 tasida qatnashdi (qoldirgan: Ch 25.11)", text)
        self.assertIn("Uy vazifalari: 2 tadan 1 tasi bajarildi", text)
        self.assertIn("Uy vazifalari: 2 tadan 2 tasi bajarildi", reports.report_text(self.malika, MONDAY, SUNDAY, "uz"))
        loner = self.student("v115_loner", "Loner", "+998 99 111 22 33", in_class=False)
        empty = reports.report_text(loner, MONDAY, SUNDAY, "uz")
        self.assertIn("Bu hafta darslar, baholar va testlar bo'lmadi.", empty)


@override_settings(TELEGRAM_PARENT_BOT_TOKEN="test-token")
class SendingTests(ParentBotBase):
    def test_each_child_once_a_week_and_new_children_are_picked_up(self):
        self.subscribe()
        with mock.patch.object(reports, "send_message") as send:
            stats = reports.send_weekly_reports(SUNDAY, pause=0)
            self.assertEqual(stats["sent"], 2)
            self.assertEqual(send.call_count, 2)
            self.assertEqual(reports.send_weekly_reports(SUNDAY, pause=0)["sent"], 0)   # the 19:30 run
            self.assertEqual(send.call_count, 2)
            late = self.student("v115_late", "Late", "+998901234567")                  # added in Hollihop later
            stats = reports.send_weekly_reports(SUNDAY, pause=0)
            self.assertEqual((stats["linked"], stats["sent"]), (1, 1))
        self.assertTrue(ParentWeeklyReport.objects.filter(student=late, status="sent").exists())

    def test_failures_are_retried_three_times_at_most(self):
        self.subscribe()
        ParentTelegramLink.objects.filter(student=self.malika).delete()
        ParentTelegramSubscriber.objects.update(phone="")  # do not relink by phone
        with mock.patch.object(reports, "send_message", side_effect=RuntimeError("Telegram answered 500")):
            for _ in range(4):
                reports.send_weekly_reports(SUNDAY, pause=0)
        row = ParentWeeklyReport.objects.get()
        self.assertEqual((row.status, row.attempts, row.error), ("failed", 3, "Telegram answered 500"))

    def test_blocked_bot_turns_the_subscriber_off(self):
        self.subscribe()
        with mock.patch.object(reports, "send_message", side_effect=reports.TelegramBlocked()):
            stats = reports.send_weekly_reports(SUNDAY, pause=0)
        self.assertEqual(stats["blocked"], 1)
        self.assertFalse(ParentTelegramSubscriber.objects.get().is_active)

    @override_settings(TELEGRAM_PARENT_BOT_TOKEN="")
    def test_nothing_without_a_token(self):
        self.subscribe()
        self.assertTrue(reports.send_weekly_reports(SUNDAY)["disabled"])
        self.assertFalse(ParentWeeklyReport.objects.exists())

    def test_report_button_sends_this_week_so_far(self):
        self.subscribe()
        replies = bot.on_text(501, "📊 Отчёт за эту неделю")
        self.assertEqual(len(replies), 2)
        self.assertTrue(all(r.is_html for r in replies))
        self.assertFalse(ParentWeeklyReport.objects.exists())  # not counted as the Sunday report

    def test_sunday_evening_schedule(self):
        entry = settings.CELERY_BEAT_SCHEDULE["makon-parent-weekly-reports"]
        self.assertEqual(entry["task"], "apps.ratings.tasks.send_parent_weekly_reports")
        self.assertEqual(entry["schedule"].day_of_week, {0})
        self.assertEqual(min(entry["schedule"].hour), 19)


class PagesTests(ParentBotBase):
    def test_manager_page(self):
        manager = User.objects.create_user("v115_manager", password="x")
        manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.subscribe()
        self.client.force_login(manager)
        with override_settings(TELEGRAM_PARENT_BOT_TOKEN="", TELEGRAM_PARENT_BOT_USERNAME=""):
            page = self.client.get(reverse("manager_parent_reports_root"))
        self.assertContains(page, "The parents' bot is not set up yet")
        self.assertContains(page, "2 / 3")  # Aziz and Malika of three students
        with override_settings(TELEGRAM_PARENT_BOT_TOKEN="t", TELEGRAM_PARENT_BOT_USERNAME="MakonBookParentsBot"):
            page = self.client.get(reverse("manager_parent_reports_root"))
        self.assertContains(page, "https://t.me/MakonBookParentsBot")
        self.assertContains(page, 'data-nav-key="parent-reports"')

        self.client.force_login(self.aziz)
        self.assertEqual(self.client.get(reverse("manager_parent_reports_root")).status_code, 403)

    @override_settings(TELEGRAM_PARENT_BOT_USERNAME="MakonBookParentsBot")
    def test_parent_portal_links_the_bot(self):
        page = self.client.get(reverse("rating_parent_lookup") + "?lang=uz")
        self.assertContains(page, "https://t.me/MakonBookParentsBot")
        self.assertContains(page, "Haftalik hisobotni Telegram")
