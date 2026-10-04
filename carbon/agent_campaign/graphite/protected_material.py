"""Graphite's protected-material check, as a leaf both its users import.

`tools.protected` refuses a tool request or result that names protected
material (GRAPHITE-D5), and `literature` refuses a card that names it when an
index is built - including the fixture index built when `literature` is
imported. `tools` imports `literature`, so the check cannot live in `tools`
without an import cycle: importing `tools` first would build the fixture
index while `tools` was still initialising. It lives here, importing nothing
from Graphite; `tools` re-exports it unchanged (`tools.protected`,
`tools.PROTECTED_MARKERS`).
"""

from __future__ import annotations

import json

from .. import boundaries

#: Graphite's markers beyond the checkout deny rules. Lower-case substrings.
PROTECTED_MARKERS = (
    "official_seed",
    "official-seed",
    "official seed",
    "derived_seed",
    "derived-seed",
    "draw_id",
    "draw-id",
    "protected_exam",
    "protected-exam",
    "protected exam",
    "hidden_case",
    "hidden-case",
    "verification_reference",
    "verification-reference",
    "verification reference",
    "validator_private",
    "private_validator",
    "private validator",
    boundaries.CANARY_PREFIX.lower(),
)


def _strings(value):
    """Every string in a JSON value, including JSON encoded inside strings."""
    if type(value) is str:
        yield value
        try:
            inner = json.loads(value)
        except (ValueError, RecursionError):
            return
        if type(inner) in (dict, list):
            yield from _strings(inner)
    elif type(value) is dict:
        for key, item in value.items():
            yield str(key)
            yield from _strings(item)
    elif type(value) in (list, tuple):
        for item in value:
            yield from _strings(item)


def _protected_text(text):
    lowered = text.lower()
    return boundaries._denied(lowered) or any(
        marker in lowered for marker in PROTECTED_MARKERS
    )


def protected(value):
    """True when any string in `value` names protected material."""
    return any(_protected_text(text) for text in _strings(value))
