"""The geometric-v1 coverage class rule (Validator 11-01, rev 2): the ONE source of the class vocabulary.

`klass` is byte-for-byte the receipted function of probe_set.py rev 4 (codex-queue SEP_PROBE_SETS_REV4_20261101, file
sha256 7464f4a461172c9ac3d1bdb4ac13b288f86dbb4a29ee3d296815340bf8f9392a), pinned by its source sha in the tests. On the
signed region, first match in this order: every input inside the TRAIN box (``region["base"]``); every input inside the
TRAIN box widened by ``INNER`` of each signed extension, not all in TRAIN; exactly one input outside the TRAIN box, the
others inside it (that input's side); else the extended shell.

`names_valid` accepts exactly the rule's 4 name forms; the side form is class_map.py rev 3's regex (codex-queue
CLASS_MAP_PLAN_REV3_20261101, file sha256 77798314f05281bff988f3dc20b9229ca9626ea2ec2cf87a191966b095ff1cfb). The grader and
the exam type no class name: they read this module (CV-B / Validator-2B 11 Nov, B1 option (a)).
"""

from __future__ import annotations

import re

INNER = 0.5
RULE = "geometric-v1"
#: class_map.py rev 3's side-name form.
SIDE = re.compile(r"regime:side_[a-z0-9_]+_(low|high)")
#: The rule's three fixed names (the fourth form is `SIDE`).
FIXED_NAMES = ("in_train", "regime:inner_band", "extended_shell")


# byte-for-byte the receipted function: its source sha is pinned, so no formatter may touch it
# fmt: off
def klass(region, names, inputs):
    """geometric-v1 (Validator 11-01), first match in this order, with the coverage plan's registered names."""
    out = [n for n in names if not region["base"][n][0] - 1e-12 <= inputs[n] <= region["base"][n][1] + 1e-12]
    if not out:
        return "in_train"
    inner = all(
        region["base"][n][0] - INNER * (region["base"][n][0] - region["extended"][n][0]) - 1e-12
        <= inputs[n]
        <= region["base"][n][1] + INNER * (region["extended"][n][1] - region["base"][n][1]) + 1e-12
        for n in names
    )
    if inner:
        return "regime:inner_band"
    if len(out) == 1:
        n = out[0]
        return f"regime:side_{n}_{'high' if inputs[n] > region['base'][n][1] else 'low'}"
    return "extended_shell"
# fmt: on


def is_name(name) -> bool:
    """Whether ``name`` is one geometric-v1 class name (class_map.py rev 3's `is_class` form). A non-str is not."""
    return type(name) is str and (
        name in FIXED_NAMES or SIDE.fullmatch(name) is not None
    )


def names_valid(classes) -> bool:
    """Whether a coverage plan's class names are all geometric-v1 names: a non-empty collection, each one of the 4 forms.
    Anything else (another form, an empty string, a non-str, no names at all) is False; there is no fallback.
    """
    names = list(classes)
    return bool(names) and all(is_name(name) for name in names)


__all__ = ["FIXED_NAMES", "INNER", "RULE", "SIDE", "is_name", "klass", "names_valid"]
