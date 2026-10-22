import copy
import os

from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from django.db.models import Q

from apps.base.models import UserProfile
from apps.sat.models import (
    English_Question,
    GlobalEvent,
    Math_Question,
    QuestionDomain,
    QuestionType,
    SupportLessonTitle,
    SupportLessonTopic,
    SupportTeacherAvailability,
    SupportTeacherProfile,
    SupportTeacherProfileSection,
    Test,
)


ROLE_GROUPS = (
    "Admin",
    "Tester",
    "Manager",
    "Teacher",
    "Support Teacher",
)
SOURCE_ALIAS = "prod_seed"


def _env(name, default=""):
    return os.getenv(name, default).strip()


def _is_loopback(host):
    return host.strip().lower() in {"127.0.0.1", "localhost", "::1"}


def _field_value(obj, field):
    value = getattr(obj, field.attname)
    # FileField/ImageField values must stay as storage keys; do not download/upload media.
    if hasattr(value, "name") and hasattr(field, "upload_to"):
        return value.name
    return value


def _scalar_defaults(obj, *, exclude=()):
    excluded = set(exclude)
    data = {}
    for field in obj._meta.concrete_fields:
        if field.primary_key or field.name in excluded or field.attname in excluded:
            continue
        data[field.attname] = _field_value(obj, field)
    return data


def _copy_by_pk(model, source_obj, *, exclude=(), overrides=None):
    defaults = _scalar_defaults(source_obj, exclude=exclude)
    if overrides:
        defaults.update(overrides)
    target, _ = model.objects.using("default").update_or_create(
        pk=source_obj.pk,
        defaults=defaults,
    )
    return target


def _permission_key(permission):
    ct = permission.content_type
    return (ct.app_label, ct.model, permission.codename)


