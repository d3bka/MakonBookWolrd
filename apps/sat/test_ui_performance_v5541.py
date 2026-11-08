from django.contrib.auth.models import User
from django.test import TestCase

from apps.sat.models import English_Question, Math_Question, Test
from apps.sat.views import (
    _decorate_pretest_config_metadata_batch,
    _test_module_inventory,
)


class HomeworkUiPerformanceV5541Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='v5541_student',
            password='pass',
        )
        self.test = Test.objects.create(name='DAY57', is_available=True)
        English_Question.objects.create(
            test=self.test,
            module='module_1',
            number=1,
            question='RW',
            answer='A',
        )
        Math_Question.objects.create(
            test=self.test,
            module='module_1',
            number=1,
            question='Math',
            answer='1',
            written=True,
        )

    def test_inventory_accepts_string_test_primary_key(self):
        inventory = _test_module_inventory([self.test.pk])
        self.assertEqual(inventory['DAY57'][('english', 'm1')], 1)
        self.assertEqual(inventory['DAY57'][('math', 'm1')], 1)

    def test_batch_metadata_accepts_string_test_primary_key(self):
        rows = _decorate_pretest_config_metadata_batch(
            [self.test],
            self.user,
            classroom=None,
        )
        self.assertEqual(rows[0].pk, 'DAY57')
        self.assertTrue(rows[0].preconfig_full_available)
