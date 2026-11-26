import io
import secrets
import string
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group, User
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count, Avg
from django.db.models.deletion import ProtectedError
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.core.paginator import Paginator
from .models import (
    Test, TestReview, Mock, SecretCode, SupportTeacherProfile,
    SupportTeacherAvailability, SupportLessonBooking, PublicPlacementLead,
    PlacementTelegramNotification,
)
from .forms_admin import UserFilterForm, UserGroupEditForm, GroupCreateForm, MockCreateForm, GroupAssignedTestsForm, SupportTeacherProfileForm, SupportTeacherAvailabilityForm
from .roles import SUPPORT_TEACHER_GROUP, TEACHER_GROUP, in_group, is_role_group_name


def generate_password(length=12):
    alphabet = string.ascii_letters + string.digits
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and any(c.isdigit() for c in password)):
            return password


def _warn_about_revoked_staff_roles(request, user):
    if user.owned_classrooms.exists() and not in_group(user, TEACHER_GROUP):
        messages.warning(
            request,
            f"Teacher access is revoked for '{user.username}'. Existing classrooms were preserved but no longer grant Teacher permissions.",
        )
    try:
        has_support_profile = user.support_teacher_profile is not None
    except Exception:
        has_support_profile = False
    if has_support_profile and not in_group(user, SUPPORT_TEACHER_GROUP):
        messages.warning(
            request,
            f"Support Teacher access is revoked for '{user.username}'. The profile/history was preserved but no longer grants permissions.",
        )



# --- Permission Check ---
def is_admin_user(user):
    return user.is_authenticated and (
        user.groups.filter(name='Admin').exists()
        or user.is_staff
        or user.is_superuser
    )


admin_panel_required = user_passes_test(is_admin_user, login_url='/login/')


# V73: role groups hold every teacher / manager / admin account. "Delete group"
# used to delete all of its users too, so one confirmation could wipe the staff.
def _is_protected_group(group):
    return is_role_group_name(group.name)


def _mock_generated_usernames(mocks):
    """Usernames a mock created itself (first column of its credentials CSV)."""
    names = set()
    for mock in mocks:
        for line in (mock.credentials or "").splitlines()[1:]:
            username = line.split(",", 1)[0].strip()
            if username:
                names.add(username)
    return names


def _split_group_members(group, acting_user):
    """Return (accounts to delete, accounts only detached from the group).

    Only throw-away accounts are deleted. Kept: the admin doing it, staff and
    superusers, anyone in another group (a role or a second mock), and, for a
    mock group, real students who joined it with the mock's secret code.
    """
    mocks = list(Mock.objects.filter(group=group))
    generated = _mock_generated_usernames(mocks) if mocks else None
    delete, keep = [], []
    for user in group.user_set.all().prefetch_related("groups"):
        disposable = (
            user.pk != acting_user.pk
            and not user.is_staff
            and not user.is_superuser
            and all(g.pk == group.pk for g in user.groups.all())
            and (generated is None or user.username in generated)
        )
        (delete if disposable else keep).append(user)
    return delete, keep


def _delete_or_deactivate(user):
    """Delete an account; one with protected history (assessments) is deactivated instead."""
    try:
        with transaction.atomic():
            user.delete()
        return True
    except ProtectedError:
        User.objects.filter(pk=user.pk).update(is_active=False)
        return False


# --- Dashboard ---
@login_required
@admin_panel_required
def admin_dashboard(request):
    today = timezone.localdate()
    placement_leads = PublicPlacementLead.objects.select_related("event", "attempt")
    recent_placement_leads = list(placement_leads.order_by("-created_at")[:6])

    context = {
        'user_count': User.objects.count(),
        'group_count': Group.objects.count(),
        'test_count': Test.objects.count(),
        'mock_count': Mock.objects.count(),
        'support_teacher_count': SupportTeacherProfile.objects.filter(user__groups__name__iexact=SUPPORT_TEACHER_GROUP).distinct().count(),
        'active_support_teacher_count': SupportTeacherProfile.objects.filter(is_active=True, user__groups__name__iexact=SUPPORT_TEACHER_GROUP).distinct().count(),
        'support_booking_count': SupportLessonBooking.objects.count(),
        'placement_lead_count': placement_leads.count(),
        'placement_today_count': placement_leads.filter(created_at__date=today).count(),
        'placement_testing_count': placement_leads.filter(attempt__status='in_progress').count(),
        'placement_completed_count': placement_leads.filter(attempt__status='submitted').count(),
        'telegram_pending_count': PlacementTelegramNotification.objects.filter(status='pending').count(),
        'recent_placement_leads': recent_placement_leads,
        'page_title': 'Admin Dashboard',
        'active_page': 'dashboard',
    }
    return render(request, 'sat/admin/dashboard.html', context)


