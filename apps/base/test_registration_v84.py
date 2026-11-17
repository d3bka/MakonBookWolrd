"""V84: public sign-up with an email code, and joining a SATMakon (Hollihop) account
with an SMS code. Plus the Hollihop sync rules that keep self-registered accounts safe."""
import re
from unittest import mock

from django.contrib.auth import authenticate, get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.base.models import PendingRegistration, SatmakonLinkCode
from apps.integrations.hollihop.sync import HollihopSyncEngine
from apps.integrations.tests import BASE_SETTINGS, FakeHollihopClient
from apps.sat.models import Classroom, ClassroomMembership
from apps.sat.student_access import is_active_satmakon_student

User = get_user_model()
PASSWORD = "Makon-Strong-2026"


def code_from_mail():
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)


class SignUpTests(TestCase):
    def setUp(self):
        cache.clear()

    def post_form(self, **overrides):
        data = {"first_name": "Laylo", "last_name": "Aliyeva", "email": "Laylo@Example.com",
                "password": PASSWORD, "password2": PASSWORD, "agree": "1"}
        data.update(overrides)
        return self.client.post(reverse("register"), data)

    def test_sign_up_creates_the_account_only_after_the_email_code(self):
        self.assertEqual(self.client.get(reverse("register")).status_code, 200)
        response = self.post_form()
        self.assertRedirects(response, reverse("register_verify"))
        self.assertFalse(User.objects.filter(email__iexact="laylo@example.com").exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["laylo@example.com"])
        code = code_from_mail()

        wrong = self.client.post(reverse("register_verify"), {"code": "000000" if code != "000000" else "111111"})
        self.assertContains(wrong, "The code is not correct.")
        response = self.client.post(reverse("register_verify"), {"code": code})
        self.assertRedirects(response, reverse("satmakon_link"), fetch_redirect_response=False)
        user = User.objects.get(email="laylo@example.com")
        self.assertTrue(user.profile.self_registered)
        self.assertIsNotNone(user.profile.email_verified_at)
        self.assertEqual((user.first_name, user.last_name), ("Laylo", "Aliyeva"))
        self.assertIsNone(user.profile.hollihop_client_id)
        self.assertFalse(is_active_satmakon_student(user))  # a free account: first tests only
        self.assertEqual(authenticate(username="laylo@example.com", password=PASSWORD), user)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_one_email_one_account(self):
        User.objects.create_user("someone", email="taken@example.com", password="x")
        response = self.post_form(email="TAKEN@example.com")
        self.assertContains(response, "already exists")
        self.assertFalse(PendingRegistration.objects.exists())

    def test_form_errors(self):
        response = self.post_form(first_name="", password="short", password2="other", agree="")
        for text in ("Enter your first name.", "The passwords do not match.", "Please accept the terms"):
            self.assertContains(response, text)
        self.assertEqual(len(mail.outbox), 0)

    def test_five_wrong_codes_lock_the_code_and_a_new_one_works(self):
        self.post_form()
        first = code_from_mail()
        for _ in range(5):
            self.client.post(reverse("register_verify"), {"code": "999999" if first != "999999" else "888888"})
        response = self.client.post(reverse("register_verify"), {"code": first})
        self.assertContains(response, "Too many wrong codes")
        self.client.post(reverse("register_resend"))
        second = code_from_mail()
        self.assertEqual(len(mail.outbox), 2)
        response = self.client.post(reverse("register_verify"), {"code": second})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email="laylo@example.com").exists())

    def test_an_unconfirmed_sign_up_does_not_block_the_real_owner(self):
        self.post_form()
        other = self.client_class()
        other.post(reverse("register"), {"first_name": "Real", "last_name": "Owner", "email": "laylo@example.com",
                                         "password": PASSWORD, "password2": PASSWORD, "agree": "1"})
        code = code_from_mail()
        other.post(reverse("register_verify"), {"code": code})
        self.assertEqual(User.objects.get(email="laylo@example.com").first_name, "Real")

    def test_login_page_offers_sign_up(self):
        self.assertContains(self.client.get(reverse("login")), reverse("register"))

    def test_signed_in_users_are_sent_to_their_dashboard(self):
        user = User.objects.create_user("x1", password="x")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("register")).status_code, 302)


