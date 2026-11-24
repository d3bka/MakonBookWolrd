"""V104: find people with two MakonBook accounts and merge them into one.

Typical case: a teacher or student had an account created by hand, and the Hollihop
import created a second one ("HH …"). Hollihop classes then live on one account while
the person logs in with the other.

Finding pairs (students: only a hand-made account next to a Hollihop one): names are compared after transliteration (Cyrillic → Latin, x/kh/h, q/k,
y/i, …). Two names match when every word matches exactly or has the same consonant
"skeleton" (Jaksymuratov ~ Jahsimurodov). Female forms never match male ones
(Karimov ≠ Karimova, Aziz ≠ Aziza). Staff accounts also match on the same phone or e-mail;
students only by name (siblings share a parent's phone).

Merging moves everything that points at the removed account to the kept one, generically
for every model with a foreign key to User. A row that would collide with a row the kept
account already has (for example the same homework submission) stays with the removed
account: nothing is deleted. The removed account is switched off, never deleted. Hollihop
ids move to the kept account so synchronization keeps finding it.
"""
from __future__ import annotations

import re
from collections import defaultdict
from itertools import combinations, permutations

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Count

from apps.base.models import AccountDuplicateDismissal, AccountMerge, UserProfile

STAFF_GROUPS = {"teacher", "manager", "admin", "support teacher"}
HOLLIHOP_FIELDS = (
    ("hollihop_client_id", "Hollihop student"),
    ("hollihop_teacher_id", "Hollihop teacher"),
    ("hollihop_employee_id", "Hollihop employee"),
)


class MergeRefused(Exception):
    pass


# --------------------------------------------------------------------------- names

_CYR = dict(zip(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюяўқғҳ",
    ["a", "b", "v", "g", "d", "e", "yo", "j", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u",
     "f", "h", "ts", "ch", "sh", "sh", "", "i", "", "e", "yu", "ya", "o", "k", "g", "h"],
))
_SUBS = (("dzh", "j"), ("dj", "j"), ("kh", "h"), ("sh", "s"), ("ch", "c"), ("x", "h"), ("q", "k"),
         ("y", "i"), ("w", "v"), ("ph", "f"), ("ii", "i"))
_FEMALE_ENDINGS = ("ova", "eva", "iva", "ina")
_SKELETON = str.maketrans({"h": "k", "g": "k", "d": "t", "z": "s", "b": "p", "v": "f"})


def normalize_word(word: str) -> str:
    word = "".join(_CYR.get(ch, ch) for ch in (word or "").casefold())
    word = re.sub(r"[ʻʼ'`’‘]", "", word)
    for old, new in _SUBS:
        word = word.replace(old, new)
    return re.sub(r"[^a-z]", "", word)


def name_words(user) -> list[str]:
    raw = f"{user.first_name or ''} {user.last_name or ''}"
    return [w for w in (normalize_word(part) for part in raw.split()) if len(w) >= 2]


def _skeleton(word: str) -> str:
    return re.sub(r"[aeiou]", "", word).translate(_SKELETON)


