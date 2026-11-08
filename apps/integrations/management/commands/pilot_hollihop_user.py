from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.base.models import UserProfile
from apps.integrations.hollihop.client import HollihopClient, HollihopConfigurationError, HollihopError
from apps.integrations.hollihop.credentials import deliver_new_temporary_access
from apps.integrations.hollihop.normalization import normalize_phone, safe_text
from apps.integrations.hollihop.sync import HollihopSyncAlreadyRunning, HollihopSyncEngine


SUPPORTED_KINDS = {"auto", "student", "teacher", "manager"}


@dataclass(frozen=True)
class PilotTarget:
    requested_id: int
    kind: str = "auto"

    @property
    def label(self) -> str:
        return f"{self.kind}:{self.requested_id}" if self.kind != "auto" else str(self.requested_id)


@dataclass(frozen=True)
class PilotIdentity:
    kind: str
    requested_id: int
    external_id: int
    payload: dict

    @property
    def display_name(self) -> str:
        first = safe_text(self.payload.get("FirstName"), 150)
        last = safe_text(self.payload.get("LastName"), 150)
        middle = safe_text(self.payload.get("MiddleName"), 150)
        return " ".join(part for part in [first, last, middle] if part).strip() or f"{self.kind.title()} #{self.requested_id}"

    @property
    def phone(self) -> str:
        return normalize_phone(self.payload.get("Mobile") or self.payload.get("Phone"))


