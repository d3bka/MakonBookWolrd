from __future__ import annotations

from datetime import timedelta
import secrets
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.sat.roles import is_teacher as has_teacher_access, can_manage_classroom, is_platform_admin
from apps.sat.models import Classroom, ClassroomMembership, MakonNotification

from .engine import build_board, student_rating
from .forms import RatingAssessmentForm
from .models import RatingAssessment, RatingConfig, RatingProfile, TermGrade
from .assessment_policy import today_assessment_state, prepare_today_obligations, required_lesson_dates, week_start
from apps.integrations.models import HollihopAttendance
from apps.sat.models import TestReview, VocabularyQuizAttempt
from apps.apclasses.models import APExamAttempt


PARENT_LANGUAGE_CHOICES = ("en", "ru", "uz")

PARENT_TRANSLATIONS = {
    "en": {
        "page_title": "Parent Portal | SAT Makon",
        "open_menu": "Open menu",
        "main_navigation": "Main navigation",
        "home": "Home",
        "student_rating": "Student Rating",
        "parent_access": "Parent access",
        "leaderboard": "Leaderboard",
        "landing_page": "Landing page",
        "back_to_makonbook": "Back to MakonBook",
        "parent_title": "Parent access",
        "parent_intro": "Enter the phone number registered on the student's SATMakon account. After a successful lookup, this browser keeps the student open after refresh so you do not have to enter the phone number every time.",
        "public_leaderboard": "Public leaderboard",
        "student_access_code": "Registered phone number",
        "code_placeholder": "+998 90 123 45 67",
        "open_rating": "Open student stats",
        "rank": "Rank",
        "rating": "Rating",
        "assessments": "Assessments",
        "classrooms": "Classrooms",
        "date": "Date",
        "classroom": "Classroom",
        "homework": "Homework",
        "progress": "Progress",
        "activity": "Activity",
        "attendance": "Attendance",
        "behavior": "Behavior",
        "mean": "Mean",
        "no_history": "No rating history is available yet.",
        "footer_text": "Digital SAT practice platform with tests, analytics, classrooms, and student rating.",
        "back_to_top": "Back to top",
        "language": "Language",
        "report_issue": "Report issue",
        "report_problem": "Report a problem",
        "close": "Close",
        "report_description": "Describe what happened and what you expected. This is one general platform report, not an automatic request to change an answer key.",
        "category": "Category",
        "technical_problem": "Technical problem",
        "content_problem": "Question or content problem",
        "account_problem": "Account or access problem",
        "rating_problem": "Rating problem",
        "suggestion": "Suggestion",
        "other": "Other",
        "name_optional": "Name (optional)",
        "email_optional": "Email (optional)",
        "comment": "Comment",
        "comment_placeholder": "Example: I could not open my child's statistics using the registered phone number...",
        "send_report": "Send report",
        "sending": "Sending...",
        "report_sent": "Report sent. Thank you.",
        "report_failed": "Could not send report.",
        "too_many_attempts": "Too many phone-number lookup attempts. Try again later.",
        "code_not_found": "Phone number not found. Enter the phone number registered on the student's SATMakon account.",
        "remembered_on_device": "Remembered on this device",
        "switch_student": "Use another student",
        "registration_help": "Use the phone number already registered on the student's SATMakon account. No separate parent code is required.",
        "device_note": "After the first successful lookup, this browser remembers the student. Refreshing the page will keep the statistics open. Use “Use another student” on shared devices when you are finished.",
        "use_registered_phone": "Use the student's registered phone number",
        "support": "Support",
        "multiple_students_title": "Choose a student",
        "multiple_students_intro": "This phone number is linked to more than one student. Select the student whose statistics you want to open.",
        "select_student": "Open statistics",
        "use_another_phone": "Use another phone number",
        "records": "records",
    },
    "ru": {
        "page_title": "Родительский портал | SAT Makon",
        "open_menu": "Открыть меню",
        "main_navigation": "Главная навигация",
        "home": "Главная",
        "student_rating": "Рейтинг учеников",
        "parent_access": "Для родителей",
        "leaderboard": "Рейтинг",
        "landing_page": "Главная страница",
        "back_to_makonbook": "Вернуться в MakonBook",
        "parent_title": "Доступ для родителей",
        "parent_intro": "Введите номер телефона, зарегистрированный в аккаунте ученика SATMakon. После успешного поиска браузер запомнит ученика, поэтому после обновления вводить номер повторно не нужно.",
        "public_leaderboard": "Общий рейтинг",
        "student_access_code": "Зарегистрированный номер телефона",
        "code_placeholder": "+998 90 123 45 67",
        "open_rating": "Открыть статистику",
        "rank": "Место",
        "rating": "Рейтинг",
        "assessments": "Оценивания",
        "classrooms": "Классы",
        "date": "Дата",
        "classroom": "Класс",
        "homework": "Домашняя работа",
        "progress": "Прогресс",
        "activity": "Активность",
        "attendance": "Посещаемость",
        "behavior": "Поведение",
        "mean": "Среднее",
        "no_history": "Истории оценивания пока нет.",
        "footer_text": "Платформа подготовки к Digital SAT: тесты, аналитика, классы и рейтинг учеников.",
        "back_to_top": "Наверх",
        "language": "Язык",
        "report_issue": "Сообщить о проблеме",
        "report_problem": "Сообщить о проблеме",
        "close": "Закрыть",
        "report_description": "Опишите, что произошло и какой результат вы ожидали. Это общее сообщение о проблеме платформы.",
        "category": "Категория",
        "technical_problem": "Техническая проблема",
        "content_problem": "Проблема с вопросом или содержанием",
        "account_problem": "Проблема с аккаунтом или доступом",
        "rating_problem": "Проблема с рейтингом",
        "suggestion": "Предложение",
        "other": "Другое",
        "name_optional": "Имя (необязательно)",
        "email_optional": "Email (необязательно)",
        "comment": "Комментарий",
        "comment_placeholder": "Например: я не смог открыть статистику ребёнка по зарегистрированному номеру телефона...",
        "send_report": "Отправить",
        "sending": "Отправка...",
        "report_sent": "Сообщение отправлено. Спасибо.",
        "report_failed": "Не удалось отправить сообщение.",
        "too_many_attempts": "Слишком много попыток поиска по номеру телефона. Попробуйте позже.",
        "code_not_found": "Номер телефона не найден. Введите номер, зарегистрированный в аккаунте ученика SATMakon.",
        "remembered_on_device": "Сохранено на этом устройстве",
        "switch_student": "Другой ученик",
        "registration_help": "Введите номер телефона, который уже зарегистрирован в аккаунте ученика SATMakon. Отдельный код для родителей не нужен.",
        "device_note": "После первого успешного поиска этот браузер запомнит ученика. После обновления страницы статистика останется открытой. На общем устройстве используйте кнопку «Другой ученик», когда закончите.",
        "use_registered_phone": "Используйте номер телефона, зарегистрированный у ученика",
        "support": "Поддержка",
        "multiple_students_title": "Выберите ученика",
        "multiple_students_intro": "Этот номер телефона привязан к нескольким ученикам. Выберите, чью статистику нужно открыть.",
        "select_student": "Открыть статистику",
        "use_another_phone": "Использовать другой номер",
        "records": "записей",
    },
    "uz": {
        "page_title": "Ota-onalar portali | SAT Makon",
        "open_menu": "Menyuni ochish",
        "main_navigation": "Asosiy navigatsiya",
        "home": "Bosh sahifa",
        "student_rating": "O‘quvchilar reytingi",
        "parent_access": "Ota-onalar uchun",
        "leaderboard": "Reyting",
        "landing_page": "Bosh sahifa",
        "back_to_makonbook": "MakonBook’ga qaytish",
        "parent_title": "Ota-onalar uchun kirish",
        "parent_intro": "O‘quvchining SATMakon akkauntida ro‘yxatdan o‘tgan telefon raqamini kiriting. Muvaffaqiyatli qidiruvdan so‘ng brauzer o‘quvchini eslab qoladi.",
        "public_leaderboard": "Umumiy reyting",
        "student_access_code": "Ro‘yxatdan o‘tgan telefon raqami",
        "code_placeholder": "+998 90 123 45 67",
        "open_rating": "Statistikani ochish",
        "rank": "O‘rin",
        "rating": "Reyting",
        "assessments": "Baholashlar",
        "classrooms": "Sinflar",
        "date": "Sana",
        "classroom": "Sinf",
        "homework": "Uy vazifasi",
        "progress": "O‘sish",
        "activity": "Faollik",
        "attendance": "Davomat",
        "behavior": "Xulq-atvor",
        "mean": "O‘rtacha",
        "no_history": "Hozircha baholash tarixi mavjud emas.",
        "footer_text": "Digital SAT tayyorgarlik platformasi: testlar, tahlil, sinflar va o‘quvchilar reytingi.",
        "back_to_top": "Yuqoriga",
        "language": "Til",
        "report_issue": "Muammo haqida xabar berish",
        "report_problem": "Muammo haqida xabar berish",
        "close": "Yopish",
        "report_description": "Nima sodir bo‘lganini va qanday natija kutganingizni yozing. Bu platformadagi umumiy muammo haqida xabar.",
        "category": "Toifa",
        "technical_problem": "Texnik muammo",
        "content_problem": "Savol yoki kontent bilan bog‘liq muammo",
        "account_problem": "Hisob yoki kirish bilan bog‘liq muammo",
        "rating_problem": "Reyting bilan bog‘liq muammo",
        "suggestion": "Taklif",
        "other": "Boshqa",
        "name_optional": "Ism (ixtiyoriy)",
        "email_optional": "Email (ixtiyoriy)",
        "comment": "Izoh",
        "comment_placeholder": "Masalan: ro‘yxatdan o‘tgan telefon raqami orqali farzandimning statistikasini ocha olmadim...",
        "send_report": "Yuborish",
        "sending": "Yuborilmoqda...",
        "report_sent": "Xabar yuborildi. Rahmat.",
        "report_failed": "Xabarni yuborib bo‘lmadi.",
        "too_many_attempts": "Telefon raqami orqali qidirish urinishlari juda ko‘p. Keyinroq qayta urinib ko‘ring.",
        "code_not_found": "Telefon raqami topilmadi. O‘quvchining SATMakon akkauntida ro‘yxatdan o‘tgan raqamni kiriting.",
        "remembered_on_device": "Ushbu qurilmada saqlandi",
        "switch_student": "Boshqa o‘quvchi",
        "registration_help": "O‘quvchining SATMakon akkauntida allaqachon ro‘yxatdan o‘tgan telefon raqamidan foydalaning. Alohida ota-ona kodi kerak emas.",
        "device_note": "Birinchi muvaffaqiyatli qidiruvdan so‘ng ushbu brauzer o‘quvchini eslab qoladi. Sahifa yangilanganda statistika ochiq qoladi. Umumiy qurilmada ish tugagach «Boshqa o‘quvchi» tugmasidan foydalaning.",
        "use_registered_phone": "O‘quvchining ro‘yxatdan o‘tgan telefon raqamidan foydalaning",
        "support": "Yordam",
        "multiple_students_title": "O‘quvchini tanlang",
        "multiple_students_intro": "Bu telefon raqami bir nechta o‘quvchiga biriktirilgan. Statistikasi ochilishi kerak bo‘lgan o‘quvchini tanlang.",
        "select_student": "Statistikani ochish",
        "use_another_phone": "Boshqa telefon raqamidan foydalanish",
        "records": "yozuv",
    },
}


