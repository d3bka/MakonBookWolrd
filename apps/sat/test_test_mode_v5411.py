from pathlib import Path
from django.contrib.auth.models import User
from django.test import TestCase
import uuid
from apps.sat.models import Test, TestStage, TestModule, English_Question, Math_Question
from apps.sat.views import get_test_sequence, _load_latest_modules, _results_url_for_test


class TestModeV5411Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='mode-user', password='pass')
        self.test = Test.objects.create(name='MODE5411')
        English_Question.objects.create(test=self.test, module='module_1', number=1, question='E1')
        English_Question.objects.create(test=self.test, module='module_2', number=1, question='E2')
        Math_Question.objects.create(test=self.test, module='module_1', number=1, question='M1')
        Math_Question.objects.create(test=self.test, module='module_2', number=1, question='M2')

    def test_mode_sequences(self):
        self.assertEqual(get_test_sequence(self.test, 'full_test'), [('english','m1'),('english','m2'),('math','m1'),('math','m2')])
        self.assertEqual(get_test_sequence(self.test, 'rw_only'), [('english','m1'),('english','m2')])
        self.assertEqual(get_test_sequence(self.test, 'math_only'), [('math','m1'),('math','m2')])
        self.assertEqual(get_test_sequence(self.test, 'single_math_m2'), [('math','m2')])

    def test_stage_mode_default(self):
        stage = TestStage.objects.create(user=self.user, test=self.test, stage=1)
        self.assertEqual(stage.mode, 'full_test')

    def test_reference_sheet_and_precover_picker_assets_exist(self):
        root = Path(__file__).resolve().parents[2]
        math_template = (root / 'templates/test/shared/attempt_math.html').read_text(encoding='utf-8')
        practice = (root / 'templates/sat/practice_tests.html').read_text(encoding='utf-8')
        cover = (root / 'templates/test/test_modules.html').read_text(encoding='utf-8')
        picker_js = (root / 'static/assets/js/makon-test-config-v550.js').read_text(encoding='utf-8')

        self.assertIn('sat-reference-wrapper', math_template)
        self.assertIn('Special Right Triangles', math_template)
        self.assertIn('makon-test-config-v550.js', practice)
        self.assertIn('Choose module', picker_js)
        self.assertIn('Exam Integrity', picker_js)
        self.assertIn("integrityFullscreen=this.state.integrity!=='off'", picker_js)
        self.assertNotIn('data-test-mode-picker', cover)
        self.assertIn('sat531-overview', cover)

    def test_selected_mode_changes_cover_overview(self):
        from apps.sat.views import _build_test_start_overview
        overview = _build_test_start_overview(self.test, self.user, mode='single_math_m2')
        self.assertEqual(overview['selected_test_mode'], 'single_math_m2')
        self.assertEqual(overview['total_modules'], 1)
        self.assertEqual(overview['total_questions'], 1)
        self.assertEqual(overview['module_rows'][0]['section'], 'math')
        self.assertEqual(overview['module_rows'][0]['module'], 'm2')

    def test_math_only_cover_overview_is_not_overwritten_by_option_loop(self):
        from apps.sat.views import _build_test_start_overview
        overview = _build_test_start_overview(self.test, self.user, mode='math_only')
        self.assertEqual(overview['selected_test_mode'], 'math_only')
        self.assertEqual(overview['total_modules'], 2)
        self.assertEqual(overview['total_questions'], 2)
        self.assertEqual(
            [(row['section'], row['module']) for row in overview['module_rows']],
            [('math', 'm1'), ('math', 'm2')],
        )

    def test_results_loader_normalizes_legacy_module_names(self):
        attempt_id = uuid.uuid4()
        TestModule.objects.create(
            user=self.user,
            test=self.test,
            test_type='regular',
            section='math',
            module='module_1',
            attempt_id=attempt_id,
            answers='{"answers": []}',
        )
        modules = _load_latest_modules(
            self.user,
            self.test,
            attempt_id=attempt_id,
            classroom=None,
        )
        self.assertIn('math_m1', modules)

    def test_results_url_can_pin_attempt_id(self):
        attempt_id = uuid.uuid4()
        url = _results_url_for_test(self.test, attempt_id=attempt_id)
        self.assertIn(f'attempt_id={attempt_id}', url)



    def test_preconfig_metadata_has_mode_stats(self):
        from apps.sat.views import _decorate_pretest_config_metadata
        _decorate_pretest_config_metadata(self.test, self.user, classroom=None)
        self.assertEqual(self.test.preconfig_math_questions, 2)
        self.assertEqual(self.test.preconfig_math_modules, 2)
        self.assertEqual(self.test.preconfig_math_minutes, 70)


    def test_classroom_practice_student_route_is_unified_redirect(self):
        import inspect
        from apps.sat.views import classroom_practice_tests
        source = inspect.getsource(classroom_practice_tests)
        self.assertIn("role == 'student'", source)
        self.assertIn("redirect('practice_tests_root')", source)
        self.assertIn('_classroom_practice_tests_management_view', source)

