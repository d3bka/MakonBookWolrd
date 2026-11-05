from django.template import Context, Template
from django.test import TestCase

from apps.sat.models import English_Question, Math_Question, Test
from apps.sat.rich_text import makon_plain_text, render_makon_text


class RenderMakonTextTests(TestCase):
    def test_paragraphs_line_breaks_and_marks(self):
        html = render_makon_text("One *it* **bold** ***both*** <u>under</u>\nnext\n\nTwo")
        self.assertEqual(
            html,
            "<p>One <em>it</em> <strong>bold</strong> <strong><em>both</em></strong> <u>under</u><br>next</p><p>Two</p>",
        )

    def test_everything_else_is_escaped(self):
        html = render_makon_text('<script>alert(1)</script> <b>x</b> & "q"')
        self.assertNotIn("<script>", html)
        self.assertNotIn("<b>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_math_is_left_for_katex_with_its_backslashes(self):
        html = render_makon_text(r"If \(x < 30\) then \[ \neq \times \text{a*b*c} \]")
        self.assertIn(r"\(x &lt; 30\)", html)
        self.assertIn(r"\[ \neq \times \text{a*b*c} \]", html)
        self.assertNotIn("<em>", html)

    def test_tables_lists_and_figures(self):
        html = render_makon_text("| x | y |\n|---|---|\n| 1 | 2 |\n\n- a\n- b\n\n![A graph](https://cdn.test/g.png)")
        self.assertIn("<tr><th>x</th><th>y</th></tr><tr><td>1</td><td>2</td></tr>", html)
        self.assertIn('<ul class="mk-list"><li>a</li><li>b</li></ul>', html)
        self.assertIn('<img class="mk-figure" src="https://cdn.test/g.png" alt="A graph"', html)

    def test_unresolved_or_unsafe_images_show_their_description(self):
        self.assertIn("[A graph]", render_makon_text("![A graph](r2:sat/x.png)"))
        self.assertNotIn("javascript", render_makon_text("![x](javascript:alert(1))"))

    def test_inline_drops_the_paragraph_of_one_line_text(self):
        self.assertEqual(render_makon_text(r"\(3\)", inline=True), r"\(3\)")

    def test_plain_text(self):
        self.assertEqual(makon_plain_text("**Answer:** ![g](r2:k) *i*"), "Answer: g i")


class QuestionTemplateFilterTests(TestCase):
    def test_question_display_renders_makon_and_escapes_legacy(self):
        test = Test.objects.create(name="T")
        makon = English_Question.objects.create(test=test, module="module_1", number=1, question="**Bold**", content_format="makon")
        legacy = Math_Question.objects.create(test=test, module="module_1", number=1, question="<b>x</b>\ny")
        template = Template('{% load question_text %}{{ q|question_display:"question" }}')
        self.assertEqual(template.render(Context({"q": makon})), "<p><strong>Bold</strong></p>")
        self.assertEqual(template.render(Context({"q": legacy})), "&lt;b&gt;x&lt;/b&gt;<br>y")


class ReviewPayloadTests(TestCase):
    def test_makon_question_review_payload_is_rendered(self):
        from apps.sat.views import _review_choices_payload, _review_question_payload

        test = Test.objects.create(name="T")
        q = Math_Question.objects.create(
            test=test, module="module_1", number=1, question="Find \\(x\\).", a="**1**", b="2", c="3", d="4",
            answer="A", explained="- step", content_format="makon",
        )
        payload = _review_question_payload(q, "math")
        self.assertTrue(payload["rich"])
        self.assertEqual(payload["question"], "<p>Find \\(x\\).</p>")
        self.assertEqual(payload["a"], "<strong>1</strong>")
        self.assertIn("<li>step</li>", payload["explanation"])
        self.assertTrue(_review_choices_payload(q, "math")[0]["rich"])


class DesmosKeyTests(TestCase):
    def test_the_key_comes_from_settings(self):
        from django.test import override_settings

        from apps.sat.templatetags.runner_tags import DESMOS_DEMO_KEY, desmos_calculator_src

        with override_settings(DESMOS_API_KEY="our-key"):
            self.assertEqual(desmos_calculator_src(), "https://www.desmos.com/api/v1.10/calculator.js?apiKey=our-key")
        with override_settings(DESMOS_API_KEY=""):
            self.assertTrue(desmos_calculator_src().endswith(f"apiKey={DESMOS_DEMO_KEY}"))
