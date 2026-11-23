"""V98: the official SAT content domains and skills (College Board).

Imported questions get a domain (QuestionDomain) and a skill (QuestionType).
Mistake analysis and topic practice group questions by these names, so imports
use exactly these spellings.
"""
from __future__ import annotations

ENGLISH_DOMAINS = {
    "Information and Ideas": [
        "Central Ideas and Details",
        "Command of Evidence",
        "Inferences",
    ],
    "Craft and Structure": [
        "Words in Context",
        "Text Structure and Purpose",
        "Cross-Text Connections",
    ],
    "Expression of Ideas": [
        "Rhetorical Synthesis",
        "Transitions",
    ],
    "Standard English Conventions": [
        "Boundaries",
        "Form, Structure, and Sense",
    ],
}

MATH_DOMAINS = {
    "Algebra": [
        "Linear equations in one variable",
        "Linear functions",
        "Linear equations in two variables",
        "Systems of two linear equations in two variables",
        "Linear inequalities in one or two variables",
    ],
    "Advanced Math": [
        "Nonlinear functions",
        "Nonlinear equations in one variable and systems of equations in two variables",
        "Equivalent expressions",
    ],
    "Problem-Solving and Data Analysis": [
        "Ratios, rates, proportional relationships, and units",
        "Percentages",
        "One-variable data: Distributions and measures of center and spread",
        "Two-variable data: Models and scatterplots",
        "Probability and conditional probability",
        "Inference from sample statistics and margin of error",
        "Evaluating statistical claims: Observational studies and experiments",
    ],
    "Geometry and Trigonometry": [
        "Area and volume",
        "Lines, angles, and triangles",
        "Right triangles and trigonometry",
        "Circles",
    ],
}

DOMAINS = {"english": ENGLISH_DOMAINS, "math": MATH_DOMAINS}

# Short names people and converters often write.
_ALIASES = {
    "geometry": "Geometry and Trigonometry",
    "trigonometry": "Geometry and Trigonometry",
    "geometry and trig": "Geometry and Trigonometry",
    "problem solving and data analysis": "Problem-Solving and Data Analysis",
    "problem-solving": "Problem-Solving and Data Analysis",
    "problem solving": "Problem-Solving and Data Analysis",
    "data analysis": "Problem-Solving and Data Analysis",
    "psda": "Problem-Solving and Data Analysis",
    "advanced math": "Advanced Math",
    "advanced mathematics": "Advanced Math",
    "information & ideas": "Information and Ideas",
    "craft & structure": "Craft and Structure",
    "expression of ideas": "Expression of Ideas",
    "standard english conventions": "Standard English Conventions",
    "sec": "Standard English Conventions",
    "conventions": "Standard English Conventions",
    "grammar": "Standard English Conventions",
}


def _key(value):
    return " ".join(str(value or "").replace("–", "-").replace("—", "-").lower().split())


def domain_choices(section=None):
    sections = [section] if section in DOMAINS else ["english", "math"]
    return [name for s in sections for name in DOMAINS[s]]


def canonical_domain(name, section=None):
    """The official spelling of a domain for this section, or "" when unknown."""
    wanted = _key(name)
    if not wanted:
        return ""
    allowed = domain_choices(section)
    for official in allowed:
        if _key(official) == wanted:
            return official
    alias = _ALIASES.get(wanted)
    return alias if alias in allowed else ""


def canonical_skill(domain, name):
    """The official spelling of a skill when it matches one; otherwise the text as given."""
    text = " ".join(str(name or "").split())[:120]
    for skills in DOMAINS.values():
        for official in skills.get(domain, []):
            if _key(official) == _key(text):
                return official
    return text


def taxonomy_text():
    """The list, as text for AI instructions and the conversion prompt."""
    lines = []
    for section, label in (("english", "Reading & Writing"), ("math", "Math")):
        lines.append(f"{label}:")
        for domain, skills in DOMAINS[section].items():
            lines.append(f"- {domain}: " + "; ".join(skills))
    return "\n".join(lines)
