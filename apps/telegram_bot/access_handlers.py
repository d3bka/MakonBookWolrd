"""V103: /id for everyone, and "👥 Access" for super admins (give and take away bot access)."""
from __future__ import annotations

import html
import logging

from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from asgiref.sync import sync_to_async

from .access import grant_access, is_superadmin, parse_telegram_id, people_with_access, revoke_access

logger = logging.getLogger(__name__)

ACCESS_BUTTON = "👥 Access"


class AccessStates(StatesGroup):
    waiting_for_person = State()


def _menu():
    people = people_with_access()
    lines = ["👥 <b>Who can use this bot</b>", ""]
    builder = InlineKeyboardBuilder()
    for person in people:
        name = html.escape(person["name"] or "—")
        if person["superadmin"]:
            lines.append(f"⭐ {name} · <code>{person['telegram_id']}</code> · super admin")
        else:
            lines.append(f"• {name} · <code>{person['telegram_id']}</code>")
            builder.button(text=f"❌ {person['name'] or person['telegram_id']}"[:60], callback_data=f"access_rm_{person['telegram_id']}")
    if len(people) == len([p for p in people if p["superadmin"]]):
        lines.append("")
        lines.append("Nobody else has access yet.")
    lines += ["", "Super admins are set in .env (TELEGRAM_SUPERADMIN_IDS)."]
    builder.button(text="➕ Give access", callback_data="access_add")
    builder.adjust(1)
    return "\n".join(lines), builder.as_markup()


def _cancel_markup():
    builder = InlineKeyboardBuilder()
    builder.button(text="✖️ Cancel", callback_data="access_cancel")
    return builder.as_markup()


async def show_id(message: types.Message):
    await message.answer(
        f"🆔 Your Telegram ID: <code>{message.from_user.id}</code>\n"
        "Send it to a MakonBook administrator if you need access to this bot."
    )


async def access_menu(message: types.Message, state: FSMContext):
    if not is_superadmin(message.from_user.id):
        return
    await state.clear()
    text, markup = await sync_to_async(_menu)()
    await message.answer(text, reply_markup=markup)


async def access_add(callback: types.CallbackQuery, state: FSMContext):
    if not is_superadmin(callback.from_user.id):
        await callback.answer("Only super admins can do this.", show_alert=True)
        return
    await state.set_state(AccessStates.waiting_for_person)
    await callback.message.answer(
        "➕ <b>Give access</b>\n\n"
        "Send me one of these:\n"
        "• the person's Telegram ID (they get it by sending /id to this bot);\n"
        "• their contact (📎 → Contact);\n"
        "• any message forwarded from them.",
        reply_markup=_cancel_markup(),
    )
    await callback.answer()


def _person_from_message(message: types.Message):
    """(telegram_id, first_name, last_name, username, problem)."""
    contact = message.contact
    if contact is not None:
        if contact.user_id:
            return contact.user_id, contact.first_name or "", contact.last_name or "", "", ""
        return None, "", "", "", "This contact has no Telegram account. Ask the person to send /id to this bot."
    origin = getattr(message, "forward_origin", None)
    if origin is not None:
        user = getattr(origin, "sender_user", None)
        if user is not None:
            return user.id, user.first_name or "", user.last_name or "", user.username or "", ""
        return None, "", "", "", "This person hides their account in forwarded messages. Ask them to send /id to this bot and send me the number."
    telegram_id = parse_telegram_id(message.text)
    if telegram_id:
        return telegram_id, "", "", "", ""
    return None, "", "", "", "That is not a Telegram ID. Send only the number, for example <code>123456789</code>."


async def access_receive(message: types.Message, state: FSMContext):
    if not is_superadmin(message.from_user.id):
        await state.clear()
        return
    telegram_id, first, last, username, problem = _person_from_message(message)
    if problem:
        await message.answer(f"⚠️ {problem}", reply_markup=_cancel_markup())
        return
    if telegram_id == message.bot.id:
        await message.answer("⚠️ That is this bot itself.", reply_markup=_cancel_markup())
        return
    admin, changed = await sync_to_async(grant_access)(telegram_id, first_name=first, last_name=last, username=username)
    await state.clear()
    from .access import display_name

    name = html.escape(display_name(admin))
    if not changed:
        await message.answer(f"ℹ️ {name} already has access.")
    else:
        try:
            await message.bot.send_message(telegram_id, "✅ You now have access to the MakonBook bot. Press /start.")
            await message.answer(f"✅ {name} now has access. I let them know.")
        except Exception:  # noqa: BLE001 - they never opened the bot
            await message.answer(f"✅ {name} now has access. Ask them to open this bot and press /start.")
    text, markup = await sync_to_async(_menu)()
    await message.answer(text, reply_markup=markup)


async def access_remove_ask(callback: types.CallbackQuery):
    if not is_superadmin(callback.from_user.id):
        await callback.answer("Only super admins can do this.", show_alert=True)
        return
    telegram_id = parse_telegram_id(callback.data.removeprefix("access_rm_"))
    builder = InlineKeyboardBuilder()
    builder.button(text="Yes, remove access", callback_data=f"access_rmok_{telegram_id}")
    builder.button(text="✖️ Cancel", callback_data="access_cancel")
    builder.adjust(1)
    await callback.message.answer(f"Remove access for <code>{telegram_id}</code>?", reply_markup=builder.as_markup())
    await callback.answer()


async def access_remove_ok(callback: types.CallbackQuery):
    if not is_superadmin(callback.from_user.id):
        await callback.answer("Only super admins can do this.", show_alert=True)
        return
    telegram_id = parse_telegram_id(callback.data.removeprefix("access_rmok_"))
    result = await sync_to_async(revoke_access)(telegram_id) if telegram_id else "missing"
    notes = {
        "removed": "✅ Access removed.",
        "superadmin": "⭐ Super admins are removed only in .env (TELEGRAM_SUPERADMIN_IDS).",
        "missing": "ℹ️ This person had no access.",
    }
    await callback.message.edit_text(notes[result])
    text, markup = await sync_to_async(_menu)()
    await callback.message.answer(text, reply_markup=markup)
    await callback.answer()


async def access_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Cancelled.")
    await callback.answer()


def register(dp):
    from aiogram.filters import Command, StateFilter

    dp.message.register(show_id, Command("id"))
    dp.message.register(access_menu, lambda m: m.text == ACCESS_BUTTON)
    dp.message.register(access_receive, StateFilter(AccessStates.waiting_for_person))
    dp.callback_query.register(access_add, lambda c: c.data == "access_add")
    dp.callback_query.register(access_remove_ok, lambda c: (c.data or "").startswith("access_rmok_"))
    dp.callback_query.register(access_remove_ask, lambda c: (c.data or "").startswith("access_rm_"))
    dp.callback_query.register(access_cancel, lambda c: c.data == "access_cancel")