def _parent_language(request):
    requested = (request.GET.get("lang") or request.POST.get("lang") or "").strip().lower()
    if requested in PARENT_LANGUAGE_CHOICES:
        request.session["rating_parent_language"] = requested
        return requested

    saved = (request.session.get("rating_parent_language") or "").strip().lower()
    if saved in PARENT_LANGUAGE_CHOICES:
        return saved

    browser_language = (request.META.get("HTTP_ACCEPT_LANGUAGE") or "").lower()
    for token in browser_language.split(","):
        code = token.split(";", 1)[0].strip().split("-", 1)[0]
        if code in PARENT_LANGUAGE_CHOICES:
            request.session["rating_parent_language"] = code
            return code

    request.session["rating_parent_language"] = "en"
    return "en"


def _parent_context(request, **extra):
    language = _parent_language(request)
    context = {
        "parent_lang": language,
        "parent_t": PARENT_TRANSLATIONS[language],
        "parent_languages": (
            ("en", "English"),
            ("ru", "Русский"),
            ("uz", "O‘zbekcha"),
        ),
        "issue_report_t": PARENT_TRANSLATIONS[language],
    }
    context.update(extra)
    return context


def _is_teacher_for(user, classroom):
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return can_manage_classroom(user, classroom)


def rating_home(request):
    # Public leaderboard was removed from the public product surface.
    # Keep /rating/ only as the signed-in student's own rating workspace.
    if not request.user.is_authenticated or request.user.is_staff or request.user.is_superuser:
        return redirect("rating_parent_lookup")

    config = RatingConfig.get_solo()
    board = build_board()
    if request.user.is_authenticated and not request.user.is_staff and not request.user.is_superuser:
        entry = student_rating(request.user)
        history = RatingAssessment.objects.filter(student=request.user).select_related("classroom", "teacher")[:100]
        context = {
            "entry": entry,
            "history": history,
            "board": board,
            "config": config,
            "profile": RatingProfile.objects.get_or_create(user=request.user)[0],
        }
        # Ranking is deliberately separate from the student's own learning
        # Progress page. Merge the complete workspace context so the shell
        # keeps real level/sidebar/classroom state instead of rendering zeros.
        try:
            from apps.sat.student_workspace import student_workspace_context
            context.update(student_workspace_context(request.user, active="ranking"))
        except Exception:
            context["student_workspace_active"] = "ranking"
        return render(request, "ratings/student_dashboard.html", context)
    return redirect("rating_parent_lookup")