# --- Users ---
@login_required
@admin_panel_required
def admin_users(request):
    form = UserFilterForm(request.GET or None)
    users = User.objects.all().order_by('-date_joined')

    if form.is_valid():
        group = form.cleaned_data.get('group')
        username = form.cleaned_data.get('username')
        status = form.cleaned_data.get('status')

        if group:
            users = users.filter(groups=group)
        if username:
            users = users.filter(username__icontains=username)
        if status == 'active':
            users = users.filter(is_active=True)
        elif status == 'inactive':
            users = users.filter(is_active=False)

    paginator = Paginator(users, 50)
    page = request.GET.get('page')
    users_page = paginator.get_page(page)

    context = {
        'form': form,
        'users': users_page,
        'page_title': 'Users',
        'active_page': 'users',
    }
    return render(request, 'sat/admin/users.html', context)


@login_required
@admin_panel_required
def admin_user_detail(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)
    groups = target_user.groups.all()
    reviews = TestReview.objects.filter(user=target_user).order_by('-created_at')[:20]

    context = {
        'target_user': target_user,
        'groups': groups,
        'reviews': reviews,
        'page_title': f'User: {target_user.username}',
        'active_page': 'users',
    }
    return render(request, 'sat/admin/user_detail.html', context)


@login_required
@admin_panel_required
def admin_user_edit(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        form = UserGroupEditForm(request.POST)
        if form.is_valid():
            target_user.groups.set(form.cleaned_data['groups'])
            messages.success(request, f"Groups updated for '{target_user.username}'.")
            _warn_about_revoked_staff_roles(request, target_user)
            return redirect('admin_user_detail', user_id=target_user.pk)
    else:
        form = UserGroupEditForm(initial={'groups': target_user.groups.all()})

    context = {
        'target_user': target_user,
        'form': form,
        'page_title': f'Edit: {target_user.username}',
        'active_page': 'users',
    }
    return render(request, 'sat/admin/user_edit.html', context)


@login_required
@admin_panel_required
def admin_user_delete(request, user_id):
    if request.method == 'POST':
        target_user = get_object_or_404(User, pk=user_id)
        username = target_user.username
        if target_user.pk == request.user.pk:
            messages.error(request, "You cannot delete your own account here.")
            return redirect('admin_users')
        if target_user.is_superuser and not request.user.is_superuser:
            messages.error(request, "Only a superuser can delete a superuser account.")
            return redirect('admin_users')
        try:
            target_user.delete()
        except ProtectedError:
            # V73: assessment records protect the account (compliance history).
            target_user.is_active = False
            target_user.save(update_fields=["is_active"])
            messages.warning(request, f"User '{username}' has assessment records, so the account was deactivated instead of deleted.")
        else:
            messages.success(request, f"User '{username}' deleted.")
    return redirect('admin_users')


@login_required
@admin_panel_required  # V73 security: this was only login-protected (any student could create an Admin)
def admin_user_create(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()
        group_id = request.POST.get("group")

        if not username or not password:
            messages.error(request, "Username and password are required.")
            return redirect("admin_user_create")

        if User.objects.filter(username=username).exists():
            messages.error(request, "User already exists.")
            return redirect("admin_user_create")

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        group = Group.objects.filter(id=group_id).first() if str(group_id or "").isdigit() else None
        if group:
            user.groups.add(group)

        messages.success(request, f"User {username} created successfully.")
        return redirect("admin_users")

    groups = Group.objects.all()

    return render(request, "sat/admin/user_create.html", {
        "groups": groups,
        "page_title": "Create User",
        "active_page": "users",
    })

# --- Groups ---
@login_required
@admin_panel_required
def admin_groups(request):
    if request.method == 'POST':
        form = GroupCreateForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            if not Group.objects.filter(name=name).exists():
                Group.objects.create(name=name)
                messages.success(request, f"Group '{name}' created.")
            else:
                messages.error(request, f"Group '{name}' already exists.")
            return redirect('admin_groups')
    else:
        form = GroupCreateForm()

    groups = Group.objects.all().annotate(member_count=Count('user')).order_by('name')

    context = {
        'groups': groups,
        'form': form,
        'page_title': 'Groups',
        'active_page': 'groups',
    }
    return render(request, 'sat/admin/groups.html', context)


@login_required
@admin_panel_required
def admin_group_detail(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    members = group.user_set.all().order_by('username')
    tests = group.tests.all()
    secret_codes = SecretCode.objects.filter(group=group)
    assigned_tests_form = GroupAssignedTestsForm(group=group)

    context = {
        'group': group,
        'members': members,
        'tests': tests,
        'secret_codes': secret_codes,
        'page_title': f'Group: {group.name}',
        'active_page': 'groups',
        'assigned_tests_form': assigned_tests_form,
    }
    return render(request, 'sat/admin/group_detail.html', context)


@login_required
@admin_panel_required
def admin_group_delete(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    if _is_protected_group(group):
        messages.error(request, f'"{group.name}" is a role group and cannot be deleted. Remove members one by one instead.')
        return redirect("admin_group_detail", group_id=group.pk)
    users_to_delete, users_to_keep = _split_group_members(group, request.user)
    page = {
        "group": group,
        "users_count": len(users_to_delete),
        "kept_count": len(users_to_keep),
    }

    if request.method == "POST":
        confirmation_name = request.POST.get("confirmation_name", "").strip()

        if confirmation_name != group.name:
            messages.error(request, "Group name confirmation does not match.")
            return render(request, "sat/admin/group_delete.html", page)

        group_name = group.name
        with transaction.atomic():
            deleted = sum(1 for user in users_to_delete if _delete_or_deactivate(user))
            group.delete()

        message = f'Group "{group_name}" and {deleted} users were deleted successfully.'
        kept = len(users_to_keep) + len(users_to_delete) - deleted
        if kept:
            message += f" {kept} account(s) were kept (staff, other groups, or protected history)."
        messages.success(request, message)
        return redirect("admin_groups")

    return render(request, "sat/admin/group_delete.html", page)


@login_required
@admin_panel_required
def admin_group_remove_user(request, group_id, user_id):
    if request.method == 'POST':
        group = get_object_or_404(Group, pk=group_id)
        user = get_object_or_404(User, pk=user_id)
        group.user_set.remove(user)
        messages.success(request, f"Removed '{user.username}' from '{group.name}'.")
        _warn_about_revoked_staff_roles(request, user)
    return redirect('admin_group_detail', group_id=group_id)


# --- Tests ---
ADMIN_TEST_TYPES = {"regular": "Practice", "placement": "Placement", "event": "Event", "exam": "Mid/Final exam"}
ADMIN_TEST_SORTS = {"name": "Name", "recent": "Recently completed", "popular": "Most completed", "new": "Newest"}


def _count_subquery(model, field="test_id"):
    from django.db.models import IntegerField, OuterRef, Subquery

    return Subquery(
        model.objects.filter(**{field: OuterRef("pk")}).values(field).annotate(total=Count("pk")).values("total")[:1],
        output_field=IntegerField(),
    )


@login_required
@admin_panel_required
def admin_tests(request):
    """V97: one query per column instead of two queries per test, with search and filters."""
    from django.db.models import DateTimeField, F, OuterRef, Subquery, Value
    from django.db.models.functions import Coalesce

    from .models import English_Question, GlobalEvent, Math_Question

    query = (request.GET.get("q") or "").strip()[:120]
    test_type = (request.GET.get("type") or "all").strip().lower()
    state = (request.GET.get("state") or "all").strip().lower()
    sort = (request.GET.get("sort") or "name").strip().lower()
    if sort not in ADMIN_TEST_SORTS:
        sort = "name"

    last_done = Subquery(
        TestReview.objects.filter(test_id=OuterRef("pk")).order_by("-created_at").values("created_at")[:1],
        output_field=DateTimeField(),
    )
    tests = (
        Test.objects.prefetch_related("groups")
        .annotate(
            english_count=Coalesce(_count_subquery(English_Question), Value(0)),
            math_count=Coalesce(_count_subquery(Math_Question), Value(0)),
            completion_count=Coalesce(_count_subquery(TestReview), Value(0)),
            event_count=Coalesce(_count_subquery(GlobalEvent), Value(0)),
            last_completed=last_done,
        )
    )
    all_tests = list(tests)
    stats = {
        "total": len(all_tests),
        "available": sum(1 for t in all_tests if t.is_available),
        "hidden": sum(1 for t in all_tests if not t.is_available),
        "completions": sum(t.completion_count for t in all_tests),
        "empty": sum(1 for t in all_tests if not (t.english_count or t.math_count)),
        "by_type": {key: sum(1 for t in all_tests if t.test_type == key) for key in ADMIN_TEST_TYPES},
    }

    if query:
        tests = tests.filter(name__icontains=query)
    if test_type in ADMIN_TEST_TYPES:
        tests = tests.filter(test_type=test_type)
    if state == "available":
        tests = tests.filter(is_available=True)
    elif state == "hidden":
        tests = tests.filter(is_available=False)
    elif state == "empty":
        tests = tests.filter(english_count=0, math_count=0)
    order = {
        "name": ["name"],
        "recent": [F("last_completed").desc(nulls_last=True), "name"],
        "popular": ["-completion_count", "name"],
        "new": [F("published_at").desc(nulls_last=True), "-created", "name"],
    }[sort]
    tests = list(tests.order_by(*order))

    context = {
        "tests": tests,
        "stats": stats,
        "query": query,
        "test_type": test_type if test_type in ADMIN_TEST_TYPES else "all",
        "state": state if state in {"available", "hidden", "empty"} else "all",
        "sort": sort,
        "type_labels": ADMIN_TEST_TYPES,
        "sort_labels": ADMIN_TEST_SORTS,
        "filtered": bool(query or test_type in ADMIN_TEST_TYPES or state in {"available", "hidden", "empty"}),
        "page_title": "Tests",
        "active_page": "tests",
    }
    return render(request, "sat/admin/tests.html", context)


@login_required
@admin_panel_required
def admin_test_import_json(request):
    """V97: a JSON file becomes a staging import (see apps.sat.json_test_import)."""
    from .json_test_import import JsonImportError, import_uploaded_json

    if request.method != "POST":
        return redirect("admin_tests")
    try:
        job = import_uploaded_json(request.FILES.get("file"), created_by=request.user)
    except JsonImportError as exc:
        messages.error(request, f"Nothing was imported: {exc}")
        return redirect("admin_tests")
    messages.success(request, f"'{job.name}' is ready for review. The AI is now solving every question to check the answer key.")
    return redirect("manager_test_import_detail_root", job_id=job.pk)


@login_required
@admin_panel_required
def admin_test_detail(request, test_name):
    from .models import English_Question, GlobalEvent, Math_Question

    test = get_object_or_404(Test.objects.prefetch_related("groups"), pk=test_name)
    modules = {}
    for label, model in (("english", English_Question), ("math", Math_Question)):
        rows = dict(model.objects.filter(test=test).values_list("module").annotate(total=Count("pk")))
        modules[label] = {"m1": rows.get("module_1", 0), "m2": rows.get("module_2", 0)}
        modules[label]["total"] = sum(rows.values())
    reviews = TestReview.objects.filter(test=test)
    summary = reviews.aggregate(
        completions=Count("pk"), students=Count("user", distinct=True), average=Avg("score"),
    )
    recent = reviews.select_related("user", "classroom").order_by("-created_at")[:12]
    events = GlobalEvent.objects.filter(test=test).order_by("-start_at")[:10]

    context = {
        "test": test,
        "groups": list(test.groups.all()),
        "modules": modules,
        "summary": summary,
        "recent": recent,
        "events": events,
        "type_label": ADMIN_TEST_TYPES.get(test.test_type, test.test_type),
        "page_title": f"Test: {test.name}",
        "active_page": "tests",
    }
    return render(request, "sat/admin/test_detail.html", context)


# --- Mocks ---
@login_required
@admin_panel_required
def admin_mocks(request):
    mocks = Mock.objects.all().order_by('-created_at')

    context = {
        'mocks': mocks,
        'page_title': 'Mocks',
        'active_page': 'mocks',
    }
    return render(request, 'sat/admin/mocks.html', context)


@login_required
@admin_panel_required
def admin_mock_create(request):
    if request.method == 'POST':
        form = MockCreateForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            test = form.cleaned_data['test']
            user_count = form.cleaned_data['user_count']
            mode = form.cleaned_data['mode']
            prefix = form.cleaned_data['username_prefix']
            pw_length = form.cleaned_data['password_length']

            try:
                with transaction.atomic():
                    # Create group
                    group_name = f"mock_{name.replace(' ', '_')}"
                    group, _ = Group.objects.get_or_create(name=group_name)

                    # Assign test to group
                    test.groups.add(group)

                    # Create users
                    created_users = []
                    for i in range(1, user_count + 1):
                        username = f"{prefix}_{i}"
                        password = generate_password(pw_length)
                        if User.objects.filter(username=username).exists():
                            continue
                        user = User.objects.create_user(username=username, password=password)
                        if mode == 'direct':
                            user.groups.add(group)
                        created_users.append({'username': username, 'password': password})

                    # Build credentials CSV
                    cred_lines = "Username,Password\n"
                    for u in created_users:
                        cred_lines += f"{u['username']},{u['password']}\n"

                    # Create secret code if needed
                    secret_code_obj = None
                    if mode == 'secret_code':
                        secret_code_obj = SecretCode.objects.create(
                            group=group,
                            test=test,
                        )

                    # Create Mock record
                    mock = Mock.objects.create(
                        name=name,
                        test=test,
                        group=group,
                        secret_code=secret_code_obj,
                        mode=mode,
                        user_count=len(created_users),
                        credentials=cred_lines,
                        created_by=request.user,
                    )

                messages.success(request, f"Mock '{name}' created with {len(created_users)} users.")
                return redirect('admin_mock_detail', mock_id=mock.pk)

            except Exception as e:
                messages.error(request, f"Error creating mock: {e}")
                return redirect('admin_mock_create')
    else:
        form = MockCreateForm()

    context = {
        'form': form,
        'page_title': 'Create Mock',
        'active_page': 'mocks',
    }
    return render(request, 'sat/admin/mock_create.html', context)


@login_required
@admin_panel_required
def admin_mock_detail(request, mock_id):
    mock = get_object_or_404(Mock, pk=mock_id)

    context = {
        'mock': mock,
        'page_title': f'Mock: {mock.name}',
        'active_page': 'mocks',
    }
    return render(request, 'sat/admin/mock_detail.html', context)


@login_required
@admin_panel_required
def admin_mock_download(request, mock_id):
    mock = get_object_or_404(Mock, pk=mock_id)
    buffer = io.StringIO(mock.credentials)
    response = HttpResponse(buffer.getvalue(), content_type='text/plain')
    filename = f"{mock.name.replace(' ', '_')}_credentials.txt"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


#--- Group Assigned Tests ---
@login_required
@admin_panel_required  # V73 security: was login-only
def edit_group_tests(request, group_id):
    group = get_object_or_404(Group, id=group_id)

    if request.method == 'POST':
        form = GroupAssignedTestsForm(request.POST, group=group)
        if form.is_valid():
            form.save()
            messages.success(request, f"Assigned tests updated for {group.name}")
            return redirect('admin_group_detail', group_id=group.id)
    else:
        form = GroupAssignedTestsForm(group=group)

    return render(request, 'sat/admin/edit_group_tests.html', {
        'group': group,
        'form': form,
    })

# Mock Deletion
@login_required
@admin_panel_required  # V73 security: was login-only
def admin_mock_delete(request, mock_id):
    mock = get_object_or_404(Mock, pk=mock_id)
    group = mock.group
    secret_code = mock.secret_code

    # V73: only the accounts this mock generated are deleted. Real students who
    # joined the mock group with its secret code used to be deleted with it.
    if group and not _is_protected_group(group):
        users_to_delete, users_to_keep = _split_group_members(group, request.user)
    else:
        users_to_delete, users_to_keep = [], []
    page = {
        'mock': mock,
        'group': group,
        'users_count': len(users_to_delete),
        'kept_count': len(users_to_keep),
    }

    if request.method == 'POST':
        confirmation_name = request.POST.get('confirmation_name', '').strip()

        if confirmation_name != mock.name:
            messages.error(request, 'Mock name confirmation does not match.')
            return render(request, 'sat/admin/mock_delete.html', page)

        mock_name = mock.name
        group_name = group.name if group else 'No group'

        with transaction.atomic():
            if secret_code:
                secret_code.delete()
            mock.delete()
            deleted = sum(1 for user in users_to_delete if _delete_or_deactivate(user))
            # the group goes too, unless another mock still uses it or it is a role group
            if group and not _is_protected_group(group) and not Mock.objects.filter(group=group).exists():
                group.delete()

        message = f'Mock "{mock_name}" was deleted together with group "{group_name}" and {deleted} generated users.'
        if users_to_keep:
            message += f' {len(users_to_keep)} other account(s) in the group were kept.'
        messages.success(request, message)
        return redirect('admin_mocks')

    return render(request, 'sat/admin/mock_delete.html', page)


# --- Support Teachers ---
@login_required
@admin_panel_required
def admin_support_teachers(request):
    now_value = timezone.now()
    teachers = (
        SupportTeacherProfile.objects.select_related('user')
        .prefetch_related('availabilities')
        .annotate(
            upcoming_count=Count(
                'bookings',
                filter=Q(bookings__status=SupportLessonBooking.STATUS_SCHEDULED, bookings__end_at__gte=now_value),
                distinct=True,
            ),
            admin_avg_rating=Avg('reviews__rating'),
            admin_reviews_count=Count('reviews', distinct=True),
        )
        .order_by('sort_order', 'display_name', 'user__username')
    )
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()

    if query:
        teachers = teachers.filter(
            Q(display_name__icontains=query)
            | Q(user__username__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(telegram_username__icontains=query)
            | Q(subjects__icontains=query)
        )

    if status == 'active':
        teachers = teachers.filter(is_active=True)
    elif status == 'inactive':
        teachers = teachers.filter(is_active=False)

    paginator = Paginator(teachers, 30)
    teachers_page = paginator.get_page(request.GET.get('page'))

    return render(request, 'sat/admin/support_teachers.html', {
        'teachers': teachers_page,
        'query': query,
        'status': status,
        'page_title': 'Support Teachers',
        'active_page': 'support_teachers',
    })


@login_required
@admin_panel_required
def admin_support_bookings(request):
    bookings = SupportLessonBooking.objects.select_related(
        'teacher', 'teacher__user', 'student', 'lesson_title', 'lesson_topic', 'session'
    ).order_by('-created_at')
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    teacher_id = request.GET.get('teacher', '').strip()
    date_from = parse_date(request.GET.get('date_from', '').strip())
    date_to = parse_date(request.GET.get('date_to', '').strip())

    if query:
        bookings = bookings.filter(
            Q(student__username__icontains=query)
            | Q(student__first_name__icontains=query)
            | Q(student__last_name__icontains=query)
            | Q(teacher__display_name__icontains=query)
            | Q(teacher__user__username__icontains=query)
            | Q(student_note__icontains=query)
        )
    if status in dict(SupportLessonBooking.STATUS_CHOICES):
        bookings = bookings.filter(status=status)
    if teacher_id.isdigit():
        bookings = bookings.filter(teacher_id=int(teacher_id))
    if date_from:
        bookings = bookings.filter(start_at__date__gte=date_from)
    if date_to:
        bookings = bookings.filter(start_at__date__lte=date_to)

    summary = SupportLessonBooking.objects.aggregate(
        total=Count('id'),
        requested=Count('id', filter=Q(status=SupportLessonBooking.STATUS_REQUESTED)),
        scheduled=Count('id', filter=Q(status=SupportLessonBooking.STATUS_SCHEDULED)),
        completed=Count('id', filter=Q(status=SupportLessonBooking.STATUS_COMPLETED)),
        cancelled=Count('id', filter=Q(status=SupportLessonBooking.STATUS_CANCELLED)),
        no_show=Count('id', filter=Q(status=SupportLessonBooking.STATUS_NO_SHOW)),
    )
    paginator = Paginator(bookings, 40)
    bookings_page = paginator.get_page(request.GET.get('page'))

    return render(request, 'sat/admin/support_bookings.html', {
        'bookings': bookings_page,
        'teachers': SupportTeacherProfile.objects.select_related('user').order_by('sort_order', 'display_name'),
        'summary': summary,
        'query': query,
        'status': status,
        'teacher_id': teacher_id,
        'date_from': date_from,
        'date_to': date_to,
        'status_choices': SupportLessonBooking.STATUS_CHOICES,
        'page_title': 'Support Bookings',
        'active_page': 'support_bookings',
    })


@login_required
@admin_panel_required
def admin_support_teacher_create(request):
    if request.method == 'POST':
        form = SupportTeacherProfileForm(request.POST)
        if form.is_valid():
            teacher = form.save(commit=False)
            teacher.created_by = request.user
            teacher.save()
            support_group, _ = Group.objects.get_or_create(name='Support Teacher')
            teacher.user.groups.add(support_group)
            messages.success(request, f"Support teacher '{teacher.name}' created.")
            return redirect('admin_support_teacher_edit', teacher_id=teacher.id)
    else:
        form = SupportTeacherProfileForm()

    return render(request, 'sat/admin/support_teacher_form.html', {
        'form': form,
        'teacher': None,
        'availability_form': None,
        'availabilities': [],
        'recent_bookings': [],
        'page_title': 'Create Support Teacher',
        'active_page': 'support_teachers',
    })


@login_required
@admin_panel_required
def admin_support_teacher_edit(request, teacher_id):
    teacher = get_object_or_404(SupportTeacherProfile.objects.select_related('user'), id=teacher_id)

    if request.method == 'POST':
        form = SupportTeacherProfileForm(request.POST, instance=teacher)
        if form.is_valid():
            teacher = form.save()
            support_group, _ = Group.objects.get_or_create(name='Support Teacher')
            teacher.user.groups.add(support_group)
            messages.success(request, f"Support teacher '{teacher.name}' updated.")
            return redirect('admin_support_teacher_edit', teacher_id=teacher.id)
    else:
        form = SupportTeacherProfileForm(instance=teacher)

    availability_form = SupportTeacherAvailabilityForm(initial={'is_active': True})
    availabilities = teacher.availabilities.all().order_by('day_of_week', 'start_time')
    recent_bookings = SupportLessonBooking.objects.filter(teacher=teacher).select_related('student', 'lesson_title', 'lesson_topic', 'session').order_by('-created_at')[:20]

    return render(request, 'sat/admin/support_teacher_form.html', {
        'form': form,
        'teacher': teacher,
        'availability_form': availability_form,
        'availabilities': availabilities,
        'recent_bookings': recent_bookings,
        'page_title': f'Edit Support Teacher: {teacher.name}',
        'active_page': 'support_teachers',
    })


@login_required
@admin_panel_required
@transaction.atomic
def admin_support_teacher_toggle(request, teacher_id):
    if request.method != 'POST':
        return redirect('admin_support_teachers')

    teacher = get_object_or_404(SupportTeacherProfile, id=teacher_id)
    teacher.is_active = not teacher.is_active
    teacher.save(update_fields=['is_active', 'updated_at'])
    messages.success(request, f"Support teacher '{teacher.name}' is now {'active' if teacher.is_active else 'inactive'}.")
    return redirect('admin_support_teachers')


@login_required
@admin_panel_required
def admin_support_teacher_availability_add(request, teacher_id):
    teacher = get_object_or_404(SupportTeacherProfile, id=teacher_id)
    if request.method != 'POST':
        return redirect('admin_support_teacher_edit', teacher_id=teacher.id)

    form = SupportTeacherAvailabilityForm(request.POST)
    if form.is_valid():
        availability = form.save(commit=False)
        availability.teacher = teacher
        try:
            availability.full_clean()
            availability.save()
            messages.success(request, "Availability slot added.")
        except Exception as exc:
            messages.error(request, f"Could not save availability: {exc}")
    else:
        messages.error(request, "Availability form has invalid values.")

    return redirect('admin_support_teacher_edit', teacher_id=teacher.id)


@login_required
@admin_panel_required
def admin_support_teacher_availability_delete(request, teacher_id, availability_id):
    teacher = get_object_or_404(SupportTeacherProfile, id=teacher_id)
    if request.method != 'POST':
        return redirect('admin_support_teacher_edit', teacher_id=teacher.id)

    availability = get_object_or_404(SupportTeacherAvailability, id=availability_id, teacher=teacher)
    availability.delete()
    messages.success(request, "Availability slot deleted.")
    return redirect('admin_support_teacher_edit', teacher_id=teacher.id)


@login_required
@admin_panel_required
def admin_system_health(request):
    """V102: is every part of MakonBook alive, and who receives the alerts."""
    from django.conf import settings as django_settings

    from apps.base.system_health import alert_recipients, collect_status, send_alert

    if request.method == "POST" and request.POST.get("action") == "test":
        report = send_alert(
            f"✅ MakonBook · Test alert sent by {request.user.get_full_name() or request.user.username}. "
            "System alerts reach this chat.",
            subject="MakonBook: test alert",
        )
        if report["delivered"]:
            messages.success(request, f"Test alert sent: {report['telegram_sent']} Telegram chat(s), {report['email_sent']} e-mail address(es).")
        else:
            messages.error(request, "The test alert reached nobody. Check the recipients below and the server logs.")
        return redirect("admin_system_health")

    statuses = collect_status()
    return render(request, "sat/admin/system_health.html", {
        "page_title": "System health",
        "statuses": statuses,
        "down_count": sum(1 for s in statuses if s.state == "down"),
        "recipients": alert_recipients(),
        "watch_enabled": getattr(django_settings, "SYSTEM_HEALTH_WATCH_ENABLED", False),
    })


@login_required
@admin_panel_required
def admin_telegram_access(request):
    """V103: who may use the MakonBook Telegram bot. Super admins come from .env."""
    import os

    from apps.telegram_bot.access import grant_access, parse_telegram_id, people_with_access, revoke_access, superadmin_ids

    if request.method == "POST":
        action = request.POST.get("action")
        telegram_id = parse_telegram_id(request.POST.get("telegram_id"))
        if not telegram_id:
            messages.error(request, "Enter a Telegram ID: only digits, for example 123456789. The person gets it by sending /id to the bot.")
        elif action == "grant":
            name = (request.POST.get("name") or "").strip()[:100]
            _admin, changed = grant_access(telegram_id, first_name=name)
            messages.success(request, f"{name or telegram_id} now has access to the bot." if changed else f"{name or telegram_id} already has access.")
        elif action == "revoke":
            result = revoke_access(telegram_id)
            if result == "superadmin":
                messages.error(request, "Super admins are changed only in .env (TELEGRAM_SUPERADMIN_IDS).")
            else:
                messages.success(request, "Access removed." if result == "removed" else "This person had no access.")
        return redirect("admin_telegram_access")

    return render(request, "sat/admin/telegram_access.html", {
        "page_title": "Telegram bot access",
        "people": people_with_access(),
        "superadmin_count": len(superadmin_ids()),
        "bot_configured": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
    })
