"""V103: only listed Telegram users may use the bot; super admins (from .env) give and take away access."""
import os
from types import SimpleNamespace
from unittest import mock

from asgiref.sync import async_to_sync
from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.telegram_bot import access
from apps.telegram_bot import access_handlers as h
from apps.telegram_bot.models import TelegramAdmin
from apps.telegram_bot.utils import check_admin_privileges

SUPER = 111111111
PERSON = 222222222


def message(user_id, text="", contact=None, forward_origin=None):
    bot = mock.AsyncMock()
    bot.id = 999999999
    return SimpleNamespace(
        from_user=SimpleNamespace(id=user_id), text=text, contact=contact, forward_origin=forward_origin,
        answer=mock.AsyncMock(), bot=bot,
    )


def callback(user_id, data):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=user_id), data=data, answer=mock.AsyncMock(),
        message=SimpleNamespace(answer=mock.AsyncMock(), edit_text=mock.AsyncMock()),
    )


def state():
    return mock.AsyncMock()


@override_settings(TELEGRAM_SUPERADMIN_IDS=f"{SUPER}, 333333333")
class BotAccessTests(TestCase):
    def test_only_listed_people_and_super_admins_get_in(self):
        check = async_to_sync(check_admin_privileges)
        self.assertIsNone(check(PERSON))
        admin = check(SUPER)  # the super admin needs no row in advance
        self.assertTrue(admin.is_admin and admin.is_active)
        access.grant_access(PERSON, first_name="Dilnoza")
        self.assertEqual(check(PERSON).first_name, "Dilnoza")
        self.assertEqual(access.revoke_access(PERSON), "removed")
        self.assertIsNone(check(PERSON))
        self.assertEqual(access.revoke_access(SUPER), "superadmin")
        self.assertIsNotNone(check(SUPER))

    def test_id_command_and_denied_message_show_the_id(self):
        msg = message(PERSON, "/id")
        async_to_sync(h.show_id)(msg)
        self.assertIn(str(PERSON), msg.answer.call_args.args[0])
        from apps.telegram_bot.handlers import StartHandler

        msg = message(PERSON, "/start")
        async_to_sync(StartHandler.start_command)(msg)
        self.assertIn("Access Denied", msg.answer.call_args.args[0])
        self.assertIn(str(PERSON), msg.answer.call_args.args[0])

    def test_super_admin_gives_access_by_id_contact_or_forward(self):
        st = state()
        async_to_sync(h.access_add)(callback(SUPER, "access_add"), st)
        st.set_state.assert_awaited_once()

        msg = message(SUPER, "  222 222 222 ")
        async_to_sync(h.access_receive)(msg, st)
        self.assertTrue(TelegramAdmin.objects.get(telegram_id=PERSON).is_admin)
        msg.bot.send_message.assert_awaited_once()  # the person is told
        st.clear.assert_awaited()

        contact = SimpleNamespace(user_id=444444444, first_name="Bekzod", last_name="T")
        async_to_sync(h.access_receive)(message(SUPER, contact=contact), state())
        self.assertEqual(TelegramAdmin.objects.get(telegram_id=444444444).first_name, "Bekzod")

        forwarded = SimpleNamespace(sender_user=SimpleNamespace(id=555555555, first_name="Malika", last_name="", username="malika_y"))
        async_to_sync(h.access_receive)(message(SUPER, forward_origin=forwarded), state())
        self.assertEqual(TelegramAdmin.objects.get(telegram_id=555555555).username, "malika_y")

        hidden = message(SUPER, forward_origin=SimpleNamespace(sender_user_name="Hidden"))
        st = state()
        async_to_sync(h.access_receive)(hidden, st)
        self.assertIn("/id", hidden.answer.call_args.args[0])
        st.clear.assert_not_awaited()  # still waiting for a usable answer

    def test_remove_and_menu(self):
        access.grant_access(PERSON, first_name="Dilnoza")
        menu = message(SUPER, h.ACCESS_BUTTON)
        async_to_sync(h.access_menu)(menu, state())
        text = menu.answer.call_args.args[0]
        self.assertIn("Dilnoza", text)
        self.assertIn("super admin", text)
        cb = callback(SUPER, f"access_rmok_{PERSON}")
        async_to_sync(h.access_remove_ok)(cb)
        self.assertFalse(TelegramAdmin.objects.get(telegram_id=PERSON).is_active)

    def test_people_without_super_admin_rights_cannot_manage(self):
        access.grant_access(PERSON)
        menu = message(PERSON, h.ACCESS_BUTTON)
        async_to_sync(h.access_menu)(menu, state())
        menu.answer.assert_not_awaited()
        cb = callback(PERSON, "access_add")
        async_to_sync(h.access_add)(cb, state())
        self.assertIn("super admins", cb.answer.call_args.args[0])
        async_to_sync(h.access_receive)(message(PERSON, "777777777"), state())
        self.assertFalse(TelegramAdmin.objects.filter(telegram_id=777777777).exists())
        cb = callback(PERSON, f"access_rmok_{SUPER}")
        async_to_sync(h.access_remove_ok)(cb)
        self.assertTrue(TelegramAdmin.objects.filter(telegram_id=PERSON, is_active=True).exists())

    def test_access_button_only_for_super_admins(self):
        from apps.telegram_bot.handlers import StartHandler

        texts = lambda kb: [b.text for row in kb.keyboard for b in row]  # noqa: E731
        self.assertIn(h.ACCESS_BUTTON, texts(StartHandler.get_main_keyboard(True, SUPER)))
        self.assertNotIn(h.ACCESS_BUTTON, texts(StartHandler.get_main_keyboard(True, PERSON)))

    def test_system_alerts_go_to_everyone_with_access(self):
        from apps.base.system_health import alert_recipients

        access.grant_access(PERSON)
        with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "x"}), override_settings(MONITORING_TELEGRAM_CHAT_ID=""):
            chats = alert_recipients()["telegram"]
        self.assertEqual(sorted(chats), sorted([str(SUPER), "333333333", str(PERSON)]))


@override_settings(TELEGRAM_SUPERADMIN_IDS=str(SUPER))
class TelegramAccessPageTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("ta_admin", "a@makonbook.example", "x")
        self.url = reverse("admin_telegram_access")

    def test_admin_gives_and_removes_access(self):
        self.client.force_login(self.admin)
        page = self.client.get(self.url)
        self.assertContains(page, "Telegram bot access")
        self.assertContains(page, str(SUPER))
        self.assertContains(page, "Super admin")
        self.client.post(self.url, {"action": "grant", "telegram_id": str(PERSON), "name": "Dilnoza"})
        self.assertTrue(TelegramAdmin.objects.get(telegram_id=PERSON).is_active)
        self.assertContains(self.client.get(self.url), "Dilnoza")
        self.client.post(self.url, {"action": "revoke", "telegram_id": str(PERSON)})
        self.assertFalse(TelegramAdmin.objects.get(telegram_id=PERSON).is_active)
        response = self.client.post(self.url, {"action": "revoke", "telegram_id": str(SUPER)}, follow=True)
        self.assertContains(response, "only in .env")
        self.client.post(self.url, {"action": "grant", "telegram_id": "abc"})
        self.assertEqual(TelegramAdmin.objects.filter(is_active=True).count(), 0)

    def test_teachers_cannot_open_it(self):
        teacher = User.objects.create_user("ta_teacher", password="x")
        teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        self.client.force_login(teacher)
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.post(self.url, {"action": "grant", "telegram_id": str(PERSON)})
        self.assertFalse(TelegramAdmin.objects.exists())