class Command(BaseCommand):
    help = (
        "Copy a safe development seed from production into the LOCAL default database: "
        "staff/roles, support-teacher profiles, SAT tests/questions, and GlobalEvent configs. "
        "Student accounts, attempts, reviews, guest participants/answers, classrooms, and bookings are not copied."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Connect to both databases, show counts, but write nothing.",
        )
        parser.add_argument(
            "--force-unsafe-target",
            action="store_true",
            help="Bypass the local-target safety check. Normally never needed.",
        )
        parser.add_argument(
            "--preserve-password-hashes",
            action="store_true",
            help="Copy production password hashes for staff. Not recommended; default resets to LOCAL_STAFF_PASSWORD.",
        )

    def _configure_source(self):
        required = {
            "PROD_SNAPSHOT_DB_NAME": _env("PROD_SNAPSHOT_DB_NAME"),
            "PROD_SNAPSHOT_DB_USER": _env("PROD_SNAPSHOT_DB_USER"),
            "PROD_SNAPSHOT_DB_PASSWORD": _env("PROD_SNAPSHOT_DB_PASSWORD"),
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise CommandError("Missing source settings: " + ", ".join(missing))

        host = _env("PROD_SNAPSHOT_HOST", "127.0.0.1")
        port = _env("PROD_SNAPSHOT_PORT", "5434")
        sslmode = _env("PROD_SNAPSHOT_DB_SSLMODE", "disable")

        source = copy.deepcopy(settings.DATABASES["default"])
        source.update(
            {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": required["PROD_SNAPSHOT_DB_NAME"],
                "USER": required["PROD_SNAPSHOT_DB_USER"],
                "PASSWORD": required["PROD_SNAPSHOT_DB_PASSWORD"],
                "HOST": host,
                "PORT": port,
                "CONN_MAX_AGE": 0,
                "CONN_HEALTH_CHECKS": True,
                "OPTIONS": {"sslmode": sslmode} if sslmode else {},
            }
        )
        # TEST is irrelevant for this read-only source alias but Django expects a dict.
        source["TEST"] = source.get("TEST") or {}
        connections.databases[SOURCE_ALIAS] = source
        connections[SOURCE_ALIAS].ensure_connection()

    def _assert_safe_target(self, force=False):
        target = connections.databases["default"]
        host = str(target.get("HOST") or "")
        port = str(target.get("PORT") or "")
        engine = str(target.get("ENGINE") or "")
        if force:
            return
        if engine != "django.db.backends.postgresql":
            raise CommandError(
                f"Refusing target ENGINE={engine!r}. Use the dedicated local PostgreSQL snapshot database."
            )
        if not _is_loopback(host):
            raise CommandError(
                f"REFUSING TO WRITE: default DB host is {host!r}, not loopback. "
                "Set DB_HOST=127.0.0.1 and DB_PORT=5433 first."
            )
        if port != "5433":
            raise CommandError(
                f"REFUSING TO WRITE: default DB port is {port!r}; expected dedicated snapshot port 5433."
            )

    def _source_staff(self):
        return (
            User.objects.using(SOURCE_ALIAS)
            .filter(
                Q(is_staff=True)
                | Q(is_superuser=True)
                | Q(groups__name__in=ROLE_GROUPS)
            )
            .distinct()
            .order_by("id")
        )

    def _plan_counts(self):
        staff = self._source_staff()
        return {
            "staff_users": staff.count(),
            "tests": Test.objects.using(SOURCE_ALIAS).count(),
            "english_questions": English_Question.objects.using(SOURCE_ALIAS).count(),
            "math_questions": Math_Question.objects.using(SOURCE_ALIAS).count(),
            "events": GlobalEvent.objects.using(SOURCE_ALIAS).count(),
            "support_profiles": SupportTeacherProfile.objects.using(SOURCE_ALIAS).filter(
                user_id__in=staff.values_list("id", flat=True)
            ).count(),
        }

    def _copy_groups(self, staff_ids):
        names = set(
            Group.objects.using(SOURCE_ALIAS)
            .filter(user__id__in=staff_ids)
            .values_list("name", flat=True)
        )
        names.update(
            Group.objects.using(SOURCE_ALIAS)
            .filter(tests__isnull=False)
            .values_list("name", flat=True)
        )
        names.update(ROLE_GROUPS)

        source_groups = Group.objects.using(SOURCE_ALIAS).filter(name__in=names).order_by("name")
        local_by_name = {}
        for src_group in source_groups:
            local_group, _ = Group.objects.using("default").get_or_create(name=src_group.name)
            local_by_name[src_group.name] = local_group

            local_permissions = []
            for src_perm in src_group.permissions.using(SOURCE_ALIAS).select_related("content_type"):
                app_label, model, codename = _permission_key(src_perm)
                local_perm = (
                    Permission.objects.using("default")
                    .filter(
                        content_type__app_label=app_label,
                        content_type__model=model,
                        codename=codename,
                    )
                    .first()
                )
                if local_perm:
                    local_permissions.append(local_perm)
            local_group.permissions.set(local_permissions)
        return local_by_name

    def _copy_staff(self, source_staff, local_groups, preserve_password_hashes=False):
        local_password = _env("LOCAL_STAFF_PASSWORD")
        if not preserve_password_hashes and not local_password:
            raise CommandError(
                "LOCAL_STAFF_PASSWORD is empty. Set a LOCAL-ONLY password or use --preserve-password-hashes explicitly."
            )

        staff_ids = set(source_staff.values_list("id", flat=True))
        for src in source_staff:
            defaults = {
                "username": src.username,
                "first_name": src.first_name,
                "last_name": src.last_name,
                "email": src.email,
                "is_staff": src.is_staff,
                "is_active": src.is_active,
                "is_superuser": src.is_superuser,
                "last_login": src.last_login,
                "date_joined": src.date_joined,
                "password": src.password if preserve_password_hashes else "!",
            }
            local, _ = User.objects.using("default").update_or_create(pk=src.pk, defaults=defaults)
            if not preserve_password_hashes:
                local.set_password(local_password)
                local.save(using="default", update_fields=["password"])

            group_names = list(src.groups.using(SOURCE_ALIAS).values_list("name", flat=True))
            local.groups.set([local_groups[name] for name in group_names if name in local_groups])

            local_user_permissions = []
            for src_perm in src.user_permissions.using(SOURCE_ALIAS).select_related("content_type"):
                app_label, model, codename = _permission_key(src_perm)
                local_perm = (
                    Permission.objects.using("default")
                    .filter(
                        content_type__app_label=app_label,
                        content_type__model=model,
                        codename=codename,
                    )
                    .first()
                )
                if local_perm:
                    local_user_permissions.append(local_perm)
            local.user_permissions.set(local_user_permissions)

            src_profile = UserProfile.objects.using(SOURCE_ALIAS).filter(user_id=src.pk).first()
            if src_profile:
                profile_defaults = _scalar_defaults(src_profile, exclude={"user", "created_at", "updated_at"})
                UserProfile.objects.using("default").update_or_create(
                    user_id=src.pk,
                    defaults=profile_defaults,
                )

        # Support-teacher public profiles and their display configuration only.
        src_support_profiles = SupportTeacherProfile.objects.using(SOURCE_ALIAS).filter(user_id__in=staff_ids)
        support_ids = []
        for src_profile in src_support_profiles:
            created_by_id = src_profile.created_by_id if src_profile.created_by_id in staff_ids else None
            _copy_by_pk(
                SupportTeacherProfile,
                src_profile,
                exclude={"user", "created_by"},
                overrides={"user_id": src_profile.user_id, "created_by_id": created_by_id},
            )
            support_ids.append(src_profile.pk)

        for section in SupportTeacherProfileSection.objects.using(SOURCE_ALIAS).filter(profile_id__in=support_ids):
            _copy_by_pk(SupportTeacherProfileSection, section)
        for availability in SupportTeacherAvailability.objects.using(SOURCE_ALIAS).filter(teacher_id__in=support_ids):
            _copy_by_pk(SupportTeacherAvailability, availability)

        # Static support-lesson taxonomy is useful in staff UI but no bookings/sessions are copied.
        for title in SupportLessonTitle.objects.using(SOURCE_ALIAS).all():
            _copy_by_pk(SupportLessonTitle, title)
        for topic in SupportLessonTopic.objects.using(SOURCE_ALIAS).all():
            _copy_by_pk(SupportLessonTopic, topic)

    def _copy_tests(self, local_groups):
        for domain in QuestionDomain.objects.using(SOURCE_ALIAS).all().order_by("id"):
            _copy_by_pk(QuestionDomain, domain)
        for qtype in QuestionType.objects.using(SOURCE_ALIAS).all().order_by("id"):
            _copy_by_pk(QuestionType, qtype)

        for src_test in Test.objects.using(SOURCE_ALIAS).all().order_by("name"):
            local_test = _copy_by_pk(Test, src_test)
            group_names = list(src_test.groups.using(SOURCE_ALIAS).values_list("name", flat=True))
            local_test.groups.set([local_groups[name] for name in group_names if name in local_groups])

        for question in English_Question.objects.using(SOURCE_ALIAS).all().order_by("id"):
            _copy_by_pk(English_Question, question)
        for question in Math_Question.objects.using(SOURCE_ALIAS).all().order_by("id"):
            _copy_by_pk(Math_Question, question)

    def _copy_events(self):
        # Config only: deliberately excludes GuestParticipant, GlobalEventAttempt,
        # GlobalEventModuleDraft and GlobalEventAnswer.
        for event in GlobalEvent.objects.using(SOURCE_ALIAS).all().order_by("id"):
            _copy_by_pk(GlobalEvent, event)

    def handle(self, *args, **options):
        self._assert_safe_target(force=options["force_unsafe_target"])
        self._configure_source()

        target = connections.databases["default"]
        source = connections.databases[SOURCE_ALIAS]
        self.stdout.write(
            f"TARGET  {target.get('HOST')}:{target.get('PORT')}/{target.get('NAME')} (LOCAL snapshot)"
        )
        self.stdout.write(
            f"SOURCE  {source.get('HOST')}:{source.get('PORT')}/{source.get('NAME')} (production via tunnel)"
        )

        counts = self._plan_counts()
        for key, value in counts.items():
            self.stdout.write(f"{key}: {value}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run only; no local rows changed."))
            return

        source_staff = self._source_staff()
        staff_ids = list(source_staff.values_list("id", flat=True))

        with transaction.atomic(using="default"):
            local_groups = self._copy_groups(staff_ids)
            self._copy_staff(
                source_staff,
                local_groups,
                preserve_password_hashes=options["preserve_password_hashes"],
            )
            self._copy_tests(local_groups)
            self._copy_events()

        self.stdout.write(self.style.SUCCESS("Local production-like snapshot seed completed."))
        self.stdout.write(
            "Excluded on purpose: students, classrooms, attempts, reviews/results, guest participants, "
            "event answers/drafts, support bookings/sessions/reviews, notifications and gamification."
        )
