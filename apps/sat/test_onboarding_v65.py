from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class PrototypeOnboardingV65Tests(TestCase):
    """Regression coverage for authenticated onboarding; no signup flow."""

    def setUp(self):
        self.User = get_user_model()

    def test_existing_student_is_not_asked_for_name_again(self):
        user = self.User.objects.create_user(
            username='goal-v65-complete-name', password='test-pass-12345',
            first_name='Alex', last_name='Test',
        )
        self.client.force_login(user)
        response = self.client.get(reverse('student_dashboard_root'), follow=True)
        self.assertContains(response, 'data-mb65-onboard')
        self.assertContains(response, 'data-name-required="0"')
        self.assertNotContains(response, 'Create your account.')

    def test_missing_name_uses_integrated_step_but_retains_global_gate_markup(self):
        user = self.User.objects.create_user(
            username='goal-v65-missing-name', password='test-pass-12345',
            first_name='', last_name='',
        )
        self.client.force_login(user)
        response = self.client.get(reverse('student_dashboard_root'), follow=True)
        self.assertContains(response, 'data-mb65-onboard')
        self.assertContains(response, 'data-name-required="1"')
        # V69: the wizard's name step replaces the global gate on this page
        # (it used to ask twice) and the wizard always opens while the name is
        # missing. Other pages still use the global gate.
        self.assertNotContains(response, 'data-profile-name-gate')
        self.assertContains(response, 'data-auto-open="1"')
        other_page = self.client.get(reverse('student_mistakes_root'))  # V79: Learn became Mistakes
        self.assertContains(other_page, 'data-profile-name-gate')

    def test_goal_form_posts_to_existing_authenticated_endpoint(self):
        user = self.User.objects.create_user(
            username='goal-v65-target', password='test-pass-12345',
            first_name='Alex', last_name='Test',
        )
        self.client.force_login(user)
        response = self.client.get(reverse('student_dashboard_root'), follow=True)
        self.assertContains(response, f'action="{reverse("student_goal_settings_root")}"')
        self.assertContains(response, 'data-goal-submit')
        self.assertContains(response, 'student-goal-universities')
