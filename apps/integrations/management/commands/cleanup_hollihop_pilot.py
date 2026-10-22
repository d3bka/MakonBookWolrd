from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from apps.integrations.hollihop.client import HollihopClient, HollihopConfigurationError, HollihopError
from apps.integrations.hollihop.sync import HollihopSyncEngine
from apps.integrations.management.commands.pilot_hollihop_user import (
    PilotTarget,
    _configured_targets,
    _detect_identity,
    _parse_targets,
    _profile_for,
)
from apps.integrations.models import (
    HollihopAttendance,
    HollihopCredentialDelivery,
    HollihopSyncConflict,
    HollihopSyncLog,
    HollihopSyncState,
)


@dataclass
class CleanupStats:
    users_deleted: int = 0
    existing_users_preserved: int = 0
    deliveries_deleted: int = 0
    logs_deleted: int = 0
    conflicts_deleted: int = 0
    attendance_deleted: int = 0
    missing_accounts: int = 0


class Command(BaseCommand):
    help = (
        "Safely remove controlled Hollihop pilot artifacts. By default this is a dry-run. "
        "Use --apply to delete only accounts marked hollihop_created=True plus pilot integration metadata."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--targets",
            default="",
            help=(
                "Optional comma-separated targets overriding .env, e.g. "
                "student:37,student:8,manager:12557."
            ),
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually delete pilot-created accounts and matching integration metadata.",
        )
        parser.add_argument(
            "--reset-state",
            action="store_true",
            help="Also delete the HollihopSyncState row. Allowed only while SCHOOL_DATA_PROVIDER=local.",
        )

    def handle(self, *args, **options):
        if str(getattr(settings, "SCHOOL_DATA_PROVIDER", "local")).strip().lower() != "local":
            raise CommandError(
                "Cleanup is blocked while SCHOOL_DATA_PROVIDER is not local. "
                "Do not run pilot cleanup against an active full Hollihop integration."
            )
        if not getattr(settings, "HOLLIHOP_PILOT_ENABLED", False):
            raise CommandError("Pilot cleanup requires HOLLIHOP_PILOT_ENABLED=true.")
        if not getattr(settings, "HOLLIHOP_ENABLED", False):
            raise CommandError("HOLLIHOP_ENABLED=true is required to resolve pilot identities safely.")

        raw_targets = str(options.get("targets") or "").strip()
        if raw_targets:
            targets = _parse_targets(raw_targets, default_kind="auto")
        else:
            targets = _configured_targets()
        if not targets:
            raise CommandError("No pilot targets configured. Use --targets or HOLLIHOP_PILOT_TARGETS.")

        apply_changes = bool(options["apply"])
        reset_state = bool(options["reset_state"])

        try:
            client = HollihopClient()
        except HollihopConfigurationError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.MIGRATE_HEADING("Hollihop pilot cleanup"))
        self.stdout.write(f"Targets: {', '.join(target.label for target in targets)}")
        self.stdout.write(f"Mode: {'APPLY' if apply_changes else 'DRY RUN'}")
        self.stdout.write("Only users with UserProfile.hollihop_created=True are eligible for account deletion.")

        stats = CleanupStats()
        errors: list[str] = []

        for index, target in enumerate(targets, start=1):
            self.stdout.write("")
            self.stdout.write(self.style.HTTP_INFO(f"[{index}/{len(targets)}] {target.label}"))
            try:
                engine = HollihopSyncEngine(client=client, dry_run=True, send_credentials=False)
                identity = _detect_identity(client, engine, target.requested_id, target.kind)
                self._cleanup_identity(identity, stats, apply_changes=apply_changes)
            except (HollihopError, ValueError, CommandError) as exc:
                message = f"{target.label}: {exc}"
                errors.append(message)
                self.stderr.write(self.style.ERROR(message))
            except Exception as exc:
                message = f"{target.label}: unexpected {type(exc).__name__}: {exc}"
                errors.append(message)
                self.stderr.write(self.style.ERROR(message))

        if reset_state:
            state_qs = HollihopSyncState.objects.filter(provider="hollihop")
            count = state_qs.count()
            self.stdout.write("")
            self.stdout.write(f"Hollihop sync state rows: {count}")
            if apply_changes and count:
                state_qs.delete()
                self.stdout.write(self.style.SUCCESS("Hollihop sync state reset."))
            elif count:
                self.stdout.write("Would reset Hollihop sync state.")

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Cleanup summary"))
        self.stdout.write(f"Pilot-created users deleted: {stats.users_deleted}")
        self.stdout.write(f"Existing MakonBook users preserved: {stats.existing_users_preserved}")
        self.stdout.write(f"Credential delivery rows deleted: {stats.deliveries_deleted}")
        self.stdout.write(f"Sync log rows deleted: {stats.logs_deleted}")
        self.stdout.write(f"Conflict rows deleted: {stats.conflicts_deleted}")
        self.stdout.write(f"Attendance rows deleted: {stats.attendance_deleted}")
        self.stdout.write(f"No MakonBook account: {stats.missing_accounts}")
        self.stdout.write(f"Errors: {len(errors)}")

        if not apply_changes:
            self.stdout.write(self.style.WARNING("DRY RUN only. Nothing was deleted."))
            self.stdout.write("Run again with --apply after reviewing the output.")
        else:
            self.stdout.write(self.style.SUCCESS("Pilot cleanup applied."))

        if errors:
            raise CommandError(
                f"Cleanup completed with {len(errors)} target error(s). Review the per-target messages above."
            )

    def _cleanup_identity(self, identity, stats: CleanupStats, *, apply_changes: bool) -> None:
        profile = _profile_for(identity)
        user = profile.user if profile else None
        external_id = str(identity.external_id)

        delivery_qs = HollihopCredentialDelivery.objects.filter(user=user) if user else HollihopCredentialDelivery.objects.none()
        log_q = Q(entity_type=identity.kind, external_id=external_id)
        if user:
            log_q |= Q(user=user)
        log_qs = HollihopSyncLog.objects.filter(log_q)
        conflict_qs = HollihopSyncConflict.objects.filter(
            external_type=identity.kind,
            external_id=external_id,
        )
        attendance_qs = HollihopAttendance.objects.filter(student=user) if user and identity.kind == "student" else HollihopAttendance.objects.none()

        deliveries = delivery_qs.count()
        logs = log_qs.count()
        conflicts = conflict_qs.count()
        attendance = attendance_qs.count()

        self.stdout.write(f"Detected type: {identity.kind}")
        self.stdout.write(f"Name: {identity.display_name}")
        self.stdout.write(f"Canonical Hollihop ID: {external_id}")
        self.stdout.write(f"MakonBook account: {'YES' if user else 'NO'}")
        if profile:
            self.stdout.write(f"Created by Hollihop: {'YES' if profile.hollihop_created else 'NO'}")
        self.stdout.write(
            f"Artifacts: deliveries={deliveries}, logs={logs}, conflicts={conflicts}, attendance={attendance}"
        )

        if not profile:
            stats.missing_accounts += 1
            if apply_changes:
                deleted_logs, _ = log_qs.delete()
                deleted_conflicts, _ = conflict_qs.delete()
                stats.logs_deleted += deleted_logs
                stats.conflicts_deleted += deleted_conflicts
            return

        if not profile.hollihop_created:
            # Never delete or mutate a pre-existing MakonBook user during pilot cleanup.
            stats.existing_users_preserved += 1
            self.stdout.write(self.style.WARNING(
                "Existing MakonBook user was matched by Hollihop. Account and profile were preserved."
            ))
            if apply_changes:
                deleted_logs, _ = log_qs.delete()
                deleted_conflicts, _ = conflict_qs.delete()
                deleted_deliveries, _ = delivery_qs.delete()
                stats.logs_deleted += deleted_logs
                stats.conflicts_deleted += deleted_conflicts
                stats.deliveries_deleted += deleted_deliveries
            return

        if not apply_changes:
            self.stdout.write(self.style.WARNING(
                f"Would delete pilot-created MakonBook user {user.get_username()!r} (id={user.id}) and dependent rows."
            ))
            return

        with transaction.atomic():
            # Count/delete explicit integration metadata first. Remaining rows tied to
            # the user (profile, attendance, reset codes, memberships, etc.) then
            # follow normal Django FK cascade rules when the pilot-created User is deleted.
            deleted_deliveries, _ = delivery_qs.delete()
            deleted_logs, _ = log_qs.delete()
            deleted_conflicts, _ = conflict_qs.delete()
            deleted_attendance, _ = attendance_qs.delete()
            stats.deliveries_deleted += deleted_deliveries
            stats.logs_deleted += deleted_logs
            stats.conflicts_deleted += deleted_conflicts
            stats.attendance_deleted += deleted_attendance
            username = user.get_username()
            user.delete()
            stats.users_deleted += 1
            self.stdout.write(self.style.SUCCESS(f"Deleted pilot-created MakonBook user {username!r}."))
