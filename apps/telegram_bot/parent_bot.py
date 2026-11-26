"""V115: the MakonBook parents' bot (a separate bot from the staff bot).

A parent picks a language, shares their own Telegram contact and gets every child whose
phone in Hollihop is that number; a child with another number is added by the family access
code. Every Sunday at 19:00 the parent gets the weekly report (apps.ratings.parent_reports,
sent by Celery). In the bot they can also see this week's report so far, their children,
add a child by code, change the language or stop the reports (/stop).

The bot runs inside the staff bot's process when TELEGRAM_PARENT_BOT_TOKEN is set.
The conversation logic is plain Django code (``on_*``) so it is tested without Telegram.
"""
from __future__ import annotations

import asyncio
import html
import logging
import re
from dataclasses import dataclass, field

from django.conf import settings
from django.utils import timezone

from apps.ratings import parent_reports as reports
from apps.ratings.models import ParentTelegramLink, ParentTelegramSubscriber

logger = logging.getLogger(__name__)

CODE_RE = re.compile(r"^[A-Za-z0-9]{12}$")

T = {
    "ru": {
        "intro": ("Это бот MakonBook для родителей. Каждое воскресенье в 19:00 я присылаю отчёт о ребёнке: "
                  "посещаемость, домашние задания, оценки учителя и пробные тесты.\n\n"
                  "Нажмите «📱 Отправить мой номер» — я найду ваших детей по номеру, записанному в учебном центре."),
        "btn_phone": "📱 Отправить мой номер",
        "btn_code": "🔑 Ввести код семьи",
        "btn_report": "📊 Отчёт за эту неделю",
        "btn_children": "👨‍👩‍👧 Мои дети",
        "btn_add": "🔑 Добавить по коду",
        "btn_language": "🌐 Язык",
        "not_own": "Отправьте, пожалуйста, свой номер кнопкой «📱 Отправить мой номер».",
        "found": "Готово! Отчёт будет приходить о: {names}.\nКаждое воскресенье в 19:00.",
        "not_found": ("По номеру {phone} учеников не нашлось. Если в учебном центре записан другой номер, "
                      "попросите ребёнка открыть MakonBook → Settings → Family access code и пришлите этот код сюда."),
        "ask_code": "Пришлите код семьи (12 букв и цифр). Он есть у ребёнка в MakonBook: Settings → Family access code.",
        "code_ok": "Добавлен(а): {name}. Отчёт придёт в воскресенье в 19:00.",
        "code_bad": "Код не подошёл. Проверьте и пришлите ещё раз (осталось попыток: {left}).",
        "code_limit": "Слишком много попыток. Попробуйте через час.",
        "children": "Ваши дети в MakonBook:\n{names}\n\nОтчёт приходит каждое воскресенье в 19:00. Чтобы убрать ребёнка, нажмите кнопку ниже.",
        "no_children": "Пока нет ни одного ребёнка. Отправьте свой номер или код семьи.",
        "unlinked": "Убрано: {name}. Отчёты о нём (ней) больше не придут.",
        "stopped": "Отчёты отключены. Чтобы снова их получать, нажмите /start.",
        "help": "Выберите действие кнопками внизу.",
        "language_set": "Язык: русский.",
    },
    "uz": {
        "intro": ("Bu MakonBook ota-onalar uchun boti. Har yakshanba soat 19:00 da farzandingiz haqida hisobot yuboraman: "
                  "davomat, uy vazifalari, o'qituvchi baholari va amaliy testlar.\n\n"
                  "«📱 Raqamimni yuborish» tugmasini bosing — o'quv markazida yozilgan raqam bo'yicha farzandlaringizni topaman."),
        "btn_phone": "📱 Raqamimni yuborish",
        "btn_code": "🔑 Oila kodini kiritish",
        "btn_report": "📊 Shu haftalik hisobot",
        "btn_children": "👨‍👩‍👧 Farzandlarim",
        "btn_add": "🔑 Kod orqali qo'shish",
        "btn_language": "🌐 Til",
        "not_own": "Iltimos, o'z raqamingizni «📱 Raqamimni yuborish» tugmasi orqali yuboring.",
        "found": "Tayyor! Hisobot quyidagilar haqida keladi: {names}.\nHar yakshanba soat 19:00 da.",
        "not_found": ("{phone} raqami bo'yicha o'quvchi topilmadi. Agar o'quv markazida boshqa raqam yozilgan bo'lsa, "
                      "farzandingizdan MakonBook → Settings → Family access code bo'limini ochishni so'rang va kodni shu yerga yuboring."),
        "ask_code": "Oila kodini yuboring (12 ta harf va raqam). U farzandingizning MakonBook sahifasida: Settings → Family access code.",
        "code_ok": "Qo'shildi: {name}. Hisobot yakshanba soat 19:00 da keladi.",
        "code_bad": "Kod mos kelmadi. Tekshirib, qayta yuboring (qolgan urinishlar: {left}).",
        "code_limit": "Urinishlar juda ko'p. Bir soatdan keyin qayta urinib ko'ring.",
        "children": "MakonBook'dagi farzandlaringiz:\n{names}\n\nHisobot har yakshanba soat 19:00 da keladi. Farzandni olib tashlash uchun pastdagi tugmani bosing.",
        "no_children": "Hozircha farzand qo'shilmagan. Raqamingizni yoki oila kodini yuboring.",
        "unlinked": "Olib tashlandi: {name}. Uning hisobotlari endi kelmaydi.",
        "stopped": "Hisobotlar o'chirildi. Qayta olish uchun /start ni bosing.",
        "help": "Pastdagi tugmalardan birini tanlang.",
        "language_set": "Til: o'zbekcha.",
    },
}
CHOOSE_LANGUAGE = "Assalomu alaykum! Tilni tanlang.\nЗдравствуйте! Выберите язык."
LANGUAGE_BUTTONS = [("🇺🇿 O'zbekcha", "lang:uz"), ("🇷🇺 Русский", "lang:ru")]


