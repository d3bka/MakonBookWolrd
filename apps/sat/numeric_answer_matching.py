from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext


_TRANSLATION = str.maketrans({
    "−": "-",
    "–": "-",
    "—": "-",
    "＋": "+",
    "／": "/",
    "٫": ".",
    "٬": ",",
    "’": "'",
    "\u00a0": " ",
    "\u202f": " ",
})

_LATEX_FRACTION_RE = re.compile(
    r"^\\(?:d|t)?frac\s*\{\s*([+-]?(?:\d+(?:[.,]\d+)?|[.,]\d+))\s*\}"
    r"\s*\{\s*([+-]?(?:\d+(?:[.,]\d+)?|[.,]\d+))\s*\}$",
    re.IGNORECASE,
)

_GROUPED_COMMA_RE = re.compile(r"^[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?$")
_PLAIN_DECIMAL_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
_DECIMAL_COMMA_RE = re.compile(r"^[+-]?\d+,\d+$")
_FRACTION_RE = re.compile(r"^([+-]?(?:\d+(?:\.\d+)?|\.\d+))\/([+-]?(?:\d+(?:\.\d+)?|\.\d+))$")

# We only permit approximation when at least three decimal places were supplied.
# This is intentionally narrow: 0.857 may represent 6/7, while 0.86 is too coarse.
_MIN_APPROX_DECIMALS = 3


@dataclass(frozen=True)
class ParsedNumeric:
    value: Decimal
    decimal_places: int | None = None
    source_kind: str = "number"


def _clean(value) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).translate(_TRANSLATION).strip()
    # Strip common math wrappers without changing the expression itself.
    if text.startswith("\\(") and text.endswith("\\)"):
        text = text[2:-2].strip()
    if text.startswith("$") and text.endswith("$") and len(text) >= 2:
        text = text[1:-1].strip()
    text = re.sub(r"\\left|\\right", "", text)
    return text.strip()


def _decimal_places(text: str) -> int | None:
    mantissa = re.split(r"[eE]", text, maxsplit=1)[0]
    if "." not in mantissa:
        return 0
    return len(mantissa.rsplit(".", 1)[1])


def _normalize_scalar_text(text: str) -> tuple[str, int | None, str]:
    """Return a Decimal-compatible token plus visible decimal precision.

    Comma handling is deliberately context-aware:
    - 15,000 -> 15000 (English thousands grouping)
    - 0,857  -> 0.857 (decimal comma)
    - 1,5    -> 1.5   (decimal comma)
    """
    text = _clean(text)
    # Ignore grouping whitespace/apostrophes inside numbers.
    text = re.sub(r"(?<=\d)[\s'_](?=\d)", "", text)
    text = re.sub(r"\s+", "", text)

    if _GROUPED_COMMA_RE.fullmatch(text):
        # A zero integer part is much more likely to be a decimal comma (0,857)
        # than a grouped integer, so preserve that locale form as a decimal.
        signless = text.lstrip("+-")
        first_group = signless.split(",", 1)[0]
        if first_group == "0" and text.count(",") == 1 and "." not in text:
            normalized = text.replace(",", ".")
            return normalized, _decimal_places(normalized), "decimal_comma"
        normalized = text.replace(",", "")
        return normalized, _decimal_places(normalized), "grouped"

    if _DECIMAL_COMMA_RE.fullmatch(text):
        left, right = text.split(",", 1)
        # Exactly three trailing digits with a non-zero integer part is the
        # conventional thousands form (15,000 / 1,234). Other cases are decimal.
        if len(right) == 3 and left.lstrip("+-") not in {"", "0"}:
            normalized = left + right
            return normalized, 0, "grouped"
        normalized = left + "." + right
        return normalized, len(right), "decimal_comma"

    return text, _decimal_places(text) if _PLAIN_DECIMAL_RE.fullmatch(text) else None, "number"


def parse_numeric(value) -> ParsedNumeric | None:
    text = _clean(value)
    if not text:
        return None

    latex = _LATEX_FRACTION_RE.fullmatch(text.replace(" ", ""))
    if latex:
        numerator = parse_numeric(latex.group(1))
        denominator = parse_numeric(latex.group(2))
        if not numerator or not denominator or denominator.value == 0:
            return None
        with localcontext() as ctx:
            ctx.prec = 40
            return ParsedNumeric(numerator.value / denominator.value, None, "fraction")

    normalized, places, kind = _normalize_scalar_text(text)
    fraction = _FRACTION_RE.fullmatch(normalized)
    if fraction:
        try:
            numerator = Decimal(fraction.group(1))
            denominator = Decimal(fraction.group(2))
        except InvalidOperation:
            return None
        if denominator == 0:
            return None
        with localcontext() as ctx:
            ctx.prec = 40
            return ParsedNumeric(numerator / denominator, None, "fraction")

    if not _PLAIN_DECIMAL_RE.fullmatch(normalized):
        return None
    try:
        return ParsedNumeric(Decimal(normalized), places, kind)
    except InvalidOperation:
        return None


def _approx_equal(a: ParsedNumeric, b: ParsedNumeric) -> bool:
    if a.value == b.value:
        return True

    eligible_places = [
        places for places in (a.decimal_places, b.decimal_places)
        if places is not None and places >= _MIN_APPROX_DECIMALS
    ]
    if not eligible_places:
        return False

    # Use the coarsest explicitly supplied precision. This accepts a fraction
    # equivalent to a rounded 3+ dp decimal but does not make 2 dp guesses valid.
    places = min(eligible_places)
    tolerance = Decimal(5).scaleb(-(places + 1))  # half a unit in the last place
    return abs(a.value - b.value) <= tolerance


def _normalize_text_token(value) -> str:
    text = _clean(value).casefold()
    text = re.sub(r"\s+", "", text)
    return text


def _reference_variants(answer) -> list[str]:
    """Split explicit alternate reference answers without breaking numeric commas.

    Prefer semicolon, pipe, or newline for alternatives. A legacy comma list is
    used only when the complete value is not itself a valid numeric token.
    """
    text = str(answer or "").strip()
    if not text:
        return []

    explicit = [part.strip() for part in re.split(r"[;|\n]+", text) if part.strip()]
    if len(explicit) > 1:
        return explicit

    if parse_numeric(text) is not None:
        return [text]

    legacy = [part.strip() for part in text.split(",") if part.strip()]
    return legacy if len(legacy) > 1 else [text]


def normalize_written_value(value):
    """Compatibility helper used by older SAT code/tests."""
    parsed = parse_numeric(value)
    if parsed is not None:
        return parsed.value
    text = _normalize_text_token(value)
    return text or None


def check_written_answer(response, answer) -> bool:
    """Grade a Math student-produced response safely and deterministically.

    Supported harmless equivalents include grouping commas, decimal commas,
    fractions, common LaTeX fractions, Unicode minus, leading zeros, and a
    narrow 3+ decimal-place rounding tolerance for fraction/decimal equivalents.
    """
    if response is None or answer is None:
        return False
    response_text = str(response).strip()
    if not response_text:
        return False

    response_numeric = parse_numeric(response_text)
    response_text_norm = _normalize_text_token(response_text)

    for candidate in _reference_variants(answer):
        candidate_numeric = parse_numeric(candidate)
        if response_numeric is not None and candidate_numeric is not None:
            if _approx_equal(response_numeric, candidate_numeric):
                return True
            continue
        if response_text_norm and response_text_norm == _normalize_text_token(candidate):
            return True
    return False