@override_settings(MAKONBOOK_SMS_PROVIDER="disabled", MAKONBOOK_SATMAKON_LINK_TEST_CODES=True)
class SatmakonLinkTests(TestCase):
    def setUp(self):
        cache.clear()
        self.student = self.hollihop_student(5001, "Aziz", "Karimov", "+998901234567")
        self.me = User.objects.create_user("laylo.new", email="aziz.new@example.com", password=PASSWORD,
                                           first_name="Aziz", last_name="K")
        self.me.profile.self_registered = True
        self.me.profile.email_verified_at = self.me.date_joined
        self.me.profile.save()
        self.client.force_login(self.me)

    @staticmethod
    def hollihop_student(client_id, first, last, phone):
        user = User.objects.create_user(f"hstu_{client_id}", first_name=first, last_name=last)
        user.set_unusable_password()
        user.save()
        profile = user.profile
        profile.hollihop_client_id = client_id
        profile.hollihop_created = True
        profile.hollihop_status = "Занимается"
        profile.phone_number = phone
        profile.save()
        return user

    def send(self, phone):
        return self.client.post(reverse("satmakon_link"), {"phone": phone})

    def code(self, response):
        return re.search(r"your code is <strong>(\d{6})</strong>", response.content.decode()).group(1)

    def test_sms_code_joins_the_satmakon_account(self):
        response = self.send("90 123 45 67")
        self.assertContains(response, "Enter the SMS code")
        response = self.client.post(reverse("satmakon_link_verify"), {"code": self.code(response)})
        self.assertRedirects(response, reverse("student_dashboard_root"), fetch_redirect_response=False)
        self.student = User.objects.select_related("profile").get(pk=self.student.pk)
        self.me.refresh_from_db()
        self.assertEqual(self.student.email, "aziz.new@example.com")
        self.assertIsNotNone(self.student.profile.email_verified_at)
        self.assertEqual(authenticate(username="aziz.new@example.com", password=PASSWORD), self.student)
        self.assertFalse(self.me.is_active)
        self.assertEqual(self.me.email, "")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.student.pk)
        self.assertTrue(is_active_satmakon_student(self.student))

    def test_unknown_number_and_bad_codes(self):
        self.assertContains(self.send("+998 99 000 00 00"), "could not find a current SATMakon student")
        response = self.send("+998901234567")
        for _ in range(5):
            self.client.post(reverse("satmakon_link_verify"), {"code": "000000"})
        response = self.client.post(reverse("satmakon_link_verify"), {"code": self.code(response)})
        self.assertContains(response, "Too many wrong codes")
        self.student.refresh_from_db()
        self.assertEqual(self.student.email, "")

    def test_students_who_left_satmakon_cannot_be_claimed(self):
        self.student.is_active = False
        self.student.save()
        self.assertContains(self.send("+998901234567"), "could not find a current SATMakon student")

    def test_an_account_with_its_own_confirmed_email_is_never_taken_over(self):
        self.student.email = "owner@example.com"
        self.student.save()
        self.student.profile.email_verified_at = self.student.date_joined
        self.student.profile.save()
        response = self.send("+998901234567")
        response = self.client.post(reverse("satmakon_link_verify"), {"code": self.code(response)}, follow=True)
        self.assertContains(response, "already connected to another email")
        self.student.refresh_from_db()
        self.assertEqual(self.student.email, "owner@example.com")

    def test_a_shared_family_number_asks_who_you_are(self):
        sibling = self.hollihop_student(5002, "Malika", "Karimova", "+998901234567")
        response = self.send("+998901234567")
        response = self.client.post(reverse("satmakon_link_verify"), {"code": self.code(response)})
        self.assertContains(response, "Who are you?")
        self.assertContains(response, "Malika Karimova")
        outsider = self.hollihop_student(5003, "Other", "Person", "+998907777777")
        response = self.client.post(reverse("satmakon_link_choose"), {"student": outsider.pk}, follow=True)
        self.assertContains(response, "Choose one of the students")
        response = self.client.post(reverse("satmakon_link_choose"), {"student": sibling.pk})
        sibling.refresh_from_db()
        self.assertEqual(sibling.email, "aziz.new@example.com")

    @override_settings(MAKONBOOK_SMS_PROVIDER="playmobile", MAKONBOOK_SATMAKON_LINK_TEST_CODES=False,
                       PLAYMOBILE_TEMPLATE_ID="credentials-tpl", PLAYMOBILE_VERIFICATION_TEMPLATE_ID="")
    def test_the_real_sms_carries_the_code_and_it_is_not_shown(self):
        with mock.patch("apps.integrations.hollihop.sms.send_sms") as send:
            response = self.send("+998901234567")
        self.assertNotContains(response, "your code is")
        phone, text = send.call_args.args
        self.assertEqual(phone, "+998901234567")
        # Never the credentials template: approved literal text mode.
        self.assertEqual(send.call_args.kwargs, {"template_id": "", "template_variables": None})
        self.assertRegex(text, r"^MakonBook: Your verification code for MakonBook is \d{6}$")

    @override_settings(MAKONBOOK_SMS_PROVIDER="playmobile", MAKONBOOK_SATMAKON_LINK_TEST_CODES=False,
                       PLAYMOBILE_API_URL="https://send.example/broker-api/send", PLAYMOBILE_LOGIN="l",
                       PLAYMOBILE_PASSWORD="p", PLAYMOBILE_ORIGINATOR="SATMAKON",
                       PLAYMOBILE_TEMPLATE_ID="credentials-tpl", PLAYMOBILE_VERIFICATION_TEMPLATE_ID="otp-77",
                       PLAYMOBILE_VERIFICATION_TEMPLATE_VARIABLE="code")
    def test_playmobile_uses_its_own_verification_template(self):
        with mock.patch("apps.integrations.hollihop.sms._post_json_text", return_value="Request is received") as post:
            response = self.send("+998901234567")
        self.assertContains(response, "Enter the SMS code")
        item = post.call_args.args[1]["messages"][0]
        self.assertEqual(item["template-id"], "otp-77")
        self.assertRegex(item["variables"]["code"], r"^\d{6}$")
        self.assertNotIn("sms", item)

    @override_settings(MAKONBOOK_SATMAKON_LINK_TEST_CODES=False)
    def test_no_test_codes_in_production_when_sms_is_off(self):
        self.assertContains(self.send("+998901234567"), "SMS sending is not available")
        self.assertFalse(SatmakonLinkCode.objects.exists())

    def test_linked_and_hollihop_accounts_do_not_see_the_link_page(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("satmakon_link")).status_code, 302)