def public_student(request, student_id):
    # Public student profile pages belonged to the removed public leaderboard.
    return redirect("rating_parent_lookup")


def _normalize_parent_phone(raw_value):
    """Normalize parent lookup input to an E.164-like Uzbekistan phone value.

    The database stores Hollihop/SATMakon phone numbers on UserProfile. We
    accept spaces, dashes and parentheses, and treat a 9-digit local number as
    +998XXXXXXXXX.
    """
    raw = (raw_value or "").strip()
    if not raw:
        return ""
    digits = re.sub(r"\D+", "", raw)
    if len(digits) == 9:
        digits = "998" + digits
    elif len(digits) == 12 and digits.startswith("998"):
        pass
    elif raw.startswith("+") and 10 <= len(digits) <= 15:
        return "+" + digits
    else:
        return ""
    return "+" + digits


def _parent_phone_variants(normalized_phone):
    if not normalized_phone:
        return []
    digits = re.sub(r"\D+", "", normalized_phone)
    variants = {normalized_phone, digits}
    if digits.startswith("998") and len(digits) == 12:
        local = digits[3:]
        variants.update({local, "0" + local})
    return list(variants)


def _parent_profiles_from_phone(raw_value):
    """Return every active student account linked to a registered phone number.

    A family can legitimately reuse one parent phone number for siblings, so
    phone lookup must never collapse the result to ``.first()``. The caller
    decides whether to open the single match directly or show a chooser.
    """
    normalized_phone = _normalize_parent_phone(raw_value)
    if not normalized_phone:
        return [], ""
    users = list(
        User.objects.filter(
            is_active=True,
            profile__phone_number__in=_parent_phone_variants(normalized_phone),
        )
        .select_related("profile")
        .order_by("first_name", "last_name", "username", "pk")
    )
    profiles = []
    for user in users:
        profile, _ = RatingProfile.objects.get_or_create(user=user)
        profiles.append(profile)
    return profiles, normalized_phone