@dataclass
class Reply:
    text: str
    keyboard: str | None = None   # "contact", "main" or None (keep the current one)
    inline: list = field(default_factory=list)  # [(label, callback data)]
    lang: str = "uz"
    is_html: bool = False  # the weekly report is HTML already; everything else is escaped


def _name(user):
    return user.get_full_name() or user.username


def _subscriber(chat_id):
    return ParentTelegramSubscriber.objects.filter(chat_id=chat_id).first()


def _menu_reply(sub, text):
    return Reply(text, keyboard="main" if reports.linked_students(sub) else "contact", lang=sub.language)


def on_start(chat_id, user_id, first_name="", username=""):
    sub, _ = ParentTelegramSubscriber.objects.update_or_create(
        chat_id=chat_id,
        defaults={"telegram_user_id": user_id, "first_name": (first_name or "")[:200],
                  "username": (username or "")[:200], "is_active": True},
    )
    return Reply(CHOOSE_LANGUAGE, inline=LANGUAGE_BUTTONS, lang=sub.language)


def on_language(chat_id, lang):
    sub = _subscriber(chat_id)
    if sub is None or lang not in T:
        return Reply(CHOOSE_LANGUAGE, inline=LANGUAGE_BUTTONS)
    sub.language = lang
    sub.save(update_fields=["language", "updated_at"])
    if reports.linked_students(sub):
        return Reply(T[lang]["language_set"], keyboard="main", lang=lang)
    return Reply(T[lang]["intro"], keyboard="contact", lang=lang)


def on_contact(chat_id, from_user_id, contact_user_id, phone):
    sub = _subscriber(chat_id)
    if sub is None:
        return Reply(CHOOSE_LANGUAGE, inline=LANGUAGE_BUTTONS)
    t = T[sub.language]
    if not contact_user_id or contact_user_id != from_user_id:
        return Reply(t["not_own"], keyboard="contact", lang=sub.language)  # someone else's contact: not proof
    sub.phone = reports._normalize(phone)
    sub.is_active = True
    sub.save(update_fields=["phone", "is_active", "updated_at"])
    reports.link_by_phone(sub)
    children = reports.linked_students(sub)
    if not children:
        return Reply(t["not_found"].format(phone=sub.phone or phone), keyboard="contact", lang=sub.language)
    return Reply(t["found"].format(names=", ".join(_name(c) for c in children)), keyboard="main", lang=sub.language)


def _children(sub):
    t = T[sub.language]
    children = reports.linked_students(sub)
    if not children:
        return Reply(t["no_children"], keyboard="contact", lang=sub.language)
    names = "\n".join(f"• {_name(c)}" for c in children)
    return Reply(t["children"].format(names=names), keyboard="main", lang=sub.language,
                 inline=[(f"❌ {_name(c)}", f"unlink:{c.pk}") for c in children])


def report_messages(sub):
    """This week's report so far, one message per child."""
    children = reports.linked_students(sub)
    if not children:
        return [Reply(T[sub.language]["no_children"], keyboard="contact", lang=sub.language)]
    today = timezone.localdate()
    start, end = reports.week_bounds(today)
    so_far = today < end or timezone.localtime().hour < 19
    return [Reply(reports.report_text(child, start, end, sub.language, so_far=so_far), keyboard="main",
                  lang=sub.language, is_html=True) for child in children]


def on_text(chat_id, text):
    sub = _subscriber(chat_id)
    if sub is None:
        return [Reply(CHOOSE_LANGUAGE, inline=LANGUAGE_BUTTONS)]
    t = T[sub.language]
    text = (text or "").strip()
    buttons = {lang: T[lang] for lang in T}
    if any(text == b["btn_report"] for b in buttons.values()):
        return report_messages(sub)
    if any(text == b["btn_children"] for b in buttons.values()):
        return [_children(sub)]
    if any(text in (b["btn_add"], b["btn_code"]) for b in buttons.values()):
        return [Reply(t["ask_code"], lang=sub.language)]
    if any(text == b["btn_language"] for b in buttons.values()):
        return [Reply(CHOOSE_LANGUAGE, inline=LANGUAGE_BUTTONS, lang=sub.language)]
    code = text.replace(" ", "").replace("-", "")
    if CODE_RE.match(code):
        student, error = reports.link_by_code(sub, code)
        if error == "limit":
            return [Reply(t["code_limit"], lang=sub.language)]
        if error:
            return [Reply(t["code_bad"].format(left=reports.code_attempts_left(sub)), lang=sub.language)]
        if not sub.is_active:
            sub.is_active = True
            sub.save(update_fields=["is_active", "updated_at"])
        return [Reply(t["code_ok"].format(name=_name(student)), keyboard="main", lang=sub.language)]
    return [_menu_reply(sub, t["help"])]