@override_settings(**BASE_SETTINGS)
class HollihopSyncWithRegisteredStudentsTests(TestCase):
    """The user's scenario: the student already has a MakonBook account; Hollihop must just
    add them to their classrooms and open full access, without a duplicate or a new password."""

    def setUp(self):
        self.api = FakeHollihopClient()
        self.api.teachers = [{"Id": 50, "FirstName": "Tina", "LastName": "Teacher", "MiddleName": "",
                              "EMail": "t@example.com", "Mobile": "+998901111111", "Status": "Works", "Fired": False}]
        self.api.edunits = [{"Id": 14, "Name": "SAT Group A", "Corporative": False,
                             "ScheduleItems": [{"TeacherIds": [50]}], "_status": "Working"}]

    @staticmethod
    def row(client_id, *, phone="", email="", status="Active"):
        return {"ClientId": client_id, "FirstName": "Aziz", "LastName": "Karimov", "MiddleName": "",
                "EMail": email, "Mobile": phone, "Status": status}

    def full_sync(self):
        engine = HollihopSyncEngine(client=self.api)
        engine.sync_teachers()
        engine.sync_students()
        engine.sync_classrooms()
        engine.sync_memberships()

    def test_joined_account_gets_classrooms_without_duplicate_or_new_password(self):
        # 1) Hollihop made the account; 2) the student signed up and joined it by SMS code.
        self.api.students = [self.row(7001, phone="901234567")]
        self.api.relations = [{"EdUnitId": 14, "StudentClientId": 7001, "Status": "Normal", "EdUnitCorporative": False}]
        self.full_sync()
        user = User.objects.get(profile__hollihop_client_id=7001)
        user.email = "aziz@example.com"
        user.set_password(PASSWORD)
        user.save()
        user.profile.email_verified_at = user.date_joined
        user.profile.save()
        old_hash = User.objects.get(pk=user.pk).password

        # Hollihop now has another email and a new group: the login email and password stay.
        self.api.students = [self.row(7001, phone="+998 90 123 45 67", email="crm-typo@example.com")]
        self.api.edunits.append({"Id": 15, "Name": "SAT Group B", "Corporative": False,
                                 "ScheduleItems": [{"TeacherIds": [50]}], "_status": "Working"})
        self.api.relations.append({"EdUnitId": 15, "StudentClientId": 7001, "Status": "Normal", "EdUnitCorporative": False})
        self.full_sync()
        user.refresh_from_db()
        self.assertEqual(user.email, "aziz@example.com")
        self.assertEqual(user.password, old_hash)
        self.assertEqual(User.objects.filter(profile__hollihop_client_id=7001).count(), 1)
        groups = set(ClassroomMembership.objects.filter(user=user, status="approved")
                     .values_list("classroom__hollihop_edunit_id", flat=True))
        self.assertEqual(groups, {14, 15})
        self.assertTrue(is_active_satmakon_student(user))

    def test_existing_makonbook_account_with_the_hollihop_email_is_linked_not_duplicated(self):
        existing = User.objects.create_user("legacy.aziz", email="aziz@example.com", password=PASSWORD)
        old_hash = existing.password
        self.api.students = [self.row(7002, email="Aziz@Example.com", phone="901234568")]
        self.api.relations = [{"EdUnitId": 14, "StudentClientId": 7002, "Status": "Normal", "EdUnitCorporative": False}]
        self.full_sync()
        existing.refresh_from_db()
        self.assertEqual(existing.profile.hollihop_client_id, 7002)
        self.assertEqual(existing.password, old_hash)
        self.assertFalse(existing.profile.hollihop_created)  # no SMS with a new password
        self.assertTrue(ClassroomMembership.objects.filter(user=existing, classroom__hollihop_edunit_id=14,
                                                           status="approved").exists())
        self.assertEqual(User.objects.filter(profile__hollihop_client_id=7002).count(), 1)

    def test_a_self_registered_account_is_never_linked_by_contact_data(self):
        # Anyone can type any email at sign-up; only the SMS-code flow may join accounts.
        squatter = User.objects.create_user("squatter", email="victim@example.com", password=PASSWORD)
        squatter.profile.self_registered = True
        squatter.profile.save()
        self.api.students = [self.row(7003, email="victim@example.com", phone="901234569")]
        self.api.relations = [{"EdUnitId": 14, "StudentClientId": 7003, "Status": "Normal", "EdUnitCorporative": False}]
        self.full_sync()
        squatter.refresh_from_db()
        self.assertIsNone(squatter.profile.hollihop_client_id)
        self.assertFalse(ClassroomMembership.objects.filter(user=squatter).exists())
        real = User.objects.get(profile__hollihop_client_id=7003)
        self.assertNotEqual(real.pk, squatter.pk)
        self.assertEqual(Classroom.objects.filter(hollihop_edunit_id=14).count(), 1)