def _parent_candidates_from_session(request):
    candidate_ids = [
        int(value)
        for value in request.session.get("rating_parent_candidate_user_ids", [])
        if str(value).isdigit()
    ]
    if not candidate_ids:
        return []
    users = list(
        User.objects.filter(pk__in=candidate_ids, is_active=True)
        .select_related("profile")
        .order_by("first_name", "last_name", "username", "pk")
    )
    valid_ids = {user.pk for user in users}
    clean_ids = [value for value in candidate_ids if value in valid_ids]
    if clean_ids != candidate_ids:
        request.session["rating_parent_candidate_user_ids"] = clean_ids
        request.session.modified = True
    return users


def _parent_snapshot(profile):
    if not profile:
        return None, []
    return (
        student_rating(profile.user),
        RatingAssessment.objects.filter(student=profile.user)
        .select_related("classroom", "teacher")[:50],
    )


def _remembered_parent_profile(request):
    user_id = request.session.get("rating_parent_student_user_id")
    if not user_id:
        return None
    user = (
        User.objects.filter(
            pk=user_id,
            is_active=True,
            profile__phone_number__isnull=False,
        )
        .select_related("profile")
        .first()
    )
    if not user:
        request.session.pop("rating_parent_student_user_id", None)
        return None
    profile, _ = RatingProfile.objects.get_or_create(user=user)
    return profile


