"""V115: the weekly report for parents, sent by the MakonBook parents' Telegram bot.

* A parent subscribes in the bot by sharing their own Telegram contact. Every student whose
  phone (from Hollihop) is that number is linked. A parent whose number is not on file adds
  a child with the child's family access code (Settings → Family access code).
* Every Sunday at 19:00 (Asia/Tashkent) each parent gets one message per child about that
  week (Monday–Sunday): attendance, homework, the teacher's grades and comments, practice
  tests and mistakes fixed.
* A report row per parent, child and week makes sure nobody gets the same week twice;
  failed sends are retried by the next runs that evening (at most 3 attempts).
"""
from __future__ import annotations

import html
import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from .models import (
    LessonHomeworkCheck, LessonHomeworkMiss, ParentTelegramLink, ParentTelegramSubscriber, ParentWeeklyReport,
    RatingAssessment, RatingProfile,
)

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
STALE_SENDING = timedelta(minutes=30)
CODE_ATTEMPTS_PER_HOUR = 5
SEND_PAUSE_SECONDS = 0.05  # Telegram allows about 30 messages a second per bot

WEEKDAYS = {
    "ru": ["пн", "вт", "ср", "чт", "пт", "сб", "вс"],
    "uz": ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"],
}

TEXT = {
    "ru": {
        "title": "📘 <b>Отчёт MakonBook за неделю</b>",
        "week": "{start}–{end}",
        "attendance": "🏫 Посещаемость: {present} из {total} уроков",
        "absent_on": "пропустил(а): {days}",
        "homework": "📚 Домашние задания: сделано {done} из {total}",
        "homework_missed": "не сделано: {days}",
        "grades": "⭐ Оценки учителя: в среднем {mean} / 10 ({count} ур.)",
        "comment": "💬 «{comment}» — {teacher}",
        "tests": "📝 Пробные тесты: {count} · лучший результат {best} ({name})",
        "tests_none": "📝 Пробные тесты: на этой неделе не решал(а)",
        "mistakes": "✅ Исправлено ошибок: {fixed} · осталось исправить: {open}",
        "nothing": "На этой неделе уроков, оценок и тестов не было.",
        "more": "Подробнее: {link}",
        "so_far": "<i>Неделя ещё не закончилась: отчёт на сегодня.</i>",
    },
    "uz": {
        "title": "📘 <b>MakonBook haftalik hisoboti</b>",
        "week": "{start}–{end}",
        "attendance": "🏫 Davomat: {total} ta darsdan {present} tasida qatnashdi",
        "absent_on": "qoldirgan: {days}",
        "homework": "📚 Uy vazifalari: {total} tadan {done} tasi bajarildi",
        "homework_missed": "bajarilmagan: {days}",
        "grades": "⭐ O'qituvchi baholari: o'rtacha {mean} / 10 ({count} ta dars)",
        "comment": "💬 «{comment}» — {teacher}",
        "tests": "📝 Amaliy testlar: {count} ta · eng yaxshi natija {best} ({name})",
        "tests_none": "📝 Amaliy testlar: bu hafta yechilmadi",
        "mistakes": "✅ Tuzatilgan xatolar: {fixed} · tuzatish kerak: {open}",
        "nothing": "Bu hafta darslar, baholar va testlar bo'lmadi.",
        "more": "Batafsil: {link}",
        "so_far": "<i>Hafta hali tugamadi: bugungi holat bo'yicha hisobot.</i>",
    },
}


# ------------------------------------------------------------------ linking

def _normalize(phone):
    from apps.integrations.hollihop.normalization import normalize_phone

    return normalize_phone(phone)


def _student_qs():
    """Active students who are in at least one active class."""
    return User.objects.filter(
        is_active=True,
        classroom_memberships__role="student",
        classroom_memberships__status="approved",
        classroom_memberships__classroom__is_active=True,
    ).distinct()


def students_for_phone(phone):
    phone = _normalize(phone)
    if not phone:
        return []
    candidates = _student_qs().filter(
        profile__phone_number__isnull=False, profile__phone_number__endswith=phone[-2:],
    ).select_related("profile")
    found = [u for u in candidates if _normalize(u.profile.phone_number) == phone]
    return sorted(found, key=lambda u: (u.get_full_name() or u.username).casefold())


def link_by_phone(subscriber):
    """Link every student whose phone is the parent's number. Returns the new links' students."""
    added = []
    for student in students_for_phone(subscriber.phone):
        _, created = ParentTelegramLink.objects.get_or_create(
            subscriber=subscriber, student=student, defaults={"via": ParentTelegramLink.VIA_PHONE},
        )
        if created:
            added.append(student)
    return added


