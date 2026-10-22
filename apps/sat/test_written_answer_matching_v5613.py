from django.test import SimpleTestCase

from .numeric_answer_matching import check_written_answer, parse_numeric
from .views import check_written


class WrittenAnswerMatchingV5613Tests(SimpleTestCase):
    def test_thousands_separator_is_equivalent_to_plain_integer(self):
        self.assertTrue(check_written("15000", "15,000"))
        self.assertTrue(check_written("15,000", "15000"))
        self.assertFalse(check_written("15", "15,000"))

    def test_decimal_comma_is_equivalent_to_decimal_point(self):
        self.assertTrue(check_written("0,857", "0.857"))
        self.assertTrue(check_written("1,5", "1.5"))
        self.assertFalse(check_written("857", "0,857"))

    def test_fraction_and_exact_decimal_match(self):
        self.assertTrue(check_written("3/2", "1.5"))
        self.assertTrue(check_written("1.5", "3/2"))

    def test_fraction_matches_three_decimal_rounding_but_not_coarse_rounding(self):
        self.assertTrue(check_written("6/7", "0.857"))
        self.assertTrue(check_written("0.857", "6/7"))
        self.assertFalse(check_written("0.86", "6/7"))

    def test_latex_fraction_is_supported_as_reference_or_response(self):
        self.assertTrue(check_written(r"\(\frac{3}{2}\)", "1.5"))
        self.assertTrue(check_written("1.5", r"\frac{3}{2}"))

    def test_unicode_minus_and_leading_zeroes_are_harmless(self):
        self.assertTrue(check_written("−2.5", "-2.5"))
        self.assertTrue(check_written("0003", "3"))

    def test_explicit_multiple_reference_values_use_semicolon_or_newline(self):
        self.assertTrue(check_written("0.5", "1/2; 0.5"))
        self.assertTrue(check_written("2", "1\n2\n3"))
        self.assertFalse(check_written("4", "1\n2\n3"))

    def test_comma_inside_student_response_is_not_treated_as_multiple_answers(self):
        self.assertFalse(check_written("0,857", "857"))
        self.assertFalse(check_written("15,000", "15"))

    def test_zero_denominator_never_matches(self):
        self.assertFalse(check_written("1/0", "0"))
        self.assertIsNone(parse_numeric("1/0"))

    def test_non_numeric_fallback_keeps_legacy_exact_text_behavior(self):
        self.assertTrue(check_written_answer(" x = 3 ", "x=3"))
        self.assertFalse(check_written_answer("x=4", "x=3"))