def _clear_parent_private(request):
    request.session.pop('rating_parent_private_student_id', None)
    request.session.pop('rating_parent_private_timestamp', None)


def _parent_has_private_access(request, profile):
    if not profile:
        return False
    if request.user.is_authenticated and request.user.pk == profile.user_id:
        return True
    timestamp = request.session.get('rating_parent_private_timestamp', 0)
    try:
        valid_age = 0 <= timezone.now().timestamp() - float(timestamp) < 3600
    except (TypeError, ValueError):
        valid_age = False
    return bool(valid_age and request.session.get('rating_parent_private_student_id') == profile.user_id)


@login_required(login_url='/login/')
def parent_share_code(request):
    """Only the signed-in student can disclose their own private family passcode."""
    profile, _ = RatingProfile.objects.get_or_create(user=request.user)
    return render(request, 'ratings/parent_share_code.html', {'family_code': profile.parent_access_code})


def _parent_private_context(request, profile):
    if not _parent_has_private_access(request, profile):
        return {'parent_private_verified': False}
    user = profile.user
    reviews = (TestReview.objects.filter(user=user).select_related('test', 'makeup_test')
               .order_by('-created_at', '-pk'))
    results_page = Paginator(reviews, 25).get_page(request.GET.get('page'))
    attend_qs = HollihopAttendance.objects.filter(student=user)
    aggregate = attend_qs.aggregate(total=Count('pk'), present=Count('pk', filter=Q(status='present')), absent=Count('pk', filter=Q(status='absent')))
    aggregate['percentage'] = round(100 * aggregate['present'] / aggregate['total'], 1) if aggregate['total'] else None
    return {
        'parent_private_verified': True,
        'term_grades': TermGrade.objects.filter(student=user).select_related('classroom').order_by('-awarded_at', 'classroom__name'),
        'practice_results': results_page,
        'practice_count': reviews.count(),
        'vocabulary_results': VocabularyQuizAttempt.objects.filter(user=user).select_related('classroom').order_by('-completed_at'),
        'ap_results': APExamAttempt.objects.filter(student=user, status='submitted').select_related('event').order_by('-submitted_at'),
        'parent_attendance': attend_qs.select_related('classroom').order_by('-date', '-pk')[:60],
        'parent_attendance_stats': aggregate,
    }


