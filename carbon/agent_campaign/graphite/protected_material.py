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
    # The sealed tuning set (OWNER-GRAPHITE-TEST-WAVE-08 §1; VALIDATOR-17).
    "graphite-tuning",
    "graphite_tuning",
    "tuning_set",
    "tuning-set",
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


#: Each marker's class: a category name that is never a marker itself and
#: never trips the check (`test_graphite_pod_gpu_probe`). A withheld record
#: may name the class; it never carries a marker or the matched text
#: (GRAPHITE-POD-GPU-PROBE-01). Every marker has exactly one class.
MARKER_CLASSES = {
    "seed_material": (
        "official_seed",
        "official-seed",
        "official seed",
        "derived_seed",
        "derived-seed",
    ),
    "draw_material": ("draw_id", "draw-id"),
    "exam_material": (
        "protected_exam",
        "protected-exam",
        "protected exam",
        "hidden_case",
        "hidden-case",
        "graphite-tuning",
        "graphite_tuning",
        "tuning_set",
        "tuning-set",
    ),
    "reference_material": (
        "verification_reference",
        "verification-reference",
        "verification reference",
    ),
    "validator_state": ("validator_private", "private_validator", "private validator"),
    "tripwire": (boundaries.CANARY_PREFIX.lower(),),
}
#: The class of a match of the checkout deny rule (`boundaries._denied`)
#: that no Graphite marker explains.
CHECKOUT_DENY_CLASS = "checkout_deny_rule"


def marker_classes(value):
    """The sorted class names of the protected material `value` names: class
    names only, never a marker or the text that matched."""
    found = set()
    for text in _strings(value):
        lowered = text.lower()
        hit = False
        for name, markers in MARKER_CLASSES.items():
            if any(marker in lowered for marker in markers):
                found.add(name)
                hit = True
        if not hit and boundaries._denied(lowered):
            found.add(CHECKOUT_DENY_CLASS)
    return sorted(found)


#: The checkout deny fragments that name sealed or confirmation material, as
#: against the attack targets (`.env`, `secret`, `credential` and the deny
#: prefixes' repository paths).
MATERIAL_FRAGMENTS = ("ev4", "ev5", "confirmation", "canary")
#: `result_material`'s answers.
PROTECTED_MATERIAL, ATTACK_TARGET = "protected_material", "attack_target"


def result_material(value):
    """Why a withheld result was withheld: `protected_material` when a string
    names one of Graphite's markers or a fragment naming sealed or
    confirmation material; `attack_target` when only the deny rule's attack
    targets matched. Recorded on the refusal (the content stays withheld
    either way), so Carbon's attack analysis never reads a path that answered
    with an attack target as an exposure."""
    for text in _strings(value):
        lowered = text.lower()
        if any(marker in lowered for marker in PROTECTED_MARKERS) or any(
            fragment in lowered for fragment in MATERIAL_FRAGMENTS
        ):
            return PROTECTED_MATERIAL
    return ATTACK_TARGET