def code_attempts_left(subscriber, now=None):
    now = now or timezone.now()
    if not subscriber.code_attempts_since or now - subscriber.code_attempts_since > timedelta(hours=1):
        return CODE_ATTEMPTS_PER_HOUR
    return max(0, CODE_ATTEMPTS_PER_HOUR - subscriber.code_attempts)


def link_by_code(subscriber, code, now=None):
    """Returns (student or None, error) where error is "", "limit" or "not_found"."""
    now = now or timezone.now()
    if code_attempts_left(subscriber, now) <= 0:
        return None, "limit"
    if not subscriber.code_attempts_since or now - subscriber.code_attempts_since > timedelta(hours=1):
        subscriber.code_attempts, subscriber.code_attempts_since = 0, now
    subscriber.code_attempts += 1
    subscriber.save(update_fields=["code_attempts", "code_attempts_since", "updated_at"])
    code = "".join(ch for ch in str(code or "").upper() if ch.isalnum())[:32]
    profile = RatingProfile.objects.filter(parent_access_code=code, user__is_active=True).select_related("user").first() if code else None
    if profile is None:
        return None, "not_found"
    link, created = ParentTelegramLink.objects.get_or_create(
        subscriber=subscriber, student=profile.user, defaults={"via": ParentTelegramLink.VIA_CODE},
    )
    if not created and link.is_muted:  # the parent asked for this child again
        link.is_muted = False
        link.save(update_fields=["is_muted"])
    return profile.user, ""


def linked_students(subscriber):
    return [
        link.student for link in subscriber.links.select_related("student").filter(student__is_active=True, is_muted=False)
        .order_by("student__first_name", "student__last_name", "student__username")
    ]


# ------------------------------------------------------------------ the report

def week_bounds(day: date):
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


@dataclass
class WeekSummary:
    present: list = field(default_factory=list)
    absent: list = field(default_factory=list)
    homework_total: int = 0
    homework_missed: list = field(default_factory=list)
    grades: list = field(default_factory=list)       # mean scores (Decimal)
    comments: list = field(default_factory=list)     # (comment, teacher name)
    tests: list = field(default_factory=list)        # (score, test name)
    mistakes_fixed: int = 0
    mistakes_open: int = 0

    @property
    def empty(self):
        return not (self.present or self.absent or self.homework_total or self.grades or self.tests or self.mistakes_fixed)


def _aware_range(start, end):
    tz = timezone.get_current_timezone()
    return (timezone.make_aware(datetime.combine(start, datetime.min.time()), tz),
            timezone.make_aware(datetime.combine(end + timedelta(days=1), datetime.min.time()), tz))


def week_summary(student, start, end):
    from apps.integrations.models import HollihopAttendance
    from apps.sat.models import ClassroomMembership, StudentMistake, Test, TestReview

    since, until = _aware_range(start, end)
    summary = WeekSummary()
    for row in HollihopAttendance.objects.filter(student=student, date__gte=start, date__lte=end).order_by("date"):
        (summary.present if row.status == HollihopAttendance.STATUS_PRESENT else summary.absent).append(row.date)

    class_ids = list(ClassroomMembership.objects.filter(
        user=student, role="student", status="approved",
    ).values_list("classroom_id", flat=True))
    checks = LessonHomeworkCheck.objects.filter(classroom_id__in=class_ids, lesson_date__gte=start, lesson_date__lte=end)
    summary.homework_total = checks.count()
    summary.homework_missed = sorted(LessonHomeworkMiss.objects.filter(
        homework_check__in=checks, student=student,
    ).values_list("homework_check__lesson_date", flat=True))

    assessments = RatingAssessment.objects.filter(student=student).filter(
        Q(lesson_date__gte=start, lesson_date__lte=end)
        | Q(lesson_date__isnull=True, assessed_at__gte=since, assessed_at__lt=until)
    ).select_related("teacher").order_by("-assessed_at")
    for assessment in assessments:
        summary.grades.append(assessment.mean_score)
        if assessment.comment.strip() and len(summary.comments) < 2:
            teacher = assessment.teacher
            summary.comments.append((assessment.comment.strip(), teacher.get_full_name() or teacher.username))

    reviews = (
        TestReview.objects.filter(user=student, score__isnull=False, test__isnull=False, test__test_type=Test.TYPE_REGULAR,
                                  created_at__gte=since, created_at__lt=until)
        .exclude(test_type__in=["makeup", "event", "placement"]).select_related("test")
    )
    summary.tests = sorted(((r.score, r.test.name) for r in reviews), key=lambda item: -item[0])
    summary.mistakes_fixed = StudentMistake.objects.filter(
        user=student, status=StudentMistake.STATUS_FIXED, fixed_at__gte=since, fixed_at__lt=until,
    ).count()
    summary.mistakes_open = StudentMistake.objects.filter(user=student, status=StudentMistake.STATUS_OPEN).count()
    return summary


