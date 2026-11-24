"""V104: "Duplicate accounts" — people with two MakonBook accounts, merged by a manager."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.base.account_merge import (
    MergeRefused, account_summaries, dismiss_pair, find_duplicate_pairs, merge_accounts, merge_preview, recommended_keep,
)
from apps.base.models import AccountMerge

from .roles import is_manager, is_platform_admin

CATEGORIES = {"staff": "Teachers and staff", "students": "Students"}
SHOWN = 100


def _allowed(user):
    return is_manager(user) or is_platform_admin(user)


@login_required(login_url="/login/")
def manager_account_duplicates(request):
    if not _allowed(request.user):
        return HttpResponseForbidden("Manager access required.")
    category = request.GET.get("type") if request.GET.get("type") in CATEGORIES else "staff"

    if request.method == "POST" and request.POST.get("action") == "dismiss":
        a, b = request.POST.get("a", ""), request.POST.get("b", "")
        if a.isdecimal() and b.isdecimal() and a != b:
            dismiss_pair(int(a), int(b), by=request.user)
            messages.success(request, "Marked as different people. This pair will not be suggested again.")
        return redirect(f"{request.path}?type={category}")

    all_pairs = find_duplicate_pairs(category)
    pairs = all_pairs[:SHOWN]
    summaries = account_summaries([p["a"].id for p in pairs] + [p["b"].id for p in pairs])
    for pair in pairs:
        pair["keep_id"] = recommended_keep(pair["a"], pair["b"], summaries)
        pair["sides"] = [
            {"user": u, "summary": summaries.get(u.id, {}), "recommended": u.id == pair["keep_id"],
             "other": pair["b"] if u is pair["a"] else pair["a"]}
            for u in (pair["a"], pair["b"])
        ]
    other = "students" if category == "staff" else "staff"
    return render(request, "sat/manager_account_duplicates.html", {
        "category": category,
        "categories": CATEGORIES,
        "pairs": pairs,
        "total_pairs": len(all_pairs),
        "other_category": other,
        "recent_merges": AccountMerge.objects.select_related("kept_user", "merged_by")[:15],
    })


@login_required(login_url="/login/")
def manager_account_merge(request, keep_id, remove_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Manager access required.")
    keep = get_object_or_404(User, pk=keep_id)
    remove = get_object_or_404(User, pk=remove_id)
    back = request.GET.get("type") if request.GET.get("type") in CATEGORIES else "staff"

    if request.method == "POST":
        if (request.POST.get("confirm") or "").strip().upper() != "MERGE":
            messages.error(request, "Type MERGE to confirm.")
            return redirect(request.get_full_path())
        try:
            merge = merge_accounts(keep, remove, by=request.user)
        except MergeRefused as exc:
            messages.error(request, str(exc))
            return redirect(f"{reverse('manager_account_duplicates_root')}?type={back}")
        moved = sum(v for v in merge.moved.values() if isinstance(v, int))
        stayed = sum(merge.dropped.values())
        text = f"Merged: {remove.username} → {keep.username}. Moved {moved} record{'s' if moved != 1 else ''}."
        if stayed:
            text += f" {stayed} duplicate record{'s' if stayed != 1 else ''} stayed with the old account."
        messages.success(request, text)
        return redirect(f"{reverse('manager_account_duplicates_root')}?type={back}")

    summaries = account_summaries([keep.id, remove.id])
    return render(request, "sat/manager_account_merge.html", {
        "keep": keep, "remove": remove, "category": back,
        "keep_summary": summaries.get(keep.id, {}), "remove_summary": summaries.get(remove.id, {}),
        "preview": merge_preview(remove, keep),
        "blocked": "Accounts with admin rights are not merged here." if (remove.is_staff or remove.is_superuser)
        else ("This account is already switched off." if not remove.is_active else ""),
    })
