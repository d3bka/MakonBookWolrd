"""Render MakonBook's question text format to safe HTML.

Questions synced from makonbook-api keep their text exactly as the API stores
it (the same text the mobile app reads), so it is rendered here, when a page
shows it, instead of being converted when it is copied. The format
(makonbook-questionbank tools/prompts/format.md, makonbook-api
internal/practice/content.go):

- paragraphs, separated by a blank line; a single newline is a line break
- ``\\( \\)`` and ``\\[ \\]`` math, left as written for KaTeX
- ``*italic*``, ``**bold**``, ``***bold italic***``, ``<u>underline</u>``
- ``- `` lists and pipe tables (header row, ``|---|`` separator, rows)
- ``![description](url)`` figures

Everything else is escaped: the only HTML that comes out is what this module
writes. This is a port of makonbook-api's web/admin/src/practice/format.ts
parser, so both read the text the same way.
"""

from __future__ import annotations

import re

from django.utils.html import escape
from django.utils.safestring import SafeString, mark_safe

FORMAT_LEGACY = "legacy"
FORMAT_MAKON = "makon"

# Italic may hold bold (*a **b** c*): its closing * is one not followed by another.
_INLINE = re.compile(
    r"(\\\([\s\S]*?\\\)"
    r"|\\\[[\s\S]*?\\\]"
    r"|!\[[^\]]*\]\([^)\s]*\)"
    r"|\*\*\*[\s\S]+?\*\*\*"
    r"|\*\*[\s\S]+?\*\*"
    r"|<u>[\s\S]*?</u>"
    r"|\*(?![\s*])(?:[^*]|\*\*[^*]+?\*\*)*?\*(?!\*)"
    r"|\n)"
)
_IMAGE = re.compile(r"^!\[([^\]]*)\]\(([^)\s]*)\)$")
_BLOCK_SPLIT = re.compile(r"\n[ \t]*\n")
_TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{2,}")
_SAFE_SRC = re.compile(r"^(https?://|/)[^\s\"'<>]*$", re.IGNORECASE)


def _image(alt: str, src: str) -> str:
    if not _SAFE_SRC.match(src or ""):
        # An unresolved r2: key or anything unexpected: show the description.
        return f'<span class="mk-figure-missing">[{escape(alt or "image")}]</span>'
    return f'<img class="mk-figure" src="{escape(src)}" alt="{escape(alt)}" loading="lazy">'


def _inline(text: str) -> str:
    out = []
    for index, part in enumerate(_INLINE.split(text)):
        if not part:
            continue
        if index % 2 == 0:
            out.append(escape(part))
        elif part == "\n":
            out.append("<br>")
        elif part.startswith("\\(") or part.startswith("\\["):
            # KaTeX's auto-render reads text nodes, so escaped < and & still
            # reach it as < and &.
            out.append(escape(part))
        elif part.startswith("!["):
            match = _IMAGE.match(part)
            out.append(_image(match.group(1), match.group(2)) if match else escape(part))
        elif part.startswith("***"):
            out.append(f"<strong><em>{_inline(part[3:-3])}</em></strong>")
        elif part.startswith("**"):
            out.append(f"<strong>{_inline(part[2:-2])}</strong>")
        elif part.startswith("<u>"):
            out.append(f"<u>{_inline(part[3:-4])}</u>")
        else:
            out.append(f"<em>{_inline(part[1:-1])}</em>")
    return "".join(out)


def _cells(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def _blocks(text: str) -> list[str]:
    blocks: list[str] = []
    for block in _BLOCK_SPLIT.split((text or "").strip()):
        if not block.strip():
            blocks.append('<p class="mk-gap"></p>')
            continue
        lines = block.split("\n")
        if len(lines) > 1 and all(line.strip().startswith("|") for line in lines):
            rows = [_cells(line) for line in lines if not _TABLE_SEPARATOR.match(line)]
            width = max(len(row) for row in rows)
            html = ['<div class="mk-table-wrap"><table class="mk-table">']
            for row_index, row in enumerate(rows):
                tag = "th" if row_index == 0 else "td"
                cells = "".join(
                    f"<{tag}>{_inline(row[i] if i < len(row) else '')}</{tag}>" for i in range(width)
                )
                html.append(f"<tr>{cells}</tr>")
            html.append("</table></div>")
            blocks.append("".join(html))
            continue
        if all(line.startswith("- ") for line in lines):
            items = "".join(f"<li>{_inline(line[2:])}</li>" for line in lines)
            blocks.append(f'<ul class="mk-list">{items}</ul>')
            continue
        # Figures stand on their own line; the lines around them stay paragraphs.
        run: list[str] = []

        def flush():
            if run:
                blocks.append(f"<p>{_inline(chr(10).join(run))}</p>")
                run.clear()

        for line in lines:
            match = _IMAGE.match(line.strip())
            if match:
                flush()
                blocks.append(f'<figure class="mk-figure-block">{_image(match.group(1), match.group(2))}</figure>')
            else:
                run.append(line)
        flush()
    return blocks


def render_makon_text(text, *, inline: bool = False) -> SafeString:
    """The text as HTML. ``inline`` drops the paragraph around one-line text
    (answer choices), so it sits in its container like plain text."""
    if not text:
        return mark_safe("")
    blocks = _blocks(str(text))
    if inline and len(blocks) == 1 and blocks[0].startswith("<p>") and blocks[0].endswith("</p>"):
        return mark_safe(blocks[0][3:-4])
    return mark_safe("".join(blocks))


_TAG = re.compile(r"<[^>]+>")
_MARKS = re.compile(r"\*{1,3}|</?u>|!\[([^\]]*)\]\([^)\s]*\)")


def makon_plain_text(text) -> str:
    """The text without its marks, for short previews and search."""
    if not text:
        return ""
    value = _MARKS.sub(lambda m: m.group(1) or "", str(text))
    return re.sub(r"\s+", " ", value).strip()


def is_makon(question) -> bool:
    return getattr(question, "content_format", FORMAT_LEGACY) == FORMAT_MAKON


def question_html(question, field: str, *, inline: bool = False):
    """A question field ready for a page that inserts HTML (the exam runner).

    MakonBook-format text is rendered; legacy text is returned as stored,
    which is what those pages always did with it.
    """
    value = getattr(question, field, "") or ""
    if is_makon(question):
        return str(render_makon_text(value, inline=inline))
    return value


def question_display(question, field: str, *, inline: bool = False):
    """A question field for a Django template that escapes text: rendered
    MakonBook text, or legacy text escaped with its line breaks kept."""
    from django.template.defaultfilters import linebreaksbr

    value = getattr(question, field, "") or ""
    if is_makon(question):
        return render_makon_text(value, inline=inline)
    return linebreaksbr(value, autoescape=True)


def runner_question_fields(question) -> dict:
    """passage, question, choices and format for the exam runner's JSON."""
    if is_makon(question):
        return {
            "passage": question_html(question, "passage"),
            "question": question_html(question, "question"),
            "a": question_html(question, "a", inline=True),
            "b": question_html(question, "b", inline=True),
            "c": question_html(question, "c", inline=True),
            "d": question_html(question, "d", inline=True),
            "format": FORMAT_MAKON,
        }

    def choice(letter):
        getter = getattr(question, f"get_{letter}", None)
        return getter() if callable(getter) else (getattr(question, letter, "") or "")

    return {
        "passage": question.passage or "",
        "question": question.question or "",
        "a": choice("a"),
        "b": choice("b"),
        "c": choice("c"),
        "d": choice("d"),
        "format": FORMAT_LEGACY,
    }