def _days(dates, lang):
    names = WEEKDAYS[lang]
    return ", ".join(f"{names[d.weekday()]} {d:%d.%m}" for d in dates)


def parent_link(lang):
    return f"{settings.SITE_URL}/rating/parent/?lang={lang}"


def report_text(student, start, end, lang, *, so_far=False):
    lang = lang if lang in TEXT else "uz"
    t = TEXT[lang]
    s = week_summary(student, start, end)
    name = html.escape(student.get_full_name() or student.username)
    lines = [t["title"], f"👤 <b>{name}</b> · " + t["week"].format(start=f"{start:%d.%m}", end=f"{end:%d.%m}")]
    if so_far:
        lines.append(t["so_far"])
    lines.append("")
    if s.empty:
        lines.append(t["nothing"])
    else:
        total = len(s.present) + len(s.absent)
        if total:
            line = t["attendance"].format(present=len(s.present), total=total)
            if s.absent:
                line += f" ({t['absent_on'].format(days=_days(s.absent, lang))})"
            lines.append(line)
        if s.homework_total:
            line = t["homework"].format(done=s.homework_total - len(s.homework_missed), total=s.homework_total)
            if s.homework_missed:
                line += f" ({t['homework_missed'].format(days=_days(s.homework_missed, lang))})"
            lines.append(line)
        if s.grades:
            mean = sum(s.grades) / len(s.grades)
            lines.append(t["grades"].format(mean=f"{mean:.1f}", count=len(s.grades)))
            for comment, teacher in s.comments:
                lines.append(t["comment"].format(comment=html.escape(comment[:300]), teacher=html.escape(teacher)))
        if s.tests:
            best, test_name = s.tests[0]
            lines.append(t["tests"].format(count=len(s.tests), best=best, name=html.escape(test_name)))
        elif total or s.grades:
            lines.append(t["tests_none"])
        if s.mistakes_fixed or s.mistakes_open:
            lines.append(t["mistakes"].format(fixed=s.mistakes_fixed, open=s.mistakes_open))
    lines += ["", t["more"].format(link=parent_link(lang))]
    return "\n".join(lines)


# ------------------------------------------------------------------ sending

class TelegramBlocked(Exception):
    """The parent blocked the bot or deleted the chat."""


def bot_token():
    return getattr(settings, "TELEGRAM_PARENT_BOT_TOKEN", "") or ""


def send_message(chat_id, text):
    token = bot_token()
    if not token:
        raise RuntimeError("TELEGRAM_PARENT_BOT_TOKEN is not set.")
    body = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}).encode()
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=body, headers={"Content-Type": "application/json"},
    )
    for _ in range(2):
        try:
            with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310 - fixed Telegram API host
                if response.status == 200:
                    return
                raise RuntimeError(f"Telegram answered {response.status}")
        except urllib.error.HTTPError as exc:
            if exc.code == 403:
                raise TelegramBlocked() from exc
            if exc.code == 429:
                try:
                    wait = int(json.loads(exc.read() or b"{}").get("parameters", {}).get("retry_after", 5))
                except (ValueError, AttributeError):
                    wait = 5
                time.sleep(min(wait, 30))
                continue
            raise RuntimeError(f"Telegram answered {exc.code}") from exc
    raise RuntimeError("Telegram kept asking to wait")


def _claim(subscriber, student, week_start, now):
    """Create or take over this week's report row. Returns it, or None when it is not ours to send."""
    try:
        with transaction.atomic():
            return ParentWeeklyReport.objects.create(
                subscriber=subscriber, student=student, week_start=week_start, attempts=1,
            )
    except IntegrityError:
        pass
    row = ParentWeeklyReport.objects.get(subscriber=subscriber, student=student, week_start=week_start)
    claimed = ParentWeeklyReport.objects.filter(pk=row.pk, attempts__lt=MAX_ATTEMPTS).filter(
        Q(status=ParentWeeklyReport.STATUS_FAILED)
        | Q(status=ParentWeeklyReport.STATUS_SENDING, updated_at__lt=now - STALE_SENDING)
    ).update(status=ParentWeeklyReport.STATUS_SENDING, attempts=F("attempts") + 1, updated_at=now)
    return ParentWeeklyReport.objects.get(pk=row.pk) if claimed else None


