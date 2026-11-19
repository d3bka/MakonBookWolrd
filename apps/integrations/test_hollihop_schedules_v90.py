"""V90: lesson days for teacher assessments come from the Hollihop group schedule."""
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.integrations.hollihop.schedules import weekdays_from_mask
from apps.integrations.hollihop.sync import HollihopSyncEngine
from apps.integrations.test_hollihop_e2e_v88 import PROD, rel, student, teacher
from apps.integrations.tests import FakeHollihopClient
from apps.ratings.assessment_policy import prepare_today_obligations, today_assessment_state
from apps.ratings.models import AssessmentCalendarException, AssessmentObligation, AssessmentSchedule
from apps.sat.models import Classroom, ClassroomMembership

TODAY = timezone.localdate()
EVERY_DAY = 127


def group(eid, name, *, items):
    return {"Id": eid, "Name": name, "LearningType": "GROUP", "Corporative": False, "_status": "Working",
            "ScheduleItems": items}


def item(weekdays, teacher_ids, *, begin=-60, end=200):
    return {"Id": 1, "BeginDate": f"{TODAY + timedelta(days=begin)} ", "EndDate": str(TODAY + timedelta(days=end)) if end is not None else "",
            "Weekdays": weekdays, "BeginTime": "14:00", "EndTime": "16:00", "TeacherIds": teacher_ids}


