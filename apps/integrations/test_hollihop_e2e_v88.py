"""V88: Hollihop -> MakonBook end to end, with the production configuration.

Production runs HOLLIHOP_MODE=users and imports only LearningType=GROUP units, with the
Russian student statuses. The older suites mostly use mode=all without a LearningType
filter, so this file checks the real path: initial import, a repeated run, transfers,
students leaving, fired teachers, smart reconciliation and the student webhook.
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.integrations.hollihop.normalization import normalize_phone
from apps.integrations.hollihop.reconcile import (
    HollihopSmartReconciler,
    _student_needs_update,
    mark_initial_sync_completed,
)
from apps.integrations.hollihop.sync import HollihopSyncEngine, full_stage_set
from apps.integrations.hollihop.tasks import process_student_webhook
from apps.integrations.models import HollihopAttendance
from apps.integrations.tests import FakeHollihopClient
from apps.sat.models import Classroom, ClassroomMembership

PROD = dict(
    HOLLIHOP_ENABLED=True,
    SCHOOL_DATA_PROVIDER="hollihop",
    HOLLIHOP_MODE="users",
    HOLLIHOP_ALLOWED_LEARNING_TYPES=("GROUP",),
    HOLLIHOP_ACTIVE_STUDENT_STATUSES={"занимается", "active", "working"},
    HOLLIHOP_INACTIVE_STUDENT_STATUSES={"не занимается", "inactive", "archived", "архив", "закончил обучение"},
    HOLLIHOP_FALLBACK_TEACHER_USERNAME="",
    HOLLIHOP_CLASSROOM_TYPE="sat",
    HOLLIHOP_MANAGER_EMPLOYEE_IDS=set(),
    HOLLIHOP_AUTO_SEND_CREDENTIALS=False,
    HOLLIHOP_ATTENDANCE_CHUNK_DAYS=30,
    HOLLIHOP_RECENT_ATTENDANCE_DAYS=30,
    HOLLIHOP_ATTENDANCE_DELTA_DAYS=14,
)
TODAY = timezone.localdate()


def edunit(eid, name, teacher_ids, *, learning="GROUP", status="Working"):
    return {"Id": eid, "Name": name, "LearningType": learning, "Corporative": False, "_status": status,
            "ScheduleItems": [{"TeacherIds": list(teacher_ids)}]}


def rel(eid, cid, *, status="Normal", learning="GROUP", days=None):
    row = {"EdUnitId": eid, "StudentClientId": cid, "Status": status, "EdUnitLearningType": learning,
           "EdUnitCorporative": False}
    if days is not None:
        row["Days"] = days
    return row


def student(cid, first, *, phone="", email="", status="Занимается"):
    return {"ClientId": cid, "FirstName": first, "LastName": "Karimov", "MiddleName": "", "EMail": email,
            "Mobile": phone, "Status": status}


def teacher(tid, first, *, email="", phone="", fired=False):
    return {"Id": tid, "FirstName": first, "LastName": "Teacher", "MiddleName": "", "EMail": email,
            "Mobile": phone, "Status": "Работает", "Fired": fired}


@override_settings(**PROD)
class HollihopProductionFlowTests(TestCase):
    def setUp(self):
        self.api = api = FakeHollihopClient()
        api.teachers = [teacher(501, "Aziz", email="aziz@satmakon.uz"),
                        teacher(502, "Dilnoza", email="dilnoza@satmakon.uz")]
        api.edunits = [
            edunit(9001, "SAT Math A", [501]),
            edunit(9002, "SAT English B", [502]),
            edunit(9003, "IELTS Online", [501], learning="ONLINE"),
            edunit(9004, "SAT Old 2024", [501], status="Finished"),
        ]
        day1, day2 = (TODAY - timedelta(days=3)).isoformat(), (TODAY - timedelta(days=1)).isoformat()
        self.days = [{"Date": f"{day1}T00:00:00", "Pass": False, "ScheduleItemIds": [11]},
                     {"Date": f"{day2}T00:00:00", "Pass": True, "ScheduleItemIds": [11], "Description": "ill"}]
        api.students = [
            student(1001, "Malika", phone="+998 90 111 22 33"),
            student(1002, "Bekzod"),
            student(1003, "Sardor", status="Не занимается"),
            student(1004, "Online", phone="+998905550004"),
            student(1005, "Linked", phone="+998 90 777 66 55"),
            student(1006, "Kid", email="kid@example.com"),
            student(1007, "Alumni"),
        ]
        api.relations = [
            rel(9001, 1001, days=self.days), rel(9001, 1002), rel(9002, 1002), rel(9001, 1003),
            rel(9003, 1004, learning="ONLINE"), rel(9002, 1005), rel(9002, 1006), rel(9004, 1007),
        ]
        # An existing MakonBook teacher (matched by email) and an existing student (by phone).
        self.dilnoza = User.objects.create_user("ms_dilnoza", email="dilnoza@satmakon.uz", password="Teach-123")
        self.dilnoza.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        self.old_student = User.objects.create_user("old_student", password="Keep-me-1")
        self.old_student.profile.phone_number = normalize_phone("+998907776655")
        self.old_student.profile.save()
        # Someone signed up on the site with the email Hollihop has for student 1006.
        self.stranger = User.objects.create_user("self_signup", email="kid@example.com", password="x-12345678")
        self.stranger.profile.self_registered = True
        self.stranger.profile.save()

    def run_full(self):
        return HollihopSyncEngine(client=self.api).run(
            stages=full_stage_set(), date_from=TODAY - timedelta(days=10), date_to=TODAY)

    @staticmethod
    def user_for(cid):
        return User.objects.filter(profile__hollihop_client_id=cid).first()

    @staticmethod
    def members(edunit_id, status="approved"):
        return set(ClassroomMembership.objects.filter(
            classroom__hollihop_edunit_id=edunit_id, role="student", status=status,
        ).values_list("user__profile__hollihop_client_id", flat=True))

    # ------------------------------------------------------------------ initial import

    def test_only_studying_students_get_new_accounts(self):
        # V113: blank and unknown statuses are ignored just like "Не занимается".
        self.api.students += [student(1008, "Blank", status=""), student(1009, "Reserve", status="Резерв")]
        self.api.relations += [rel(9001, 1008), rel(9001, 1009)]
        summary = self.run_full()
        self.assertEqual(summary.errors, 0, summary.as_dict())
        self.assertIsNone(self.user_for(1008))
        self.assertIsNone(self.user_for(1009))
        self.assertNotIn(1008, self.members(9001))
        self.assertIn(1001, self.members(9001))
        # Once Hollihop marks the student as studying, the next sync creates the account.
        self.api.students[-1]["Status"] = "Занимается"
        self.run_full()
        self.assertIsNotNone(self.user_for(1009))
        self.assertIn(1009, self.members(9001))

    def test_initial_import_creates_the_right_people_classrooms_and_attendance(self):
        summary = self.run_full()
        self.assertEqual(summary.errors, 0, summary.as_dict())

        # Students: active GROUP students only.
        self.assertTrue(self.user_for(1001).username.startswith("hstu_"))
        self.assertIsNone(self.user_for(1003), "a student who no longer studies must not get a new account")
        self.assertIsNone(self.user_for(1004), "ONLINE-only students stay out of MakonBook")
        self.assertIsNone(self.user_for(1007), "students of a finished group stay out of MakonBook")
        new = self.user_for(1001)
        self.assertFalse(new.has_usable_password())
        self.assertEqual(new.profile.credentials_delivery_status, "pending")
        self.assertEqual(new.profile.phone_number, normalize_phone("+998901112233"))
        self.assertEqual(new.profile.hollihop_status, "Занимается")

        # The existing student is linked, not duplicated; the password is kept.
        linked = self.user_for(1005)
        self.assertEqual(linked.pk, self.old_student.pk)
        self.assertTrue(linked.check_password("Keep-me-1"))
        self.assertEqual(User.objects.filter(profile__phone_number=normalize_phone("+998907776655")).count(), 1)

        # A self-registered account is never taken over by contact data.
        self.stranger.refresh_from_db()
        self.assertIsNone(self.stranger.profile.hollihop_client_id)
        self.assertNotEqual(self.user_for(1006).pk, self.stranger.pk)

        # Teachers: new one created, existing one linked with its password.
        aziz = User.objects.get(profile__hollihop_teacher_id=501)
        self.assertTrue(aziz.username.startswith("hteach_"))
        self.assertTrue(aziz.groups.filter(name="Teacher").exists())
        self.dilnoza.refresh_from_db()
        self.assertEqual(self.dilnoza.profile.hollihop_teacher_id, 502)
        self.assertTrue(self.dilnoza.check_password("Teach-123"))

        # Classrooms: the two active GROUP units, each with its teacher.
        self.assertEqual(set(Classroom.objects.values_list("hollihop_edunit_id", flat=True)), {9001, 9002})
        math = Classroom.objects.get(hollihop_edunit_id=9001)
        self.assertEqual((math.name, math.teacher_id, math.is_active, math.classroom_type), ("SAT Math A", aziz.pk, True, "sat"))
        self.assertTrue(ClassroomMembership.objects.filter(classroom=math, user=aziz, role="teacher", status="approved").exists())
        self.assertEqual(Classroom.objects.get(hollihop_edunit_id=9002).teacher_id, self.dilnoza.pk)

        # Memberships.
        self.assertEqual(self.members(9001), {1001, 1002})
        self.assertEqual(self.members(9002), {1002, 1005, 1006})

        # Attendance: present + absent with the note, keyed per day.
        rows = HollihopAttendance.objects.filter(student=new).order_by("date")
        self.assertEqual([r.status for r in rows], [HollihopAttendance.STATUS_PRESENT, HollihopAttendance.STATUS_ABSENT])
        self.assertEqual(rows[1].description, "ill")
        self.assertTrue(all(r.classroom_id == math.pk for r in rows))

    def test_a_second_run_changes_nothing(self):
        self.run_full()
        counts = (User.objects.count(), Classroom.objects.count(), ClassroomMembership.objects.count(),
                  HollihopAttendance.objects.count())
        summary = self.run_full()
        self.assertEqual(summary.errors, 0)
        self.assertEqual((summary.students_created, summary.teachers_created, summary.classrooms_created,
                          summary.memberships_added, summary.attendance_created), (0, 0, 0, 0, 0))
        self.assertEqual(counts, (User.objects.count(), Classroom.objects.count(),
                                  ClassroomMembership.objects.count(), HollihopAttendance.objects.count()))

    # ------------------------------------------------------------------ changes in Hollihop

    def test_transfer_between_groups_and_a_student_who_stops(self):
        self.run_full()
        # Malika moves from Math A to English B; Bekzod stops studying altogether.
        self.api.relations = [r for r in self.api.relations if (r["EdUnitId"], r["StudentClientId"]) != (9001, 1001)]
        self.api.relations.append(rel(9002, 1001))
        for row in self.api.students:
            if row["ClientId"] == 1002:
                row["Status"] = "Не занимается"
        self.api.relations = [r if r["StudentClientId"] != 1002 else {**r, "Status": "Stopped"} for r in self.api.relations]
        summary = self.run_full()
        self.assertEqual(summary.errors, 0, summary.as_dict())
        self.assertEqual(self.members(9001), set())
        self.assertEqual(self.members(9002), {1001, 1005, 1006})
        self.assertEqual(self.members(9001, "removed"), {1001, 1002})
        self.assertFalse(self.user_for(1002).is_active)
        # History stays: Malika's attendance in Math A is still there.
        self.assertEqual(HollihopAttendance.objects.filter(student=self.user_for(1001)).count(), 2)

    def test_a_fired_teacher_loses_the_teacher_role(self):
        self.run_full()
        self.api.teachers[0]["Fired"] = True
        HollihopSyncEngine(client=self.api).run(stages={"teachers"})
        aziz = User.objects.get(profile__hollihop_teacher_id=501)
        self.assertFalse(aziz.groups.filter(name="Teacher").exists())
        self.assertFalse(aziz.is_active)

    def test_two_groups_with_the_same_name_and_teacher_stay_two_classrooms(self):
        # Hollihop often reuses a group name for a new intake with the same teacher.
        self.api.edunits.append(edunit(9005, "SAT Math A", [501]))
        self.api.relations.append(rel(9005, 1005))
        self.run_full()
        self.run_full()
        rows = dict(Classroom.objects.filter(name="SAT Math A").values_list("hollihop_edunit_id", "id"))
        self.assertEqual(set(rows), {9001, 9005})
        self.assertEqual(self.members(9001), {1001, 1002})
        self.assertEqual(self.members(9005), {1005})

    # ------------------------------------------------------------------ automatic paths

    def test_smart_reconciliation_picks_up_a_new_student(self):
        self.run_full()
        mark_initial_sync_completed()
        self.api.students.append(student(1008, "Newcomer", phone="+998901230008"))
        self.api.relations.append(rel(9002, 1008))
        with mock.patch("apps.integrations.hollihop.sync.HollihopClient", return_value=self.api):
            report, summary = HollihopSmartReconciler().run()
        self.assertEqual(summary.errors, 0, summary.as_dict())
        self.assertIsNotNone(self.user_for(1008))
        self.assertIn(1008, self.members(9002))

    def test_student_webhook_moves_the_student_and_imports_attendance(self):
        self.run_full()
        mark_initial_sync_completed()
        HollihopAttendance.objects.all().delete()
        self.api.relations = [r for r in self.api.relations if (r["EdUnitId"], r["StudentClientId"]) != (9001, 1001)]
        self.api.relations.append(rel(9002, 1001, days=self.days))
        with mock.patch("apps.integrations.hollihop.sync.HollihopClient", return_value=self.api):
            result = process_student_webhook("PassSet", 1001)
        self.assertEqual(result["status"], "ok", result)
        self.assertNotIn(1001, self.members(9001))
        self.assertIn(1001, self.members(9002))
        self.assertEqual(HollihopAttendance.objects.filter(student=self.user_for(1001)).count(), 2)

    def test_a_confirmed_login_email_is_not_resynced_every_cycle(self):
        # V84: a student who confirmed their own email keeps it as their login. The smart
        # sync must not treat Hollihop's (parent) email as a pending change forever.
        self.api.students[0]["EMail"] = "parent@example.com"
        self.run_full()
        user = self.user_for(1001)
        user.email = "malika@example.com"
        user.save(update_fields=["email"])
        user.profile.email_verified_at = timezone.now()
        user.profile.save()
        engine = HollihopSyncEngine(client=self.api)
        self.assertFalse(_student_needs_update(engine, self.api.students[0], User.objects.get(pk=user.pk)))
        engine.run(stages={"students"})
        user.refresh_from_db()
        self.assertEqual(user.email, "malika@example.com")

    def test_one_bad_teacher_row_does_not_stop_smart_sync(self):
        self.run_full()
        mark_initial_sync_completed()
        from apps.integrations.models import HollihopSyncState

        state = HollihopSyncState.objects.get(provider="hollihop")
        state.cursor_state = {**state.cursor_state, "teachers_checked_at": "2000-01-01T00:00:00+00:00"}
        state.save(update_fields=["cursor_state"])
        self.api.teachers[0]["FirstName"] = "Aziz-renamed"
        self.api.teachers[1]["FirstName"] = "Dilnoza-renamed"
        self.api.students.append(student(1009, "AfterTeachers"))
        self.api.relations.append(rel(9002, 1009))
        real = HollihopSyncEngine._sync_teacher

        def flaky(engine, data):
            if int(data["Id"]) == 501:
                raise ValueError("odd teacher payload")
            return real(engine, data)

        with mock.patch("apps.integrations.hollihop.sync.HollihopClient", return_value=self.api), \
                mock.patch.object(HollihopSyncEngine, "_sync_teacher", flaky):
            report, summary = HollihopSmartReconciler().run()
        self.assertEqual(summary.errors, 1)
        self.assertEqual(User.objects.get(profile__hollihop_teacher_id=502).first_name, "Dilnoza-renamed")
        self.assertIsNotNone(self.user_for(1009))