def send_weekly_reports(today=None, *, pause=SEND_PAUSE_SECONDS):
    """Send this week's report to every subscribed parent. Safe to run again: sends only what is missing."""
    stats = {"sent": 0, "failed": 0, "blocked": 0, "skipped": 0, "linked": 0}
    if not bot_token():
        stats["disabled"] = True
        return stats
    today = today or timezone.localdate()
    start, end = week_bounds(today)
    now = timezone.now()
    for subscriber in ParentTelegramSubscriber.objects.filter(is_active=True).order_by("pk"):
        if subscriber.phone:
            stats["linked"] += len(link_by_phone(subscriber))  # children added in Hollihop since
        for student in linked_students(subscriber):
            row = _claim(subscriber, student, start, now)
            if row is None:
                stats["skipped"] += 1
                continue
            try:
                send_message(subscriber.chat_id, report_text(student, start, end, subscriber.language))
            except TelegramBlocked:
                row.status, row.error = ParentWeeklyReport.STATUS_FAILED, "The parent blocked the bot."
                row.attempts = MAX_ATTEMPTS
                row.save(update_fields=["status", "error", "attempts", "updated_at"])
                ParentTelegramSubscriber.objects.filter(pk=subscriber.pk).update(is_active=False, updated_at=now)
                stats["blocked"] += 1
                break
            except Exception as exc:  # noqa: BLE001
                row.status, row.error = ParentWeeklyReport.STATUS_FAILED, str(exc)[:300]
                row.save(update_fields=["status", "error", "updated_at"])
                stats["failed"] += 1
                logger.warning("Parent weekly report failed: %s", exc.__class__.__name__)
            else:
                row.status, row.error, row.sent_at = ParentWeeklyReport.STATUS_SENT, "", timezone.now()
                row.save(update_fields=["status", "error", "sent_at", "updated_at"])
                stats["sent"] += 1
            if pause:
                time.sleep(pause)
    return stats


# ------------------------------------------------------------------ manager overview

def overview(week_start=None):
    from apps.sat.models import Classroom, ClassroomMembership

    week_start = week_start or week_bounds(timezone.localdate())[0]
    active_links = ParentTelegramLink.objects.filter(subscriber__is_active=True, student__is_active=True, is_muted=False)
    covered = set(active_links.values_list("student_id", flat=True))
    classes = []
    memberships = ClassroomMembership.objects.filter(
        role="student", status="approved", classroom__is_active=True, user__is_active=True,
    ).values_list("classroom_id", "user_id")
    per_class = {}
    for classroom_id, user_id in memberships:
        per_class.setdefault(classroom_id, set()).add(user_id)
    names = {c.pk: c for c in Classroom.objects.filter(pk__in=per_class).select_related("teacher")}
    for classroom_id, students in per_class.items():
        classroom = names[classroom_id]
        with_parent = len(students & covered)
        classes.append({
            "classroom": classroom, "students": len(students), "with_parent": with_parent,
            "rate": round(with_parent * 100 / len(students)) if students else 0,
        })
    classes.sort(key=lambda c: (c["rate"], c["classroom"].name.casefold()))
    all_students = set().union(*per_class.values()) if per_class else set()
    reports = ParentWeeklyReport.objects.filter(week_start=week_start)
    last_week = ParentWeeklyReport.objects.filter(week_start=week_start - timedelta(days=7))
    return {
        "subscribers": ParentTelegramSubscriber.objects.filter(is_active=True).count(),
        "stopped": ParentTelegramSubscriber.objects.filter(is_active=False).count(),
        "students": len(all_students),
        "students_with_parent": len(all_students & covered),
        "coverage": round(len(all_students & covered) * 100 / len(all_students)) if all_students else 0,
        "this_week": {s: reports.filter(status=s).count() for s in ("sent", "failed", "sending")},
        "last_week": {s: last_week.filter(status=s).count() for s in ("sent", "failed", "sending")},
        "failures": list(reports.filter(status=ParentWeeklyReport.STATUS_FAILED).select_related("subscriber", "student")[:30]),
        "classes": classes,
        "week_start": week_start,
    }