class MaskTests(TestCase):
    def test_hollihop_bit_mask(self):
        self.assertEqual(weekdays_from_mask(5), [1, 3])        # Mon/Wed, the example in the API docs
        self.assertEqual(weekdays_from_mask(10), [2, 4])       # Tue/Thu
        self.assertEqual(weekdays_from_mask(127), [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(weekdays_from_mask(64), [7])
        self.assertEqual(weekdays_from_mask(None), [])
        self.assertEqual(weekdays_from_mask("x"), [])


@override_settings(**PROD)
class ScheduleFromHollihopTests(TestCase):
    def setUp(self):
        self.api = FakeHollihopClient()
        self.api.teachers = [teacher(501, "Aziz", email="aziz@satmakon.uz"), teacher(502, "Dilnoza", email="dil@satmakon.uz")]
        self.api.edunits = [group(9001, "SAT Math A", items=[item(5, [501])])]
        self.api.students = [student(1001, "Malika")]
        self.api.relations = [rel(9001, 1001)]

    def sync(self):
        summary = HollihopSyncEngine(client=self.api).run(stages={"teachers", "students", "classrooms", "memberships"})
        self.assertEqual(summary.errors, 0, summary.as_dict())

    def schedule(self, teacher_id=501):
        return AssessmentSchedule.objects.get(classroom__hollihop_edunit_id=9001, teacher__profile__hollihop_teacher_id=teacher_id)

    def test_sync_creates_the_schedule_with_fines_off(self):
        self.sync()
        schedule = self.schedule()
        self.assertEqual(schedule.weekdays, [1, 3])
        self.assertEqual((schedule.enabled, schedule.fines_enabled, schedule.hollihop_managed), (True, False, True))
        self.assertEqual(schedule.starts_on, TODAY, "never back-dated")
        self.assertEqual(schedule.ends_on, TODAY + timedelta(days=200))

    def test_teachers_assess_at_once_but_fines_wait_for_the_manager(self):
        self.api.edunits[0]["ScheduleItems"] = [item(EVERY_DAY, [501])]
        self.sync()
        schedule = self.schedule()
        ClassroomMembership.objects.filter(classroom=schedule.classroom).update(approved_at=timezone.now() - timedelta(days=5))
        _, allowed, required = today_assessment_state(schedule.classroom, schedule.teacher)
        self.assertEqual((allowed, required), (True, False))
        self.assertEqual(prepare_today_obligations(), 0)

        manager = User.objects.create_user("v90_manager", password="x")
        manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.client.force_login(manager)
        self.client.post(reverse("manager_schedule_fines_all"))
        schedule.refresh_from_db()
        self.assertEqual((schedule.fines_enabled, schedule.fines_from), (True, TODAY + timedelta(days=1)))
        self.assertEqual(prepare_today_obligations(), 0, "turning fines on never fines today's lesson")
        # The next day the lesson is mandatory.
        AssessmentSchedule.objects.filter(pk=schedule.pk).update(fines_from=TODAY)
        self.assertEqual(prepare_today_obligations(), 1)
        self.assertTrue(AssessmentObligation.objects.filter(schedule=schedule, lesson_date=TODAY).exists())

    def test_hollihop_changes_update_days_and_keep_exceptions_and_fines(self):
        self.sync()
        schedule = self.schedule()
        AssessmentSchedule.objects.filter(pk=schedule.pk).update(fines_enabled=True)
        AssessmentCalendarException.objects.create(schedule=schedule, date=TODAY + timedelta(days=3), action="cancelled", reason="Holiday")
        self.api.edunits[0]["ScheduleItems"] = [item(10, [501], end=None)]
        self.sync()
        schedule.refresh_from_db()
        self.assertEqual((schedule.weekdays, schedule.ends_on, schedule.fines_enabled), ([2, 4], None, True))
        self.assertEqual(schedule.exceptions.count(), 1)

    def test_a_new_teacher_takes_over_and_the_old_schedule_stops(self):
        self.sync()
        self.api.edunits[0]["ScheduleItems"] = [item(5, [502])]
        self.sync()
        self.assertFalse(self.schedule(501).enabled)
        new = self.schedule(502)
        self.assertEqual((new.enabled, new.fines_enabled, new.weekdays), (True, False, [1, 3]))

    def test_a_manual_schedule_of_a_hollihop_group_follows_hollihop(self):
        # The group has a teacher but no lesson days in Hollihop yet.
        self.api.edunits[0]["ScheduleItems"] = [item(0, [501])]
        self.sync()
        classroom = Classroom.objects.get(hollihop_edunit_id=9001)
        aziz = User.objects.get(profile__hollihop_teacher_id=501)
        manual = AssessmentSchedule.objects.create(classroom=classroom, teacher=aziz, weekdays=[6], starts_on=TODAY)
        self.sync()  # still no schedule in Hollihop: the manual one is untouched
        manual.refresh_from_db()
        self.assertEqual((manual.weekdays, manual.hollihop_managed), ([6], False))
        self.api.edunits[0]["ScheduleItems"] = [item(5, [501])]
        self.sync()
        manual.refresh_from_db()
        self.assertEqual((manual.weekdays, manual.hollihop_managed, manual.fines_enabled), ([1, 3], True, True))

    def test_finished_items_are_ignored_and_items_without_teacher_use_the_group_teacher(self):
        self.api.edunits[0]["ScheduleItems"] = [item(64, [501], begin=-300, end=-10), item(16, [])]
        self.sync()
        self.assertEqual(self.schedule().weekdays, [5])

    def test_manager_page_shows_hollihop_schedules_and_keeps_the_form_for_other_classrooms(self):
        self.sync()
        Classroom.objects.create(name="Manual group", teacher=User.objects.get(profile__hollihop_teacher_id=501))
        manager = User.objects.create_user("v90_boss", password="x")
        manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.client.force_login(manager)
        response = self.client.get(reverse("manager_assessment_schedules"))
        self.assertContains(response, "From Hollihop")
        self.assertContains(response, "Mon, Wed")
        self.assertContains(response, "Assessing · fines off")
        self.assertContains(response, "Turn fines on for all (1)")
        self.assertEqual([c.name for c in response.context["classrooms"]], ["Manual group"])
        schedule = self.schedule()
        self.client.post(reverse("manager_schedule_fines", args=[schedule.pk]), {"fines": "on"})
        schedule.refresh_from_db()
        self.assertTrue(schedule.fines_enabled)
        self.client.post(reverse("manager_schedule_fines", args=[schedule.pk]), {"fines": "off"})
        schedule.refresh_from_db()
        self.assertFalse(schedule.fines_enabled)

    def test_only_managers_switch_fines(self):
        self.sync()
        kid = User.objects.create_user("v90_kid", password="x")
        self.client.force_login(kid)
        response = self.client.post(reverse("manager_schedule_fines", args=[self.schedule().pk]), {"fines": "on"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.schedule().fines_enabled)

    def test_dry_run_writes_no_schedule(self):
        HollihopSyncEngine(client=self.api, dry_run=True).run(stages={"teachers", "students", "classrooms"})
        self.assertFalse(AssessmentSchedule.objects.exists())