def _word_score(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if a + "a" == b or b + "a" == a:
        return 0.0
    for ending in _FEMALE_ENDINGS:
        if (a.endswith(ending) and b == a[:-1]) or (b.endswith(ending) and a == b[:-1]):
            return 0.0
    if min(len(a), len(b)) >= 4 and _skeleton(a) == _skeleton(b):
        return 0.9
    return 0.0


def name_score(words_a: list[str], words_b: list[str]) -> float:
    if len(words_a) < 2 or len(words_b) < 2:
        return 0.0
    if len(words_a) > len(words_b):
        words_a, words_b = words_b, words_a
    if len(words_b) > 4:
        return 0.0
    best = 0.0
    for perm in permutations(words_b, len(words_a)):
        scores = [_word_score(a, b) for a, b in zip(words_a, perm)]
        if min(scores) > 0:
            best = max(best, sum(scores) / len(scores))
    return best


def _phone_key(phone) -> str:
    digits = re.sub(r"\D", "", phone or "")
    return digits[-9:] if len(digits) >= 9 else ""


# --------------------------------------------------------------------------- finding pairs

def _category(user, profile) -> str:
    groups = {g.name.casefold() for g in user.groups.all()}
    if groups & STAFF_GROUPS or (profile and (profile.hollihop_teacher_id or profile.hollihop_employee_id)):
        return "staff"
    return "students"


def _conflicting_hollihop(pa, pb) -> bool:
    if not pa or not pb:
        return False
    for field, _label in HOLLIHOP_FIELDS:
        va, vb = getattr(pa, field), getattr(pb, field)
        if va and vb and va != vb:
            return True
    return False


def _from_hollihop(profile) -> bool:
    return bool(profile and (profile.hollihop_client_id or profile.hollihop_teacher_id or profile.hollihop_employee_id))


def _pair_key(a_id, b_id):
    return (a_id, b_id) if a_id < b_id else (b_id, a_id)


def find_duplicate_pairs(category: str = "staff") -> list[dict]:
    users = list(
        User.objects.filter(is_active=True)
        .select_related("profile")
        .prefetch_related("groups")
    )
    info = {}
    for user in users:
        profile = getattr(user, "profile", None)
        cat = _category(user, profile)
        if cat != category:
            continue
        info[user.id] = {
            "user": user, "profile": profile, "words": name_words(user),
            "phone": _phone_key(profile.phone_number if profile else ""),
            "email": (user.email or "").strip().casefold(),
        }
    dismissed = set(AccountDuplicateDismissal.objects.values_list("user_low_id", "user_high_id"))

    # Two names can only match when two of their words have the same consonant skeleton,
    # so index every account by each pair of its word skeletons: groups stay tiny.
    candidates = defaultdict(set)
    blocks = defaultdict(set)
    for uid, item in info.items():
        skeletons = sorted({_skeleton(w) for w in item["words"][:4]})
        for pair in combinations(skeletons, 2):
            blocks[("n",) + pair].add(uid)
        if item["phone"] and category == "staff":
            blocks[("p", item["phone"])].add(uid)
        if item["email"] and category == "staff":
            blocks[("e", item["email"])].add(uid)
    for key, ids in blocks.items():
        if key[0] != "n" and len(ids) > 20:  # a shared office phone or e-mail is not a person
            continue
        for a, b in combinations(sorted(ids), 2):
            candidates[a].add(b)

    pairs = []
    for a, others in candidates.items():
        for b in others:
            ia, ib = info[a], info[b]
            if _pair_key(a, b) in dismissed or _conflicting_hollihop(ia["profile"], ib["profile"]):
                continue
            if category == "students" and _from_hollihop(ia["profile"]) == _from_hollihop(ib["profile"]):
                # Students: only a hand-made account next to a Hollihop one. Many different
                # students share a full name; two Hollihop students are two Hollihop records.
                continue
            reasons = []
            score = name_score(ia["words"], ib["words"])
            if score >= 1.0:
                reasons.append("Same name")
            elif score > 0:
                reasons.append("Similar name")
            if category == "staff":
                if ia["phone"] and ia["phone"] == ib["phone"]:
                    reasons.append("Same phone")
                    score = max(score, 0.85)
                if ia["email"] and ia["email"] == ib["email"]:
                    reasons.append("Same e-mail")
                    score = max(score, 0.85)
            if score <= 0:
                continue
            pairs.append({"a": ia["user"], "b": ib["user"], "score": round(score, 2), "reasons": reasons})
    pairs.sort(key=lambda p: (-p["score"], (p["a"].get_full_name() or p["a"].username).casefold()))
    return pairs


def account_summaries(user_ids) -> dict[int, dict]:
    """What each account holds, for choosing which one to keep."""
    from apps.sat.models import Classroom, ClassroomHomeworkSubmission, ClassroomMembership, TestReview

    ids = list(set(user_ids))
    taught = dict(Classroom.objects.filter(teacher_id__in=ids).values("teacher_id").annotate(n=Count("id")).values_list("teacher_id", "n"))
    member = dict(ClassroomMembership.objects.filter(user_id__in=ids, status="approved").values("user_id").annotate(n=Count("id")).values_list("user_id", "n"))
    tests = dict(TestReview.objects.filter(user_id__in=ids).values("user_id").annotate(n=Count("id")).values_list("user_id", "n"))
    homework = dict(ClassroomHomeworkSubmission.objects.filter(student_id__in=ids).values("student_id").annotate(n=Count("id")).values_list("student_id", "n"))
    profiles = {p.user_id: p for p in UserProfile.objects.filter(user_id__in=ids)}
    out = {}
    for uid in ids:
        profile = profiles.get(uid)
        links = [label for field, label in HOLLIHOP_FIELDS if profile and getattr(profile, field)]
        out[uid] = {
            "classes_taught": taught.get(uid, 0), "classes": member.get(uid, 0),
            "tests": tests.get(uid, 0), "homework": homework.get(uid, 0),
            "hollihop": links, "hollihop_ids": [str(getattr(profile, f)) for f, _ in HOLLIHOP_FIELDS if profile and getattr(profile, f)],
            "phone": bool(profile and profile.phone_number),
        }
    return out


def recommended_keep(a, b, summaries) -> int:
    """Keep the account the person actually uses: latest login, then more data, then Hollihop-linked."""
    def rank(user):
        s = summaries.get(user.id, {})
        data = s.get("classes_taught", 0) + s.get("classes", 0) + s.get("tests", 0) + s.get("homework", 0)
        return (user.last_login.timestamp() if user.last_login else 0, data, bool(s.get("hollihop")))
    return a.id if rank(a) >= rank(b) else b.id


# --------------------------------------------------------------------------- merging

_SKIP_MODELS = {"base.accountmerge", "base.accountduplicatedismissal", "base.userprofile"}


def _user_relations():
    for rel in User._meta.related_objects:
        model = rel.related_model
        if model._meta.proxy or not model._meta.managed or model._meta.label_lower in _SKIP_MODELS:
            continue
        if rel.many_to_many:
            through = rel.field.remote_field.through
            if not through._meta.auto_created:
                continue  # a custom through model is handled as its own foreign key
            yield rel, through, rel.field.m2m_reverse_field_name()
        else:
            yield rel, model, rel.field.name


def _label(model, field_name) -> str:
    return f"{model._meta.app_label}.{model._meta.model_name}.{field_name}"


def merge_preview(remove, keep=None) -> list[tuple[str, int]]:
    rows = []
    for rel, model, field in _user_relations():
        if rel.one_to_one and keep is not None and model._base_manager.filter(**{field: keep}).exists():
            continue  # the kept account already has its own; this one stays with the old account
        count = model._base_manager.filter(**{field: remove}).count()
        if count:
            name = str(model._meta.verbose_name_plural if not rel.many_to_many else rel.field.model._meta.verbose_name_plural)
            rows.append((f"{name} ({field.replace('_', ' ')})", count))
    rows.sort(key=lambda r: -r[1])
    return rows


def _move_rows(model, field, keep, remove) -> tuple[int, int]:
    qs = model._base_manager.filter(**{field: remove})
    total = qs.count()
    if not total:
        return 0, 0
    try:
        with transaction.atomic():
            moved = qs.update(**{field: keep})
        return moved, 0
    except IntegrityError:
        pass
    moved = stayed = 0
    for pk in list(qs.values_list("pk", flat=True)):
        try:
            with transaction.atomic():
                moved += model._base_manager.filter(pk=pk).update(**{field: keep})
        except IntegrityError:
            stayed += 1  # the kept account already has an equivalent row; this one stays with the old account
    return moved, stayed


def _merge_profiles(keep, remove, moved):
    kp, _ = UserProfile.objects.get_or_create(user=keep)
    rp, _ = UserProfile.objects.get_or_create(user=remove)
    for field, label in HOLLIHOP_FIELDS:
        kv, rv = getattr(kp, field), getattr(rp, field)
        if kv and rv and kv != rv:
            raise MergeRefused(f"The two accounts are different {label} records in Hollihop ({kv} and {rv}). They are different people.")
    took = []
    for field, _label in HOLLIHOP_FIELDS:
        rv = getattr(rp, field)
        if rv and not getattr(kp, field):
            setattr(rp, field, None)
            took.append((field, rv))
    if took:
        rp.save()
        for field, value in took:
            setattr(kp, field, value)
        kp.hollihop_status = kp.hollihop_status or rp.hollihop_status
        kp.hollihop_last_synced_at = kp.hollihop_last_synced_at or rp.hollihop_last_synced_at
        moved["hollihop_links"] = [field for field, _ in took]
    if not kp.phone_number and rp.phone_number:
        kp.phone_number = rp.phone_number
    if not kp.middle_name and rp.middle_name:
        kp.middle_name = rp.middle_name
    kp.save()
    # The switched-off account must not be found by Hollihop's contact matching any more.
    UserProfile.objects.filter(pk=rp.pk).update(phone_number=None)


def merge_accounts(keep: User, remove: User, *, by: User) -> AccountMerge:
    if keep.pk == remove.pk:
        raise MergeRefused("Choose two different accounts.")
    if remove.is_superuser or remove.is_staff:
        raise MergeRefused("Accounts with admin rights are not merged here. Change them in Django admin.")
    if not remove.is_active:
        raise MergeRefused("This account is already switched off.")
    moved, dropped = {}, {}
    with transaction.atomic():
        keep = User.objects.select_for_update().get(pk=keep.pk)
        remove = User.objects.select_for_update().get(pk=remove.pk)
        _merge_profiles(keep, remove, moved)

        for field in ("first_name", "last_name", "email"):
            if not getattr(keep, field) and getattr(remove, field):
                setattr(keep, field, getattr(remove, field))
        keep.save()
        keep.groups.add(*remove.groups.all())

        for rel, model, field in _user_relations():
            if rel.one_to_one:
                if not model._base_manager.filter(**{field: keep}).exists():
                    n = model._base_manager.filter(**{field: remove}).update(**{field: keep})
                    if n:
                        moved[_label(model, field)] = n
                continue
            n_moved, n_stayed = _move_rows(model, field, keep, remove)
            if n_moved:
                moved[_label(model, field)] = n_moved
            if n_stayed:
                dropped[_label(model, field)] = n_stayed

        try:  # allauth: one primary e-mail address per user
            from allauth.account.models import EmailAddress

            primaries = list(EmailAddress.objects.filter(user=keep, primary=True).order_by("id"))
            if len(primaries) > 1:
                EmailAddress.objects.filter(pk__in=[e.pk for e in primaries[1:]]).update(primary=False)
        except Exception:  # noqa: BLE001 - allauth missing or schema differs; nothing to fix then
            pass

        removed_name = remove.get_full_name()
        remove.is_active = False
        remove.email = ""
        remove.set_unusable_password()
        remove.save(update_fields=["is_active", "email", "password"])

        return AccountMerge.objects.create(
            kept_user=keep, removed_user=remove, removed_username=remove.username,
            removed_name=removed_name[:300], merged_by=by, moved=moved, dropped=dropped,
        )


def dismiss_pair(a_id: int, b_id: int, *, by) -> None:
    low, high = _pair_key(a_id, b_id)
    AccountDuplicateDismissal.objects.get_or_create(user_low_id=low, user_high_id=high, defaults={"dismissed_by": by})