def parent_lookup(request):
    language = _parent_language(request)
    translations = PARENT_TRANSLATIONS[language]
    action = (request.POST.get("action") or "lookup") if request.method == "POST" else ""

    if request.method == "POST" and action == "reset":
        _clear_parent_private(request)
        request.session.pop("rating_parent_student_user_id", None)
        request.session.pop("rating_parent_candidate_user_ids", None)
        request.session.pop("rating_parent_candidate_phone", None)
        request.session.modified = True
        return redirect(f"{reverse('rating_parent_lookup')}?lang={language}")

    if request.method == "POST" and action == "switch":
        _clear_parent_private(request)
        request.session.pop("rating_parent_student_user_id", None)
        # If the same family phone belongs to siblings, return to the chooser
        # instead of making the parent type the same phone number again.
        candidates = _parent_candidates_from_session(request)
        if len(candidates) <= 1:
            request.session.pop("rating_parent_candidate_user_ids", None)
            request.session.pop("rating_parent_candidate_phone", None)
        request.session.modified = True
        return redirect(f"{reverse('rating_parent_lookup')}?lang={language}")

    if request.method == "POST" and action == "select":
        _clear_parent_private(request)
        candidates = _parent_candidates_from_session(request)
        allowed_ids = {user.pk for user in candidates}
        try:
            selected_id = int(request.POST.get("student_user_id") or 0)
        except (TypeError, ValueError):
            selected_id = 0
        if selected_id in allowed_ids:
            request.session["rating_parent_student_user_id"] = selected_id
            request.session.modified = True
        return redirect(f"{reverse('rating_parent_lookup')}?lang={language}")

    profile = _remembered_parent_profile(request)
    if request.method == 'POST' and action == 'verify_private' and profile:
        attempts = [int(ts) for ts in request.session.get('rating_parent_private_attempts', [])
                    if timezone.now().timestamp() - int(ts) < 3600]
        if len(attempts) >= 8:
            messages.error(request, 'Too many private access attempts. Try again later.')
        else:
            supplied = (request.POST.get('family_code') or '').strip().upper()[:32]
            attempts.append(int(timezone.now().timestamp()))
            request.session['rating_parent_private_attempts'] = attempts
            if secrets.compare_digest(supplied, profile.parent_access_code):
                request.session['rating_parent_private_student_id'] = profile.user_id
                request.session['rating_parent_private_timestamp'] = timezone.now().timestamp()
                request.session.modified = True
                return redirect(f"{reverse('rating_parent_lookup')}?lang={language}")
            messages.error(request, 'Invalid family access code.')
    phone_number_value = request.session.get("rating_parent_candidate_phone", "") if not profile else ""

    if request.method == "POST" and action == "lookup":
        _clear_parent_private(request)
        now_ts = int(timezone.now().timestamp())
        attempts = [
            int(ts)
            for ts in request.session.get("rating_parent_lookup_times", [])
            if now_ts - int(ts) < 3600
        ]
        if len(attempts) >= 10:
            messages.error(request, translations["too_many_attempts"])
            entry, history = _parent_snapshot(profile)
            registered_phone = getattr(getattr(profile.user, "profile", None), "phone_number", "") if profile else ""
            return render(
                request,
                "ratings/parent_lookup.html",
                _parent_context(
                    request,
                    profile=profile,
                    entry=entry,
                    history=history,
                    registered_phone=registered_phone,
                    phone_number_value=phone_number_value,
                    parent_candidates=_parent_candidates_from_session(request) if not profile else [],
                ),
                status=429,
            )

        phone_number_value = (
            request.POST.get("phone_number")
            or request.POST.get("registration_number")  # temporary compatibility alias
            or request.POST.get("code")
            or ""
        ).strip()[:32]
        attempts.append(now_ts)
        request.session["rating_parent_lookup_times"] = attempts

        profiles, normalized_phone = _parent_profiles_from_phone(phone_number_value)
        if not profiles:
            request.session.pop("rating_parent_candidate_user_ids", None)
            request.session.pop("rating_parent_candidate_phone", None)
            messages.error(request, translations["code_not_found"])
        elif len(profiles) == 1:
            request.session["rating_parent_student_user_id"] = profiles[0].user_id
            request.session["rating_parent_candidate_user_ids"] = [profiles[0].user_id]
            request.session["rating_parent_candidate_phone"] = normalized_phone
            request.session.modified = True
            return redirect(f"{reverse('rating_parent_lookup')}?lang={language}")
        else:
            request.session.pop("rating_parent_student_user_id", None)
            request.session["rating_parent_candidate_user_ids"] = [item.user_id for item in profiles]
            request.session["rating_parent_candidate_phone"] = normalized_phone
            request.session.modified = True
            return redirect(f"{reverse('rating_parent_lookup')}?lang={language}")

    if profile is None:
        profile = _remembered_parent_profile(request)

    parent_candidates = [] if profile else _parent_candidates_from_session(request)
    entry, history = _parent_snapshot(profile)
    registered_phone = (
        getattr(getattr(profile.user, "profile", None), "phone_number", "")
        if profile
        else ""
    )
    return render(
        request,
        "ratings/parent_lookup.html",
        _parent_context(
            request,
            profile=profile,
            entry=entry,
            history=history,
            registered_phone=registered_phone,
            phone_number_value=phone_number_value,
            parent_candidates=parent_candidates,
            **_parent_private_context(request, profile),
        ),
    )

