from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import English_Question, GlobalEvent, GlobalEventAttempt, Test


User = get_user_model()


class TestTypeV5560Tests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username='type_student', password='pass12345')
        self.staff = User.objects.create_user(username='type_staff', password='pass12345', is_staff=True)

        self.regular = Test.objects.create(
            name='TYPE DAY1',
            test_type=Test.TYPE_REGULAR,
            is_available=True,
        )
        self.placement = Test.objects.create(
            name='Diagnostic Alpha',
            test_type=Test.TYPE_PLACEMENT,
            is_available=True,
        )
        self.event_test = Test.objects.create(
            name='Autumn Cup Bank',
            test_type=Test.TYPE_EVENT,
            is_available=True,
        )
        English_Question.objects.create(
            test=self.placement,
            module='module_1',
            number=1,
            question='Placement sample',
            answer='A',
        )

    def test_new_tests_default_to_regular(self):
        test = Test.objects.create(name='DEFAULT TYPE TEST')
        self.assertEqual(test.test_type, Test.TYPE_REGULAR)

    def test_standalone_placement_typed_test_does_not_publish_without_global_event(self):
        """Placement hub is event-driven; a Test row alone must not publish a card."""
        self.client.force_login(self.student)
        response = self.client.get(reverse('placement_tests'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.placement.name)
        self.assertContains(response, 'No placement tests available right now.')

    def test_placement_source_can_stay_regular_and_only_global_event_publishes_it(self):
        restricted_group = Group.objects.create(name='Legacy Placement Gate')
        self.placement.groups.add(restricted_group)

        self.client.force_login(self.student)
        response = self.client.get(reverse('placement_tests'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.placement.name)

        # Direct legacy Placement Test access remains valid for now, but it is
        # not discoverable in Placement Tests without a Placement GlobalEvent.
        start = self.client.get(reverse('practice_test_start_root', args=[self.placement.name]))
        self.assertEqual(start.status_code, 200)
        self.assertContains(start, self.placement.name)

    def test_empty_placement_page_has_simple_student_message(self):
        self.placement.is_available = False
        self.placement.save(update_fields=['is_available'])
        self.client.force_login(self.student)
        response = self.client.get(reverse('placement_tests'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No placement tests available right now.')
        self.assertNotContains(response, 'Test Type')
        self.assertNotContains(response, 'admin')

    def test_placement_can_start_without_classroom_assignment(self):
        self.client.force_login(self.student)
        response = self.client.get(
            reverse('practice_test_start_root', args=[self.placement.name])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.placement.name)
        self.assertContains(response, 'Exam Integrity')

    def test_event_only_test_cannot_bypass_event_entry_route(self):
        self.client.force_login(self.student)
        response = self.client.get(
            reverse('practice_test_start_root', args=[self.event_test.name])
        )
        self.assertRedirects(response, reverse('events'), fetch_redirect_response=False)

    def test_staff_regular_library_excludes_placement_and_event_only_tests(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('practice_tests_root'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TYPE DAY1')
        self.assertNotContains(response, 'Diagnostic Alpha')
        self.assertNotContains(response, 'Autumn Cup Bank')

    def test_events_page_shows_only_active_event_category_global_events(self):
        now = timezone.now()
        live_event = GlobalEvent.objects.create(
            title='Autumn Cup Live',
            slug='autumn-cup-live-v5563',
            event_type=GlobalEvent.TYPE_EVENT,
            test=self.regular,
            start_at=now - timedelta(minutes=5),
            end_at=now + timedelta(hours=2),
            status='live',
            is_public=True,
            always_live=False,
        )
        placement_event = GlobalEvent.objects.create(
            title='Admissions Placement Live',
            slug='admissions-placement-live-v5563',
            event_type=GlobalEvent.TYPE_PLACEMENT,
            test=self.regular,
            start_at=now - timedelta(minutes=5),
            end_at=now + timedelta(hours=2),
            status='live',
            is_public=True,
            always_live=False,
        )
        GlobalEvent.objects.create(
            title='Autumn Cup Scheduled',
            slug='autumn-cup-scheduled-v5563',
            event_type=GlobalEvent.TYPE_EVENT,
            test=self.regular,
            start_at=now + timedelta(hours=2),
            end_at=now + timedelta(hours=4),
            status='scheduled',
            is_public=True,
            always_live=False,
        )
        GlobalEvent.objects.create(
            title='Autumn Cup Closed',
            slug='autumn-cup-closed-v5563',
            event_type=GlobalEvent.TYPE_EVENT,
            test=self.regular,
            start_at=now - timedelta(hours=4),
            end_at=now - timedelta(hours=2),
            status='closed',
            is_public=True,
            always_live=False,
        )

        self.client.force_login(self.student)
        response = self.client.get(reverse('events'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, live_event.title)
        self.assertContains(response, self.regular.name)
        self.assertNotContains(response, placement_event.title)
        self.assertNotContains(response, 'Autumn Cup Scheduled')
        self.assertNotContains(response, 'Autumn Cup Closed')

    def test_live_placement_global_event_appears_on_placement_page(self):
        now = timezone.now()
        event = GlobalEvent.objects.create(
            title='Placement Session A',
            slug='placement-session-a-v5563',
            event_type=GlobalEvent.TYPE_PLACEMENT,
            test=self.regular,
            start_at=now - timedelta(minutes=5),
            end_at=now + timedelta(hours=1),
            status='live',
            is_public=True,
        )
        self.client.force_login(self.student)
        response = self.client.get(reverse('placement_tests'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, event.title)
        self.assertContains(response, 'Open placement')
        self.assertNotContains(response, 'Live placement session using TYPE DAY1')
        self.assertNotContains(response, 'Source test: TYPE DAY1')

    def test_global_event_does_not_change_regular_source_test_type(self):
        regular_source = Test.objects.create(
            name='DAY 60 MOCK SOURCE',
            test_type=Test.TYPE_REGULAR,
            is_available=True,
        )
        now = timezone.now()
        event = GlobalEvent.objects.create(
            title='Mock 11.10.2026 For Minor Branch',
            slug='mock-minor-branch-v5563',
            event_type=GlobalEvent.TYPE_EVENT,
            test=regular_source,
            start_at=now - timedelta(minutes=5),
            end_at=now + timedelta(hours=1),
            status='live',
            is_public=True,
        )
        regular_source.refresh_from_db()
        self.assertEqual(regular_source.test_type, Test.TYPE_REGULAR)

        self.client.force_login(self.staff)
        tests_page = self.client.get(reverse('practice_tests_root'))
        self.assertEqual(tests_page.status_code, 200)
        self.assertContains(tests_page, regular_source.name)

        self.client.force_login(self.student)
        events_page = self.client.get(reverse('events'))
        self.assertEqual(events_page.status_code, 200)
        self.assertContains(events_page, event.title)
        self.assertContains(events_page, regular_source.name)

    def test_global_event_defaults_to_event_category(self):
        now = timezone.now()
        event = GlobalEvent.objects.create(
            title='Default Event Category',
            slug='default-event-category-v5563',
            test=self.regular,
            start_at=now - timedelta(minutes=5),
            end_at=now + timedelta(hours=1),
            status='live',
            is_public=True,
        )
        self.assertEqual(event.event_type, GlobalEvent.TYPE_EVENT)

    def test_global_event_admin_exposes_event_or_placement_selector(self):
        admin_user = User.objects.create_superuser(
            username='type_admin',
            email='type_admin@example.com',
            password='pass12345',
        )
        now = timezone.now()
        event = GlobalEvent.objects.create(
            title='Admin Event Type',
            slug='admin-event-type-v5563',
            event_type=GlobalEvent.TYPE_EVENT,
            test=self.regular,
            start_at=now - timedelta(minutes=5),
            end_at=now + timedelta(hours=1),
            status='live',
            is_public=True,
        )
        self.client.force_login(admin_user)
        response = self.client.get(reverse('admin:sat_globalevent_change', args=[event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="event_type"')
        self.assertContains(response, '>Event<')
        self.assertContains(response, '>Placement Test<')
        self.assertContains(response, 'Saving the Global Event does not reclassify it.')

    def test_private_live_global_event_is_hidden_but_code_opens_and_starts(self):
        now = timezone.now()
        English_Question.objects.create(
            test=self.regular,
            module='module_1',
            number=1,
            question='Private mock sample',
            answer='A',
        )
        private_event = GlobalEvent.objects.create(
            title='Private Minor Branch Mock',
            slug='private-minor-branch-mock-v5564',
            event_type=GlobalEvent.TYPE_EVENT,
            test=self.regular,
            access_code='234930',
            start_at=now - timedelta(minutes=5),
            end_at=now + timedelta(hours=2),
            status='live',
            is_public=False,
            always_live=True,
        )
        self.assertTrue(private_event.is_live_now)

        self.client.force_login(self.student)
        listing = self.client.get(reverse('events'))
        self.assertEqual(listing.status_code, 200)
        self.assertNotContains(listing, private_event.title)

        direct = self.client.get(reverse('global_event_detail_root', args=[private_event.slug]))
        self.assertEqual(direct.status_code, 200)
        self.assertContains(direct, private_event.title)
        self.assertContains(direct, 'Event access code')

        code_response = self.client.post(reverse('events'), {'code': private_event.access_code})
        self.assertRedirects(
            code_response,
            reverse('global_event_detail_root', args=[private_event.slug]),
            fetch_redirect_response=False,
        )

        detail = self.client.get(reverse('global_event_detail_root', args=[private_event.slug]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, private_event.title)
        self.assertContains(detail, 'Access code verified')

        start = self.client.post(reverse('start_global_event_root', args=[private_event.slug]), {})
        self.assertEqual(start.status_code, 302)
        self.assertIn('/events/attempt/', start.url)
        attempt = GlobalEventAttempt.objects.get(event=private_event)
        attempt_page = self.client.get(reverse('global_event_attempt_root', args=[attempt.guest_token]))
        self.assertEqual(attempt_page.status_code, 200)

    def test_private_live_global_event_rejects_wrong_code(self):
        now = timezone.now()
        private_event = GlobalEvent.objects.create(
            title='Private Code Test',
            slug='private-code-test-v5564',
            event_type=GlobalEvent.TYPE_EVENT,
            test=self.regular,
            access_code='ZXCV12',
            start_at=now - timedelta(minutes=5),
            end_at=now + timedelta(hours=2),
            status='live',
            is_public=False,
            always_live=True,
        )
        self.client.force_login(self.student)
        response = self.client.post(reverse('events'), {'code': 'WRONG1'})
        self.assertRedirects(response, reverse('events'), fetch_redirect_response=False)
        direct = self.client.get(reverse('global_event_detail_root', args=[private_event.slug]))
        self.assertEqual(direct.status_code, 200)
        self.assertContains(direct, 'Event access code')

    def test_public_live_event_remains_visible_for_five_hour_end_grace(self):
        now = timezone.now()
        within_grace = GlobalEvent.objects.create(
            title='Grace Window Mock',
            slug='grace-window-mock-v5567',
            event_type=GlobalEvent.TYPE_EVENT,
            test=self.regular,
            start_at=now - timedelta(hours=8),
            end_at=now - timedelta(hours=4, minutes=59),
            status='live',
            is_public=True,
            always_live=False,
        )
        self.assertTrue(within_grace.is_live_now)

        self.client.force_login(self.student)
        response = self.client.get(reverse('events'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, within_grace.title)

    def test_event_disappears_after_five_hour_end_grace_or_when_closed(self):
        now = timezone.now()
        expired = GlobalEvent.objects.create(
            title='Expired Grace Mock',
            slug='expired-grace-mock-v5567',
            event_type=GlobalEvent.TYPE_EVENT,
            test=self.regular,
            access_code='OLD555',
            start_at=now - timedelta(hours=10),
            end_at=now - timedelta(hours=5, minutes=1),
            status='live',
            is_public=True,
            always_live=False,
        )
        closed = GlobalEvent.objects.create(
            title='Manually Closed Mock',
            slug='manually-closed-mock-v5567',
            event_type=GlobalEvent.TYPE_EVENT,
            test=self.regular,
            start_at=now - timedelta(hours=2),
            end_at=now + timedelta(hours=2),
            status='closed',
            is_public=True,
            always_live=False,
        )
        self.assertFalse(expired.is_live_now)
        self.assertFalse(closed.is_live_now)

        self.client.force_login(self.student)
        response = self.client.get(reverse('events'))
        self.assertNotContains(response, expired.title)
        self.assertNotContains(response, closed.title)

        code_response = self.client.post(reverse('events'), {'code': expired.access_code})
        self.assertRedirects(code_response, reverse('events'), fetch_redirect_response=False)

    def test_placement_page_lists_only_public_active_placement_global_events(self):
        now = timezone.now()
        live = GlobalEvent.objects.create(
            title='Published Placement',
            slug='published-placement-v5567',
            event_type=GlobalEvent.TYPE_PLACEMENT,
            test=self.regular,
            start_at=now - timedelta(minutes=10),
            end_at=now + timedelta(hours=1),
            status='live',
            is_public=True,
        )
        GlobalEvent.objects.create(
            title='Private Placement',
            slug='private-placement-v5567',
            event_type=GlobalEvent.TYPE_PLACEMENT,
            test=self.regular,
            access_code='PLC123',
            start_at=now - timedelta(minutes=10),
            end_at=now + timedelta(hours=1),
            status='live',
            is_public=False,
        )
        self.client.force_login(self.student)
        response = self.client.get(reverse('placement_tests'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, live.title)
        self.assertNotContains(response, self.placement.name)
        self.assertNotContains(response, 'Private Placement')


    def test_always_live_event_ignores_calendar_end_until_manually_closed(self):
        now = timezone.now()
        event = GlobalEvent.objects.create(
            title='Expired Always Live Event',
            slug='expired-always-live-event-v5568',
            event_type=GlobalEvent.TYPE_EVENT,
            test=self.regular,
            start_at=now - timedelta(days=2),
            end_at=now - timedelta(hours=5, minutes=1),
            status='live',
            is_public=True,
            always_live=True,
        )
        self.assertTrue(event.is_live_now)
        self.assertIsNone(event.effective_end_at)

        self.client.force_login(self.student)
        response = self.client.get(reverse('events'))
        self.assertContains(response, event.title)
        event.refresh_from_db()
        self.assertEqual(event.status, 'live')

        event.status = 'closed'
        event.save(update_fields=['status'])
        self.assertFalse(event.is_live_now)

    def test_old_always_live_placement_remains_listed_while_status_is_live(self):
        now = timezone.now()
        event = GlobalEvent.objects.create(
            title='Old Always Live Placement',
            slug='old-always-live-placement-v5568',
            event_type=GlobalEvent.TYPE_PLACEMENT,
            test=self.regular,
            start_at=now - timedelta(days=90),
            end_at=now - timedelta(days=80),
            status='live',
            is_public=True,
            always_live=True,
        )
        self.assertTrue(event.is_live_now)
        self.assertIsNone(event.effective_end_at)

        self.client.force_login(self.student)
        response = self.client.get(reverse('placement_tests'))
        self.assertContains(response, event.title)
        event.refresh_from_db()
        self.assertEqual(event.status, 'live')

    def test_inactive_global_event_code_does_not_open_event(self):
        now = timezone.now()
        inactive = GlobalEvent.objects.create(
            title='Not Yet Active',
            slug='not-yet-active-v5563',
            event_type=GlobalEvent.TYPE_EVENT,
            test=self.regular,
            access_code='ZXCV12',
            start_at=now + timedelta(hours=1),
            end_at=now + timedelta(hours=3),
            status='scheduled',
            is_public=True,
            always_live=False,
        )
        self.client.force_login(self.student)
        response = self.client.post(reverse('events'), {'code': inactive.access_code})
        self.assertRedirects(response, reverse('events'), fetch_redirect_response=False)
