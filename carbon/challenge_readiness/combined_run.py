"""One combined admission run: the parts every Challenge shares.

OWNER-ADMISSION-COMBINED-01 (2026-10-02): construction, attack and value run
as one test per Challenge and ladder rung. Each run has one frozen sheet, one
panel, one fresh confirmation set and three verdicts that are never blended.
This module holds what is the same for every Challenge. A Challenge's adapter
supplies every value from its own registered records (for battery EV5:
`carbon.battery.value.ev5`).

- **Fresh conditions.** `check_conditions` refuses any condition outside the
  Challenge's published box, repeated within the run, or already used by an
  earlier study; `repeats` lists the earlier uses.
- **Panel kinds.** A panel member is one of three kinds:
  - `RECONSTRUCTED`: a legitimate construction, rebuilt from its recipe;
  - `SYNTHETIC_CONTROL`: built from the reference answers to test one scoring
    failure mode;
  - `ATTACK_CONSTRUCTION`: an attacker's construction, rebuilt, scored and
    value-tested exactly like a real one, so an attack that only shows up as
    a value failure is still caught.
- **Attack constructions.** `admit_attack_construction` admits a declarative
  recipe from an origin the run names. It refuses participant code by name:
  executable participant code starts at construction Level 4
  (OWNER-CHALLENGE-ROADMAP-03 item 6) and needs its own isolated execution
  stage, which a combined run does not have.
- **Freeze.** `unset` names every registered value that is still missing,
  None or HUMAN_INPUT, and `refuse_freeze` refuses while any blocker remains.
  A run never freezes around an unset value.

Nothing here chooses a value, and nothing here dispatches work.
"""

from __future__ import annotations

import hashlib
import json

RECONSTRUCTED = "RECONSTRUCTED"
SYNTHETIC_CONTROL = "SYNTHETIC_CONTROL"
ATTACK_CONSTRUCTION = "ATTACK_CONSTRUCTION"
PANEL_KINDS = (RECONSTRUCTED, SYNTHETIC_CONTROL, ATTACK_CONSTRUCTION)

DECLARATIVE_RECIPE = "declarative_recipe"
PARTICIPANT_CODE = "participant_code"
ATTACK_ENTRY_KEYS = {"origin", "family", "attempt", "material", "document"}
HUMAN_INPUT = "HUMAN_INPUT"


class CombinedRunError(ValueError):
    def __init__(self, code, detail="", blockers=()):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.blockers = tuple(blockers)


def digest(value):
    """The sha256 of a value's canonical JSON."""
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(body.encode()).hexdigest()


# --- conditions --------------------------------------------------------------------


def key(condition):
    """A condition's comparison key: each coordinate rounded to 1e-9."""
    return tuple(round(float(v), 9) for v in condition)


def repeats(splits, prior):
    """Each run condition an earlier study already used, with its sources.

    `splits` maps a split name to its conditions; `prior` maps a source name
    to the conditions that source used."""
    used = {
        source: {key(c) for c in conditions} for source, conditions in prior.items()
    }
    out = []
    for split, conditions in splits.items():
        for condition in conditions:
            sources = sorted(s for s, keys in used.items() if key(condition) in keys)
            if sources:
                out.append(
                    {"split": split, "condition": list(condition), "sources": sources}
                )
    return out


def check_conditions(splits, box, prior):
    """`splits` unchanged, or a refusal by name.

    `box` is the Challenge's published (low, high) per coordinate, inclusive.
    Refuses a condition of the wrong shape, outside the box, repeated within
    the run, or used by any `prior` source."""
    seen = set()
    for split, conditions in splits.items():
        if not conditions:
            raise CombinedRunError("conditions_empty", split)
        for condition in conditions:
            if len(condition) != len(box):
                raise CombinedRunError("condition_shape", f"{split} {condition}")
            if not all(
                low <= float(v) <= high for v, (low, high) in zip(condition, box)
            ):
                raise CombinedRunError("condition_outside_box", f"{split} {condition}")
            if key(condition) in seen:
                raise CombinedRunError("condition_repeated", f"{split} {condition}")
            seen.add(key(condition))
    found = repeats(splits, prior)
    if found:
        raise CombinedRunError(
            "condition_not_fresh",
            "; ".join(f"{r['condition']} in {','.join(r['sources'])}" for r in found),
        )
    return splits


# --- attack constructions ----------------------------------------------------------


def admit_attack_construction(entry, *, origins):
    """`entry` unchanged when the run rebuilds it, or a refusal by name.

    An entry is {origin, family, attempt, material, document}. Only a
    declarative recipe (a JSON document) from one of `origins` is admitted.
    Whether the recipe compiles is the Challenge's construction contract's
    question, answered when it is rebuilt."""
    if type(entry) is not dict or set(entry) != ATTACK_ENTRY_KEYS:
        raise CombinedRunError("attack_construction_fields")
    if entry["material"] == PARTICIPANT_CODE:
        raise CombinedRunError(
            "participant_code_out_of_scope",
            "executable participant code starts at construction Level 4",
        )
    if entry["material"] != DECLARATIVE_RECIPE:
        raise CombinedRunError("attack_construction_material", str(entry["material"]))
    if entry["origin"] not in origins:
        raise CombinedRunError("attack_construction_origin", str(entry["origin"]))
    if type(entry["document"]) is not dict:
        raise CombinedRunError(
            "declarative_recipe_not_a_document", str(entry["attempt"])
        )
    return entry


# --- freeze --------------------------------------------------------------------------


def unset(values):
    """The names of registered values that are None or HUMAN_INPUT."""
    return sorted(
        name
        for name, value in values.items()
        if value is None or (type(value) is str and value.strip() == HUMAN_INPUT)
    )


def refuse_freeze(blockers):
    """Refuse to freeze while any blocker remains, naming every one."""
    blockers = list(blockers)
    if blockers:
        raise CombinedRunError("freeze_refused", "; ".join(blockers), blockers)