@login_required
def teacher_classroom_ratings(request, classroom_id):
    classroom = get_object_or_404(Classroom, pk=classroom_id)
    if not _is_teacher_for(request.user, classroom):
        raise PermissionDenied
    memberships = list(ClassroomMembership.objects.filter(classroom=classroom, role="student", status="approved").select_related("user").order_by("user__first_name", "user__last_name", "user__username"))
    for index, membership in enumerate(memberships):
        membership.previous_student_id = memberships[index - 1].user_id if index > 0 else None
        membership.next_student_id = memberships[index + 1].user_id if index + 1 < len(memberships) else None
    schedule, allowed, required = today_assessment_state(classroom, request.user)
    if allowed:
        prepare_today_obligations(schedule=schedule)
    today = timezone.localdate()
    graded_today = set(RatingAssessment.objects.filter(
        classroom=classroom, teacher=request.user, lesson_date=today,
    ).values_list('student_id', flat=True))
    for membership in memberships:
        membership.graded_today = membership.user_id in graded_today
    recent = RatingAssessment.objects.filter(classroom=classroom, teacher=request.user).select_related("student")[:30]
    return render(request, "ratings/teacher_classroom.html", {
        "classroom": classroom,
        "memberships": memberships,
        "recent": recent,
        "config": RatingConfig.get_solo(),
        "assessment_form": RatingAssessmentForm(),
        "assessment_allowed_today": allowed,
        "assessment_required_today": required,
        "lesson_schedule": schedule,
        "week_required_dates": required_lesson_dates(schedule, today) if schedule else [],
        "graded_today_count": len(graded_today),
    })


@login_required
@require_POST
def save_assessment_deck(request, classroom_id):
    classroom = get_object_or_404(Classroom, pk=classroom_id)
    if not _is_teacher_for(request.user, classroom):
        raise PermissionDenied
    schedule, allowed, required = today_assessment_state(classroom, request.user)
    if not allowed:
        raise PermissionDenied('Assessment is closed: no confirmed lesson today. Deadline 23:59:59 (Asia/Tashkent).')
    prepare_today_obligations(schedule=schedule)
    memberships = {
        row.user_id: row
        for row in ClassroomMembership.objects.filter(
            classroom=classroom, role="student", status="approved"
        ).select_related("user")
    }
    selected_ids = []
    for raw_id in request.POST.getlist("student_ids"):
        try:
            student_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if student_id in memberships and request.POST.get(f"include_{student_id}") == "1":
            selected_ids.append(student_id)
    if not selected_ids:
        messages.error(request, "Enter or change at least one student's assessment before saving the deck.")
        return redirect("teacher_classroom_assessments_root", classroom_id=classroom.id)

    prepared = []
    for student_id in selected_ids:
        payload = {
            "homework": request.POST.get(f"homework_{student_id}"),
            "progress": request.POST.get(f"progress_{student_id}"),
            "activity": request.POST.get(f"activity_{student_id}"),
            "attendance": request.POST.get(f"attendance_{student_id}"),
            "behavior": request.POST.get(f"behavior_{student_id}"),
            "comment": request.POST.get(f"comment_{student_id}", ""),
        }
        existing = RatingAssessment.objects.filter(
            classroom=classroom, teacher=request.user, student_id=student_id,
            lesson_date=timezone.localdate(),
        ).first()
        form = RatingAssessmentForm(payload, instance=existing)
        if not form.is_valid():
            messages.error(request, f"Check the scores for {memberships[student_id].user.get_full_name() or memberships[student_id].user.username}.")
            return redirect("teacher_classroom_assessments_root", classroom_id=classroom.id)
        prepared.append((student_id, form))

    created = []
    with transaction.atomic():
        for student_id, form in prepared:
            assessment = form.save(commit=False)
            assessment.classroom = classroom
            assessment.student_id = student_id
            assessment.teacher = request.user
            assessment.lesson_date = timezone.localdate()
            assessment.assessed_at = timezone.now()
            from django.core.exceptions import ValidationError
            try:
                assessment.full_clean()
            except ValidationError as exc:
                raise PermissionDenied(f'Assessment not accepted: {exc}')
            assessment.save()
            created.append(assessment)
        MakonNotification.objects.bulk_create([
            MakonNotification(
                user_id=assessment.student_id,
                type=MakonNotification.TYPE_ASSESSMENT,
                title=f"New assessment: {classroom.name}",
                message=f"Your teacher saved a new classroom assessment. Mean: {assessment.mean_score:.1f}/10.",
                url=reverse("student_progress_root"),
            )
            for assessment in created
        ])
    messages.success(request, f"Assessment deck saved for {len(created)} student(s).")
    return redirect("teacher_classroom_assessments_root", classroom_id=classroom.id)


