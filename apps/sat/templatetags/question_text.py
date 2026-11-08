from django import template

from apps.sat.rich_text import makon_plain_text, question_display, question_html

register = template.Library()


@register.filter(name="question_html")
def question_html_filter(question, field):
    """For JSON the exam runner inserts as HTML: rendered MakonBook text, or
    legacy text as stored. Escape it for its context (escapejs) as before."""
    inline = field in {"a", "b", "c", "d"}
    return question_html(question, field, inline=inline)


@register.filter(name="question_display")
def question_display_filter(question, field):
    """For an HTML page: rendered MakonBook text, or legacy text escaped with
    its line breaks kept (what `|linebreaksbr` did)."""
    inline = field in {"a", "b", "c", "d"}
    return question_display(question, field, inline=inline)


@register.filter(name="question_format")
def question_format_filter(question):
    return getattr(question, "content_format", "legacy") or "legacy"


@register.filter(name="question_plain")
def question_plain_filter(question, field):
    """Short previews: MakonBook text without its marks; legacy text as stored."""
    value = getattr(question, field, "") or ""
    if getattr(question, "content_format", "legacy") == "makon":
        return makon_plain_text(value)
    return value