def _as_positive_int(value, field_name: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Hollihop returned an invalid {field_name}: {value!r}.") from exc
    if number <= 0:
        raise ValueError(f"Hollihop returned an invalid {field_name}: {value!r}.")
    return number


def _exact_rows(rows, *, field: str, requested_id: int, entity_label: str) -> list[dict]:
    """Never trust upstream filtering blindly; accept only exact ID matches."""
    exact = []
    for row in rows or []:
        try:
            row_id = int(row.get(field))
        except (TypeError, ValueError):
            continue
        if row_id == requested_id:
            exact.append(row)
    if len(exact) > 1:
        raise ValueError(f"Hollihop returned multiple exact {entity_label} records for ID #{requested_id}.")
    return exact


def _detect_identity(client: HollihopClient, engine: HollihopSyncEngine, requested_id: int, forced_kind: str) -> PilotIdentity:
    matches: list[PilotIdentity] = []

    # Important: the ID shown in Hollihop UI for a student is Students[].Id.
    # Students[].ClientId is a different identifier used by relations/sync.
    if forced_kind in {"auto", "student"}:
        rows = client.get_students(student_id=requested_id)
        rows = _exact_rows(rows, field="Id", requested_id=requested_id, entity_label="Student")
        if rows:
            row = rows[0]
            client_id = _as_positive_int(row.get("ClientId"), "Student.ClientId")
            matches.append(PilotIdentity("student", requested_id, client_id, row))

    if forced_kind in {"auto", "teacher"}:
        rows = client.get_teachers(teacher_id=requested_id)
        rows = _exact_rows(rows, field="Id", requested_id=requested_id, entity_label="Teacher")
        if rows:
            row = rows[0]
            teacher_id = _as_positive_int(row.get("Id"), "Teacher.Id")
            matches.append(PilotIdentity("teacher", requested_id, teacher_id, row))

    if forced_kind in {"auto", "manager"}:
        rows = client.get_employees(employee_id=requested_id, corporative=None)
        rows = _exact_rows(rows, field="Id", requested_id=requested_id, entity_label="Employee")
        if rows:
            row = rows[0]
            employee_id = _as_positive_int(row.get("Id"), "Employee.Id")
            if engine._employee_is_manager(row):
                matches.append(PilotIdentity("manager", requested_id, employee_id, row))
            elif forced_kind == "manager":
                role_values = ", ".join(engine._employee_role_values(row)) or "none"
                raise ValueError(
                    f"Hollihop Employee #{requested_id} exists but is not manager-eligible. "
                    f"Role/type/position values: {role_values}."
                )

    if not matches:
        raise ValueError(
            f"No supported Hollihop Student, Teacher, or manager-eligible Employee was found for ID #{requested_id}."
        )
    if len(matches) > 1:
        kinds = ", ".join(item.kind for item in matches)
        raise ValueError(
            f"Hollihop ID #{requested_id} exists in multiple identity namespaces: {kinds}. "
            "Use HOLLIHOP_PILOT_TARGETS with an explicit prefix, for example "
            f"student:{requested_id}, teacher:{requested_id}, or manager:{requested_id}."
        )
    return matches[0]


def _profile_for(identity: PilotIdentity):
    if identity.kind == "student":
        return UserProfile.objects.select_related("user").filter(hollihop_client_id=identity.external_id).first()
    if identity.kind == "teacher":
        return UserProfile.objects.select_related("user").filter(hollihop_teacher_id=identity.external_id).first()
    return UserProfile.objects.select_related("user").filter(hollihop_employee_id=identity.external_id).first()


def _normalize_ids(value) -> list[int]:
    """Accept tuple/list/int/string so override_settings and old V5573 env both work."""
    if value is None:
        return []
    if isinstance(value, int):
        return [value] if value > 0 else []
    if isinstance(value, str):
        raw_items = value.split(",")
    else:
        try:
            raw_items = list(value)
        except TypeError:
            raw_items = [value]

    result: list[int] = []
    seen: set[int] = set()
    for raw in raw_items:
        if isinstance(raw, str):
            pieces = raw.split(",")
        else:
            pieces = [raw]
        for piece in pieces:
            text = str(piece).strip()
            if not text:
                continue
            try:
                number = int(text)
            except (TypeError, ValueError) as exc:
                raise CommandError(f"Invalid Hollihop pilot ID {text!r}; use positive integers separated by commas.") from exc
            if number <= 0:
                continue
            if number not in seen:
                seen.add(number)
                result.append(number)
    return result


def _parse_targets(raw_value, *, default_kind: str) -> list[PilotTarget]:
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        tokens = raw_value.split(",")
    else:
        try:
            tokens = list(raw_value)
        except TypeError:
            tokens = [raw_value]

    targets: list[PilotTarget] = []
    seen: set[tuple[str, int]] = set()
    for raw in tokens:
        text = str(raw).strip()
        if not text:
            continue
        kind = default_kind
        id_text = text
        if ":" in text:
            prefix, id_text = text.split(":", 1)
            kind = prefix.strip().lower()
        if kind not in SUPPORTED_KINDS:
            raise CommandError(
                f"Invalid Hollihop pilot target kind {kind!r}; use auto, student, teacher, or manager."
            )
        try:
            number = int(id_text.strip())
        except ValueError as exc:
            raise CommandError(
                f"Invalid Hollihop pilot target {text!r}; use ID or kind:ID, for example student:37."
            ) from exc
        if number <= 0:
            continue
        key = (kind, number)
        if key not in seen:
            seen.add(key)
            targets.append(PilotTarget(requested_id=number, kind=kind))
    return targets


def _configured_targets() -> list[PilotTarget]:
    default_kind = str(getattr(settings, "HOLLIHOP_PILOT_KIND", "auto") or "auto").strip().lower()
    if default_kind not in SUPPORTED_KINDS:
        raise CommandError("HOLLIHOP_PILOT_KIND must be auto, student, teacher, or manager.")

    explicit = getattr(settings, "HOLLIHOP_PILOT_TARGETS", "")
    targets = _parse_targets(explicit, default_kind=default_kind)
    if targets:
        return targets

    ids = _normalize_ids(getattr(settings, "HOLLIHOP_PILOT_USER_IDS", ()))
    if not ids:
        ids = _normalize_ids(getattr(settings, "HOLLIHOP_PILOT_USER_ID", 0))
    return [PilotTarget(requested_id=value, kind=default_kind) for value in ids]


class Command(BaseCommand):
    help = (
        "Controlled Hollihop pilot for one or more IDs. Prefer HOLLIHOP_PILOT_TARGETS "
        "(supports student:37, teacher:4, manager:12557). Legacy HOLLIHOP_PILOT_USER_IDS "
        "remains supported. Student UI IDs are translated to canonical ClientId before sync."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Detect and report configured Hollihop identities without writing MakonBook or sending SMS.",
        )
        parser.add_argument(
            "--no-sms",
            action="store_true",
            help="Sync targets but suppress pilot credential SMS even if HOLLIHOP_PILOT_SEND_SMS=true.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        if not getattr(settings, "HOLLIHOP_PILOT_ENABLED", False):
            raise CommandError("Pilot mode is disabled. Set HOLLIHOP_PILOT_ENABLED=true intentionally.")
        if not settings.HOLLIHOP_ENABLED:
            raise CommandError("HOLLIHOP_ENABLED=true is required for the pilot.")
        if settings.SCHOOL_DATA_PROVIDER != "local":
            raise CommandError(
                "Pilot mode requires SCHOOL_DATA_PROVIDER=local. Keep the full Hollihop integration disabled until the pilot is finished."
            )

        targets = _configured_targets()
        if not targets:
            raise CommandError(
                "Set HOLLIHOP_PILOT_TARGETS or HOLLIHOP_PILOT_USER_IDS/HOLLIHOP_PILOT_USER_ID to one or more Hollihop IDs."
            )
        if not settings.HOLLIHOP_API_URL or not settings.HOLLIHOP_AUTH_KEY:
            raise CommandError("HOLLIHOP_API_URL and HOLLIHOP_AUTH_KEY must be configured.")

        send_sms = bool(getattr(settings, "HOLLIHOP_PILOT_SEND_SMS", False)) and not options["no_sms"] and not dry_run

        try:
            client = HollihopClient()
        except HollihopConfigurationError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.MIGRATE_HEADING("Hollihop controlled pilot batch"))
        self.stdout.write(f"Configured targets: {', '.join(target.label for target in targets)}")
        self.stdout.write(f"Targets: {len(targets)}")
        self.stdout.write(f"Dry run: {'YES' if dry_run else 'NO'}")
        self.stdout.write(f"Pilot SMS: {'YES' if send_sms else 'NO'}")

        success_count = 0
        error_count = 0
        per_target_errors: list[tuple[PilotTarget, str]] = []

        for index, target in enumerate(targets, start=1):
            self.stdout.write("")
            self.stdout.write(self.style.HTTP_INFO(
                f"[{index}/{len(targets)}] Hollihop target {target.label}"
            ))
            try:
                self._process_one(
                    client=client,
                    target=target,
                    dry_run=dry_run,
                    send_sms=send_sms,
                )
            except (HollihopConfigurationError, HollihopError, HollihopSyncAlreadyRunning, ValueError, CommandError) as exc:
                error_count += 1
                message = str(exc)
                per_target_errors.append((target, message))
                self.stderr.write(self.style.ERROR(f"Target {target.label}: {message}"))
                continue
            except Exception as exc:
                error_count += 1
                message = f"unexpected {type(exc).__name__}: {safe_text(exc, 400)}"
                per_target_errors.append((target, message))
                self.stderr.write(self.style.ERROR(f"Target {target.label}: {message}"))
                continue
            success_count += 1

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Pilot batch summary"))
        self.stdout.write(f"Successful: {success_count}")
        self.stdout.write(f"Errors: {error_count}")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN complete. No MakonBook rows changed and no SMS was sent."))
        elif error_count == 0:
            self.stdout.write(self.style.SUCCESS("Hollihop pilot batch complete."))

        if error_count:
            if len(targets) == 1 and per_target_errors:
                target, message = per_target_errors[0]
                raise CommandError(f"Target {target.label}: {message}")
            raise CommandError(
                f"Pilot batch processed all {len(targets)} target(s) but {error_count} target(s) failed. Review the per-target errors above."
            )

    def _process_one(self, *, client, target: PilotTarget, dry_run: bool, send_sms: bool) -> None:
        engine = HollihopSyncEngine(client=client, dry_run=dry_run, send_credentials=False)
        identity = _detect_identity(client, engine, target.requested_id, target.kind)
        profile_before = _profile_for(identity)

        self.stdout.write(f"Detected type: {identity.kind}")
        self.stdout.write(f"Name: {identity.display_name}")
        self.stdout.write(f"Phone: {identity.phone or 'NOT AVAILABLE'}")
        if identity.kind == "student":
            self.stdout.write(f"Hollihop Student ID: {identity.requested_id}")
            self.stdout.write(f"Hollihop ClientId: {identity.external_id}")
        else:
            self.stdout.write(f"Hollihop {identity.kind.title()} ID: {identity.external_id}")
        self.stdout.write(f"Already in MakonBook: {'YES' if profile_before else 'NO'}")

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Detected successfully; no changes made."))
            return

        if send_sms and not identity.phone:
            raise CommandError("Pilot SMS was requested, but Hollihop has no valid phone for this identity.")

        try:
            engine.acquire_lock()
            try:
                if identity.kind == "student":
                    engine.sync_students(only_client_id=identity.external_id)
                elif identity.kind == "teacher":
                    engine.sync_teachers(only_teacher_id=identity.external_id)
                else:
                    engine.sync_managers(only_employee_id=identity.external_id)
                engine.release_lock(success=engine.summary.errors == 0, partial=engine.summary.errors > 0)
            except Exception as exc:
                engine.release_lock(success=False, error=f"{type(exc).__name__}: {safe_text(exc, 400)}")
                raise
        except (HollihopSyncAlreadyRunning, HollihopError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        if engine.summary.errors:
            raise CommandError(f"Pilot sync completed with {engine.summary.errors} error(s); SMS was not sent.")

        profile = _profile_for(identity)
        if not profile:
            if identity.kind == "student":
                status = safe_text(identity.payload.get("Status"), 150)
                raise CommandError(
                    f"The student was not created. Hollihop status={status or 'unknown'}; inactive students without an existing MakonBook account are intentionally skipped."
                )
            raise CommandError("The target identity was not linked to a MakonBook account.")

        user = profile.user
        self.stdout.write(f"MakonBook user: {user.get_username()} (id={user.id})")
        self.stdout.write(f"Created by Hollihop: {'YES' if profile.hollihop_created else 'NO'}")
        self.stdout.write(f"Credential state: {profile.credentials_delivery_status}")

        if send_sms:
            if not profile.hollihop_created:
                raise CommandError(
                    "The Hollihop identity matched an existing MakonBook account. Pilot refused to rotate its password automatically."
                )
            if profile.credentials_delivery_status != "pending":
                self.stdout.write(self.style.WARNING(
                    f"SMS not sent: credential state is {profile.credentials_delivery_status!r}, not 'pending'."
                ))
            else:
                try:
                    delivery = deliver_new_temporary_access(
                        user,
                        channels={"sms"},
                        sms_role_label=identity.kind.title(),
                    )
                except Exception as exc:
                    raise CommandError(
                        f"Pilot SMS delivery failed safely: {type(exc).__name__}: {safe_text(exc, 300)}"
                    ) from exc
                if delivery.sms_status != "sent":
                    raise CommandError(
                        f"Pilot SMS was not delivered. status={delivery.sms_status}, overall={delivery.overall_status}."
                    )
                self.stdout.write(self.style.SUCCESS(
                    f"Credential SMS sent to {identity.phone} via the configured provider. Role={identity.kind}."
                ))

        self.stdout.write(self.style.SUCCESS(f"Target {target.label} pilot complete."))
