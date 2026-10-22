from django.test import SimpleTestCase

from apps.sat.text_formatting import convert_reading_latex_to_html


class QuestionFormattingSecurityTests(SimpleTestCase):
    def test_raw_html_is_escaped_but_supported_formatting_is_kept(self):
        value = r'<script>alert(1)</script> \underline{Safe text}'
        rendered = str(convert_reading_latex_to_html(value))
        self.assertNotIn('<script>', rendered)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', rendered)
        self.assertIn('<u>Safe text</u>', rendered)