@login_required
def assess_student(request, classroom_id, student_id):
    classroom = get_object_or_404(Classroom, pk=classroom_id)
    if not _is_teacher_for(request.user, classroom):
        raise PermissionDenied
    student = get_object_or_404(User, pk=student_id)
    if not ClassroomMembership.objects.filter(classroom=classroom, user=student, role="student", status="approved").exists():
        raise PermissionDenied("Student is not an approved classroom member.")
    schedule, allowed, required = today_assessment_state(classroom, request.user)
    if request.method == "POST":
        if not allowed:
            raise PermissionDenied('Assessment is closed: scheduled lesson days only, until 23:59:59 Tashkent time.')
        prepare_today_obligations(schedule=schedule)
        existing = RatingAssessment.objects.filter(
            classroom=classroom, teacher=request.user, student=student,
            lesson_date=timezone.localdate(),
        ).first()
        form = RatingAssessmentForm(request.POST, instance=existing)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.classroom = classroom
            assessment.student = student
            assessment.teacher = request.user
            assessment.lesson_date = timezone.localdate()
            assessment.assessed_at = timezone.now()
            from django.core.exceptions import ValidationError
            try:
                assessment.full_clean()
            except ValidationError as exc:
                raise PermissionDenied(f'Assessment not accepted: {exc}')
            assessment.save()
            messages.success(request, f"Rating saved for {student.get_full_name() or student.username}.")
            next_id = request.POST.get("next_student_id")
            if next_id:
                return redirect("rating_assess_student", classroom_id=classroom.id, student_id=next_id)
            return redirect("rating_teacher_classroom", classroom_id=classroom.id)
    else:
        form = RatingAssessmentForm()
    student_ids = list(ClassroomMembership.objects.filter(classroom=classroom, role="student", status="approved").order_by("user__first_name", "user__last_name", "user__username").values_list("user_id", flat=True))
    next_student_id = None
    previous_student_id = None
    if student.pk in student_ids:
        index = student_ids.index(student.pk)
        if index > 0:
            previous_student_id = student_ids[index - 1]
        if index + 1 < len(student_ids):
            next_student_id = student_ids[index + 1]
    return render(request, "ratings/assess_student.html", {"classroom": classroom, "student_obj": student, "form": form, "next_student_id": next_student_id, "previous_student_id": previous_student_id, "assessment_allowed_today": allowed})


@login_required
@require_POST
def edit_assessment(request, assessment_id):
    assessment = get_object_or_404(RatingAssessment.objects.select_related("classroom"), pk=assessment_id)
    if not _is_teacher_for(request.user, assessment.classroom):
        raise PermissionDenied
    if assessment.teacher_id != request.user.pk and not (request.user.is_staff or request.user.is_superuser):
        raise PermissionDenied
    if not (request.user.is_staff or request.user.is_superuser):
        _, allowed, _ = today_assessment_state(assessment.classroom, request.user)
        if not allowed or assessment.lesson_date != timezone.localdate():
            raise PermissionDenied('Assessment edits close at 23:59:59 of the lesson day.')
    form = RatingAssessmentForm(request.POST, instance=assessment)
    if form.is_valid():
        form.save()
        messages.success(request, "Assessment updated.")
    else:
        messages.error(request, "Assessment was not updated. Check all scores are from 0 to 10.")
    return redirect("rating_teacher_classroom", classroom_id=assessment.classroom_id)
