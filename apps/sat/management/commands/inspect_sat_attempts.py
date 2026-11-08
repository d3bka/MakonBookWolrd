"""Read-only triage of SAT retakes and integrity strikes.

Usage: py manage.py inspect_sat_attempts --username STUDENT --test-name "DAY 2"
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from apps.sat.models import Test, TestStage, TestModule, TestModuleDraft, TestReview, ExamIntegrityViolation
from apps.sat.views import get_test_sequence


class Command(BaseCommand):
    help = 'Read-only SAT attempt triage: modules, drafts, results and integrity events.'

    def add_arguments(self, parser):
        user = parser.add_mutually_exclusive_group(required=True)
        user.add_argument('--username')
        user.add_argument('--user-id', type=int)
        parser.add_argument('--test-name', required=True)
        parser.add_argument('--show-last', type=int, default=12)

    def handle(self, *args, **options):
        User = get_user_model()
        if options.get('username'):
            user = User.objects.filter(username=options['username']).first()
        else:
            user = User.objects.filter(pk=options['user_id']).first()
        test = Test.objects.filter(name=options['test_name']).first()
        if user is None or test is None:
            raise CommandError('User or test not found. Check exact username and test name.')
        stages = list(TestStage.objects.filter(
            user=user, test=test, test_type='regular'
        ).order_by('-attempt_started_at', '-created_at', '-pk'))
        self.stdout.write('READ-ONLY — no account, answer, or result changed.')
        self.stdout.write(f'User ID: {user.pk} | Test: {test.name} | Attempts: {len(stages)}')
        for stage in stages:
            scope = {'user': user, 'test': test, 'attempt_id': stage.attempt_id,
                     'classroom_id': stage.classroom_id}
            modules = set(TestModule.objects.filter(**scope, test_type='regular').values_list('section','module'))
            drafts = list(TestModuleDraft.objects.filter(**scope).values_list('section','module','deadline_at'))
            reviews = list(TestReview.objects.filter(**scope).values_list('id','score'))
            events = list(ExamIntegrityViolation.objects.filter(stage=stage).order_by('-created_at')
                          .values_list('event_type','strike_number','created_at')[:max(0,options['show_last'])])
            required = get_test_sequence(test, mode=stage.mode)
            expected = set(required)
            completed = bool(expected and expected.issubset(modules))
            missing = sorted(expected - modules)
            self.stdout.write(f'\nAttempt: {stage.attempt_id} | stage={stage.stage} | mode={stage.mode}')
            self.stdout.write(f'  started={stage.attempt_started_at} | completed_modules={completed}')
            self.stdout.write(f'  saved_modules={sorted(modules)} | missing_modules={missing}')
            self.stdout.write(f'  drafts={[(s,m,str(d)) for s,m,d in drafts]}')
            self.stdout.write(f'  reviews={reviews} | strikes={stage.integrity_violation_count} | terminated={bool(stage.integrity_terminated_at)}')
            if completed and not any(score is not None for _, score in reviews):
                self.stdout.write('  DIAGNOSIS: all required modules saved but no scored result; inspect results backfill.')
            elif missing and not drafts:
                self.stdout.write('  DIAGNOSIS: missing submitted modules and no draft; investigate server submission logs.')
            for kind, number, when in events:
                self.stdout.write(f'    {when}: {kind} strike={number}')