def on_unlink(chat_id, student_id):
    sub = _subscriber(chat_id)
    if sub is None:
        return Reply(CHOOSE_LANGUAGE, inline=LANGUAGE_BUTTONS)
    link = sub.links.select_related("student").filter(student_id=student_id, is_muted=False).first()
    if link is None:
        return _children(sub)
    name = _name(link.student)
    link.is_muted = True  # kept, so the Sunday run does not add the child back by phone
    link.save(update_fields=["is_muted"])
    reply = _children(sub)
    reply.text = T[sub.language]["unlinked"].format(name=name) + "\n\n" + reply.text
    return reply


def on_stop(chat_id):
    sub = _subscriber(chat_id)
    if sub is None:
        return Reply(T["uz"]["stopped"])
    sub.is_active = False
    sub.save(update_fields=["is_active", "updated_at"])
    return Reply(T[sub.language]["stopped"], lang=sub.language)


# ------------------------------------------------------------------ aiogram glue

def _markup(reply):
    from aiogram.types import (
        InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup,
    )

    if reply.inline:
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=label, callback_data=data)]
                                                     for label, data in reply.inline])
    t = T.get(reply.lang, T["uz"])
    if reply.keyboard == "contact":
        return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
            [KeyboardButton(text=t["btn_phone"], request_contact=True)], [KeyboardButton(text=t["btn_code"])],
        ])
    if reply.keyboard == "main":
        return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
            [KeyboardButton(text=t["btn_report"])],
            [KeyboardButton(text=t["btn_children"]), KeyboardButton(text=t["btn_add"])],
            [KeyboardButton(text=t["btn_language"])],
        ])
    return None


def build_router():
    from aiogram import F, Router
    from aiogram.filters import Command, CommandStart
    from aiogram.types import CallbackQuery, Message
    from asgiref.sync import sync_to_async

    router = Router(name="parents")
    router.message.filter(F.chat.type == "private")

    async def answer(message, reply):
        text = reply.text if reply.is_html else html.escape(reply.text)
        await message.answer(text, reply_markup=_markup(reply), disable_web_page_preview=True)

    @router.message(CommandStart())
    async def start(message: Message):
        user = message.from_user
        reply = await sync_to_async(on_start)(message.chat.id, user.id, user.first_name or "", user.username or "")
        await answer(message, reply)

    @router.message(Command("stop"))
    async def stop(message: Message):
        await answer(message, await sync_to_async(on_stop)(message.chat.id))

    @router.message(Command("report"))
    async def report(message: Message):
        sub = await sync_to_async(_subscriber)(message.chat.id)
        if sub is None:
            await answer(message, Reply(CHOOSE_LANGUAGE, inline=LANGUAGE_BUTTONS))
            return
        for reply in await sync_to_async(report_messages)(sub):
            await answer(message, reply)

    @router.message(F.contact)
    async def contact(message: Message):
        reply = await sync_to_async(on_contact)(
            message.chat.id, message.from_user.id, message.contact.user_id, message.contact.phone_number,
        )
        await answer(message, reply)

    @router.message(F.text)
    async def text(message: Message):
        for reply in await sync_to_async(on_text)(message.chat.id, message.text):
            await answer(message, reply)

    @router.callback_query(F.data.startswith("lang:"))
    async def language(callback: CallbackQuery):
        reply = await sync_to_async(on_language)(callback.message.chat.id, callback.data.split(":", 1)[1])
        await callback.answer()
        await answer(callback.message, reply)

    @router.callback_query(F.data.startswith("unlink:"))
    async def unlink(callback: CallbackQuery):
        raw = callback.data.split(":", 1)[1]
        reply = await sync_to_async(on_unlink)(callback.message.chat.id, int(raw) if raw.isdecimal() else 0)
        await callback.answer()
        await answer(callback.message, reply)

    return router


async def run_parent_bot():
    """Poll the parents' bot until cancelled. Does nothing without TELEGRAM_PARENT_BOT_TOKEN."""
    token = getattr(settings, "TELEGRAM_PARENT_BOT_TOKEN", "")
    if not token:
        logger.info("Parents' bot is off: TELEGRAM_PARENT_BOT_TOKEN is not set.")
        return
    from aiogram import Bot, Dispatcher
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(build_router())
    while True:
        try:
            await bot.delete_webhook(drop_pending_updates=False)
            logger.info("Parents' bot polling started.")
            await dp.start_polling(bot, handle_signals=False)
            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - keep the staff bot alive; retry later
            logger.error("Parents' bot stopped: %s; restarting in 30 s", exc.__class__.__name__)
            await asyncio.sleep(30)
        finally:
            await bot.session.close()
