"""V90: Hollihop group schedule -> lesson days for teacher assessments (AssessmentSchedule).

Hollihop API 2.0, GetEdUnits -> ScheduleItems[]: BeginDate, EndDate, Weekdays, TeacherIds.
Weekdays is a bit mask: Mon 1, Tue 2, Wed 4, Thu 8, Fri 16, Sat 32, Sun 64 (Mon/Wed = 5).

Rules (agreed with SATMakon):
* Hollihop is the source of truth for the days and the teacher of a Hollihop group; a
  manual schedule for that group is taken over and kept in sync.
* A new schedule lets the teacher assess at once, but fines stay off until a manager
  turns them on (fines_enabled). Manager calendar exceptions and fines already turned
  on are never touched.
* Start dates are never moved into the past (no back-dated obligations).
* When Hollihop has no current schedule for a group, MakonBook changes nothing.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.dateparse import parse_date

WEEKDAY_BITS = ((1, 1), (2, 2), (4, 3), (8, 4), (16, 5), (32, 6), (64, 7))


def weekdays_from_mask(value):
    """Hollihop bit mask -> ISO weekdays (Monday=1 .. Sunday=7)."""
    try:
        mask = int(value)
    except (TypeError, ValueError):
        return []
    return [iso for bit, iso in WEEKDAY_BITS if mask & bit]


def _date(value):
    text = str(value or "").strip()[:10]
    return parse_date(text) if text else None


def plan_for_edunit(data, *, today):
    """{hollihop_teacher_id | None: {"weekdays", "start", "end", "open"}} for current items."""
    plan = {}
    for item in data.get("ScheduleItems") or []:
        begin, end = _date(item.get("BeginDate")), _date(item.get("EndDate"))
        if end and end < today:
            continue  # this part of the schedule is over
        days = weekdays_from_mask(item.get("Weekdays"))
        if not days:
            continue
        teacher_ids = []
        for raw in item.get("TeacherIds") or []:
            try:
                teacher_ids.append(int(raw))
            except (TypeError, ValueError):
                continue
        for teacher_id in teacher_ids or [None]:
            entry = plan.setdefault(teacher_id, {"weekdays": set(), "start": None, "end": None, "open": False})
            entry["weekdays"].update(days)
            if begin and (entry["start"] is None or begin < entry["start"]):
                entry["start"] = begin
            if end is None:
                entry["open"] = True
            elif entry["end"] is None or end > entry["end"]:
                entry["end"] = end
    return plan


def sync_classroom_schedules(classroom, data, *, primary_teacher=None, now=None):
    """Create/update the classroom's lesson schedules from its Hollihop group. Returns a count."""
    from apps.ratings.models import AssessmentSchedule

    User = get_user_model()
    now = now or timezone.now()
    today = timezone.localdate(now)
    plan = plan_for_edunit(data, today=today)
    if not plan:
        return 0

    hollihop_ids = [teacher_id for teacher_id in plan if teacher_id is not None]
    users = {
        user.profile.hollihop_teacher_id: user
        for user in User.objects.filter(profile__hollihop_teacher_id__in=hollihop_ids).select_related("profile")
    }
    by_user = {}
    for teacher_id, entry in plan.items():
        user = primary_teacher if teacher_id is None else users.get(teacher_id)
        if user is None:
            continue
        merged = by_user.setdefault(user.pk, {"user": user, "weekdays": set(), "start": None, "end": None, "open": False})
        merged["weekdays"] |= entry["weekdays"]
        if entry["start"] and (merged["start"] is None or entry["start"] < merged["start"]):
            merged["start"] = entry["start"]
        merged["open"] = merged["open"] or entry["open"]
        if entry["end"] and (merged["end"] is None or entry["end"] > merged["end"]):
            merged["end"] = entry["end"]
    if not by_user:
        return 0  # the group's teachers are not in MakonBook yet: change nothing

    changed = 0
    kept = set()
    for item in by_user.values():
        weekdays = sorted(item["weekdays"])
        ends_on = None if item["open"] else item["end"]
        wanted_start = max(today, item["start"] or today)
        schedule = AssessmentSchedule.objects.filter(classroom=classroom, teacher=item["user"]).first()
        if schedule is None:
            schedule = AssessmentSchedule.objects.create(
                classroom=classroom, teacher=item["user"], weekdays=weekdays, starts_on=wanted_start,
                ends_on=ends_on, enabled=True, fines_enabled=False, hollihop_managed=True, hollihop_synced_at=now,
            )
            changed += 1
        else:
            fields = []
            if list(schedule.weekdays or []) != weekdays:
                schedule.weekdays = weekdays
                fields.append("weekdays")
            # A start still in the future follows Hollihop; a past start is history.
            if schedule.starts_on > today and schedule.starts_on != wanted_start and not schedule.obligations.exists():
                schedule.starts_on = wanted_start
                fields.append("starts_on")
            if ends_on and ends_on < schedule.starts_on:
                ends_on = schedule.starts_on
            if schedule.ends_on != ends_on:
                schedule.ends_on = ends_on
                fields.append("ends_on")
            if not schedule.enabled:
                schedule.enabled = True
                fields.append("enabled")
            if not schedule.hollihop_managed:
                schedule.hollihop_managed = True
                fields.append("hollihop_managed")
            schedule.hollihop_synced_at = now
            fields.append("hollihop_synced_at")
            schedule.save(update_fields=fields + ["updated_at"])
            if len(fields) > 1:
                changed += 1
        kept.add(schedule.pk)

    # A teacher who no longer teaches this group in Hollihop stops being scheduled.
    stale = AssessmentSchedule.objects.filter(classroom=classroom, enabled=True).exclude(pk__in=kept)
    for schedule in stale:
        schedule.enabled = False
        schedule.hollihop_synced_at = now
        schedule.save(update_fields=["enabled", "hollihop_synced_at", "updated_at"])
        changed += 1
    return changed
