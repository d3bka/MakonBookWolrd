from urllib.parse import quote

from django import template
from django.conf import settings

register = template.Library()

# Desmos's public demo key: it works anywhere but shows a "Desmos Trial Key"
# notice. Used only until DESMOS_API_KEY is set in .env.
DESMOS_DEMO_KEY = "dcb31709b452b1cf9dc26972add0fda6"
DESMOS_API_VERSION = "v1.10"


@register.simple_tag
def desmos_calculator_src():
    """The Desmos calculator script's URL, with the key from DESMOS_API_KEY."""
    key = (getattr(settings, "DESMOS_API_KEY", "") or "").strip() or DESMOS_DEMO_KEY
    return f"https://www.desmos.com/api/{DESMOS_API_VERSION}/calculator.js?apiKey={quote(key, safe='')}"
