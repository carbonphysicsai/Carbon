"""One sealed-exam architecture for all five Challenges (owner rule: "any
updates/changes we make to one exam architecture/design is going to all of
them"; Validator contract VALIDATOR_EXAM_ARCHITECTURE_COMMON_20261022 §1, C2,
C3, C5, C6).

The per-Challenge checks (`motor_grid_exam`, `cold_plate_exam`,
`battery_sealed`, and F02's and F08's) become thin wrappers that supply only
their Challenge's limits and quantities. What every sealed exam shares is here:

- **labels** (`label`, `label_value`): FEASIBLE when every limit holds by more
  than its U, INFEASIBLE when any is violated by more than U, UNRESOLVED
  (neither side) otherwise. U is the Challenge's registered reference
  uncertainty; nothing here chooses one.
- **straddle** (`straddle`, C6): at least a third of all cells on each side,
  per limit; UNRESOLVED and within-U cells count on neither.
- **decision check** (`decision_check`, C5): on the reference labels the grid
  must be able to measure design value. Two registered selection rules:
  ``ROBUST`` (Motor, Cooling, F02, F08: one design must hold at every
  condition) needs a complete grid, at least one design FEASIBLE at every
  condition and at least one non-trivial condition (a feasible and an
  infeasible design). ``PER_CONDITION`` (Battery: each scenario picks its own
  candidate) needs a complete grid and, at every condition, a FEASIBLE and an
  INFEASIBLE design.
- **grid and pack fields** (`validate_grid`, `validate_pack_fields`, C2, C3):
  the cells are a complete design x condition cross, the cohort is
  ``decision_sealed_grid`` and every record carries ``design_id`` and
  ``condition_id``. A single-condition Challenge (F02, F08) is a 1-condition
  grid whose cases are the designs.

Every function returns ``None`` when the batch passes and a closed failure kind
otherwise (a failed check makes the batch unusable: one redraw, then STOP); it
raises only on a malformed input. Nothing here reads a value from a pack, draws,
solves or grades. DEVELOPMENT only: no qualification, weight, reward or LIVE
authority.
"""

from __future__ import annotations

import math
import re

FEASIBLE, INFEASIBLE, UNRESOLVED = "FEASIBLE", "INFEASIBLE", "UNRESOLVED"
#: The one cohort a sealed grid's cells carry (C3).
GRID_COHORT = "decision_sealed_grid"
ROBUST, PER_CONDITION = "robust", "per_condition"
#: ``<challenge>-dual-sealed-<shape>-v<n>`` (C3).
EVALUATION_VERSION = re.compile(
    r"[a-z0-9]+(?:-[a-z0-9]+)*-dual-sealed-[a-z0-9-]+-v[0-9]+"
)

#: Closed failure kinds.
GRID_INCOMPLETE = "decision_grid_incomplete"
NO_NONTRIVIAL_CONDITION = "decision_no_nontrivial_condition"
NO_DESIGN_FEASIBLE_EVERYWHERE = "decision_no_design_feasible_everywhere"
CONDITION_NO_FEASIBLE = "decision_condition_no_feasible"
CONDITION_NO_INFEASIBLE = "decision_condition_no_infeasible"
PACK_COHORT = "pack_cohort"
PACK_FIELDS = "pack_fields"


# --- labels -----------------------------------------------------------------------


def label(margins):
    """A cell's reference label from its ``(margin, u)`` pairs, one per limit
    (a margin is positive when the limit holds): INFEASIBLE when any margin is
    below ``-u``, FEASIBLE when every margin is above ``u``, else UNRESOLVED."""
    pairs = list(margins)
    if not pairs:
        raise ValueError("a label needs at least one limit")
    for margin, u in pairs:
        if not (math.isfinite(margin) and math.isfinite(u) and u >= 0):
            raise ValueError("a reference margin or U is not finite")
    if any(margin < -u for margin, u in pairs):
        return INFEASIBLE
    if all(margin > u for margin, u in pairs):
        return FEASIBLE
    return UNRESOLVED


def margin(value, threshold, feasible="<="):
    """The signed margin of ``value`` to ``threshold``: positive when the limit
    holds (``feasible`` is ``"<="`` for an upper limit, ``">="`` for a lower)."""
    if feasible not in ("<=", ">="):
        raise ValueError("a limit is <= or >=")
    return threshold - value if feasible == "<=" else value - threshold


def label_value(limits):
    """`label` for ``(value, threshold, feasible, u)`` limits."""
    return label((margin(v, t, f), u) for v, t, f, u in limits)


# --- straddle (C6) ----------------------------------------------------------------


def straddle(sides_by_limit, *, min_fraction=1 / 3, unresolved_max_fraction=None):
    """``None`` when, for every limit, each side holds at least ``min_fraction``
    of all cells, else ``straddle_short:<limit>`` (or, with
    ``unresolved_max_fraction``, ``unresolved_over_fraction:<limit>`` when more
    cells than that fraction are on neither side).

    ``sides_by_limit`` maps a limit name to one entry per cell: FEASIBLE,
    INFEASIBLE, or anything else (UNRESOLVED, within U, ``None``) for neither."""
    if not sides_by_limit:
        raise ValueError("a straddle needs at least one limit")
    for name, sides in sides_by_limit.items():
        sides = list(sides)
        n = len(sides)
        if n == 0:
            raise ValueError("a straddle needs cells")
        feasible, infeasible = sides.count(FEASIBLE), sides.count(INFEASIBLE)
        neither = n - feasible - infeasible
        if (
            unresolved_max_fraction is not None
            and neither > unresolved_max_fraction * n
        ):
            return f"unresolved_over_fraction:{name}"
        if min(feasible, infeasible) < min_fraction * n:
            return f"straddle_short:{name}"
    return None


# --- grid and pack fields (C2, C3) --------------------------------------------------


def _ids(cells):
    designs, conditions, seen = set(), set(), set()
    for cell in cells:
        design, condition = cell.get("design_id"), cell.get("condition_id")
        if not (
            type(design) is str and design and type(condition) is str and condition
        ):
            return None
        if (design, condition) in seen:
            return None
        seen.add((design, condition))
        designs.add(design)
        conditions.add(condition)
    return designs, conditions, seen


def validate_grid(cells, *, shape=None):
    """``None`` when ``cells`` (dicts with ``design_id`` and ``condition_id``)
    are a complete design x condition cross with no repeated cell, and, when
    ``shape`` is ``(designs, conditions)``, of exactly that shape; else
    ``decision_grid_incomplete``. A 1-condition grid is a Challenge whose
    cases are the designs."""
    cells = list(cells)
    found = _ids(cells)
    if found is None or not cells:
        return GRID_INCOMPLETE
    designs, conditions, seen = found
    if len(seen) != len(designs) * len(conditions):
        return GRID_INCOMPLETE
    if shape is not None and (len(designs), len(conditions)) != tuple(shape):
        return GRID_INCOMPLETE
    return None


def validate_pack_fields(cohorts, records, *, shape=None):
    """``None`` when every cell sits in `GRID_COHORT`, carries ``design_id`` and
    ``condition_id`` on its record, and the cells are a complete grid of
    ``shape``; else ``pack_cohort``, ``pack_fields`` or
    ``decision_grid_incomplete``."""
    cohorts, records = list(cohorts), list(records)
    if not cohorts or len(cohorts) != len(records):
        return PACK_FIELDS
    if any(c != GRID_COHORT for c in cohorts):
        return PACK_COHORT
    if any(
        type(r) is not dict
        or type(r.get("design_id")) is not str
        or not r["design_id"]
        or type(r.get("condition_id")) is not str
        or not r["condition_id"]
        for r in records
    ):
        return PACK_FIELDS
    return validate_grid(records, shape=shape)


def evaluation_version_ok(name):
    """Whether ``name`` is ``<challenge>-dual-sealed-<shape>-v<n>`` (C3)."""
    return type(name) is str and EVALUATION_VERSION.fullmatch(name) is not None


# --- the decision check (C5) ---------------------------------------------------------


def decision_check(cells, label_of, *, choice=ROBUST, shape=None):
    """``None`` when the grid can measure design value on its reference labels,
    else a closed failure kind.

    ``cells`` are dicts with ``design_id`` and ``condition_id``; ``label_of``
    maps a cell to FEASIBLE / INFEASIBLE / UNRESOLVED (the Challenge's own
    quantities and U, via `label`). ``choice`` is the Challenge's registered
    selection rule (see the module docstring)."""
    cells = list(cells)
    if validate_grid(cells, shape=shape) is not None:
        return GRID_INCOMPLETE
    labels = {(c["design_id"], c["condition_id"]): label_of(c) for c in cells}
    designs = sorted({d for d, _ in labels})
    conditions = sorted({k for _, k in labels})
    sides = {k: {labels[(d, k)] for d in designs} for k in conditions}
    if choice == ROBUST:
        if not any(sides[k] >= {FEASIBLE, INFEASIBLE} for k in conditions):
            return NO_NONTRIVIAL_CONDITION
        if not any(
            all(labels[(d, k)] == FEASIBLE for k in conditions) for d in designs
        ):
            return NO_DESIGN_FEASIBLE_EVERYWHERE
        return None
    if choice == PER_CONDITION:
        for k in conditions:
            if FEASIBLE not in sides[k]:
                return CONDITION_NO_FEASIBLE
            if INFEASIBLE not in sides[k]:
                return CONDITION_NO_INFEASIBLE
        return None
    raise ValueError("a selection rule is robust or per_condition")


__all__ = [
    "CONDITION_NO_FEASIBLE",
    "CONDITION_NO_INFEASIBLE",
    "FEASIBLE",
    "GRID_COHORT",
    "GRID_INCOMPLETE",
    "INFEASIBLE",
    "NO_DESIGN_FEASIBLE_EVERYWHERE",
    "NO_NONTRIVIAL_CONDITION",
    "PACK_COHORT",
    "PACK_FIELDS",
    "PER_CONDITION",
    "ROBUST",
    "UNRESOLVED",
    "decision_check",
    "evaluation_version_ok",
    "label",
    "label_value",
    "margin",
    "straddle",
    "validate_grid",
    "validate_pack_fields",
]


# --- the pack set and the version's aggregate (OWNER-FULL-EXAM-BANK-01) -----------------
#
# A Challenge version's exam is the union of its active sealed batches. The signed
# pack-set manifest lists the batch packs by manifest digest; the digest of its
# canonical body is the evaluation key KOTH compares on. A rotation is a new
# manifest and so a new key; the king is regraded on it before any comparison.
#
# v2 (VALIDATOR-KOTH-CARRY-SCOPE-01): the body names the Challenge, its sealed
# evaluation version and the batches, and leaves the construction version out, so
# a construction-only successor (F08 1.4 -> 1.5) serving the same batches has the
# same key. A version with no registered sealed exam keys by its construction
# version (`sealed_versions.ladder_key`), which can never equal an evaluation
# version. Prospective: a v1 set keeps its stored key and meaning, and
# `pack_set_key` still verifies a v1 body (`pack_set_document_v1`).

PACK_SET_SCHEMA = "carbon.sealed-exam.pack-set.v2"
PACK_SET_SCHEMA_V1 = "carbon.sealed-exam.pack-set.v1"
SET_REFUSED = "pack_set_malformed"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


class PackSetRefused(ValueError):
    """A typed refusal: the code names the check, never a pack's content."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _set_batches(challenge_id, challenge_version, batch_digests):
    if type(challenge_id) is not str or not challenge_id:
        raise PackSetRefused(SET_REFUSED)
    if type(challenge_version) is not str or not challenge_version:
        raise PackSetRefused(SET_REFUSED)
    digests = list(batch_digests)
    if (
        not digests
        or any(type(d) is not str or not _DIGEST.fullmatch(d) for d in digests)
        or len(set(digests)) != len(digests)
    ):
        raise PackSetRefused(SET_REFUSED)
    return sorted(digests)


def pack_set_document(challenge_id, challenge_version, batch_digests):
    """The pack-set body (v2): the Challenge, the sealed evaluation version that
    grades this construction version, and its active batch packs' manifest
    digests, sorted and distinct so one set has one body. At least one batch is
    required; a rehearsal batch is never listed (the caller's rule)."""
    from carbon.scoring.sealed_versions import ladder_key

    batches = _set_batches(challenge_id, challenge_version, batch_digests)
    return {
        "schema": PACK_SET_SCHEMA,
        "challenge_id": challenge_id,
        "evaluation_version": ladder_key(challenge_id, challenge_version),
        "batches": batches,
    }


def pack_set_document_v1(challenge_id, challenge_version, batch_digests):
    """The historical v1 body, which named the construction version. Read only:
    it rebuilds the key of a set stored before v2; no new set is keyed by it."""
    batches = _set_batches(challenge_id, challenge_version, batch_digests)
    return {
        "schema": PACK_SET_SCHEMA_V1,
        "challenge": {"id": challenge_id, "version": challenge_version},
        "batches": batches,
    }


def pack_set_key(document):
    """The evaluation key: the digest of the canonical body. Refuses a body that
    is not exactly what `pack_set_document` (v2) or `pack_set_document_v1`
    builds."""
    import hashlib
    import json

    if type(document) is not dict:
        raise PackSetRefused(SET_REFUSED)
    if document.get("schema") == PACK_SET_SCHEMA and set(document) == {
        "schema",
        "challenge_id",
        "evaluation_version",
        "batches",
    }:
        evaluation_version = document["evaluation_version"]
        if type(evaluation_version) is not str or not evaluation_version:
            raise PackSetRefused(SET_REFUSED)
        rebuilt = {
            "schema": PACK_SET_SCHEMA,
            "challenge_id": document["challenge_id"],
            "evaluation_version": evaluation_version,
            "batches": _set_batches(
                document["challenge_id"], evaluation_version, document["batches"]
            ),
        }
    elif document.get("schema") == PACK_SET_SCHEMA_V1 and set(document) == {
        "schema",
        "challenge",
        "batches",
    }:
        challenge = document["challenge"]
        if type(challenge) is not dict or set(challenge) != {"id", "version"}:
            raise PackSetRefused(SET_REFUSED)
        rebuilt = pack_set_document_v1(
            challenge["id"], challenge["version"], document["batches"]
        )
    else:
        raise PackSetRefused(SET_REFUSED)
    if rebuilt != document:
        raise PackSetRefused(SET_REFUSED)
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def verified_pack_set(challenge_id, challenge_version, batch_digests, set_key):
    """The body whose key is `set_key` for these batches: the v2 body, or - for
    a set stored before v2 - its v1 body, which keeps its key and meaning.
    Refuses a key that neither builds."""
    for build in (pack_set_document, pack_set_document_v1):
        document = build(challenge_id, challenge_version, batch_digests)
        if pack_set_key(document) == set_key:
            return document
    raise PackSetRefused("pack_set_key_mismatch")


def _unit(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1


def aggregate(batches, *, value_weight=0.5):
    """The version's grade from its batches' measurements.

    ``batches`` is one measurement per active batch, each ``{"gates": {name:
    bool}, "A": float|None, "D": float|None}`` as the Challenge's grader returns
    it for that batch's full grid. Every batch must carry the same gate names;
    a gate passes only if it passes on every batch (one failed batch makes the
    version ineligible: "not eligible", never a number). The version's A and D
    are the equal-weight means over the batches and the total is
    ``(1 - w)*A + w*D`` in 0..1. Refuses an empty list, differing gate sets, or a
    non-finite leg on an eligible version."""
    if type(batches) not in (list, tuple) or not batches:
        raise PackSetRefused("aggregate_no_batches")
    if not (type(value_weight) in (int, float) and 0 < value_weight < 1):
        raise PackSetRefused("aggregate_weight")
    names = None
    for batch in batches:
        gates = batch.get("gates") if type(batch) is dict else None
        if type(gates) is not dict or not gates:
            raise PackSetRefused("aggregate_gates")
        if names is None:
            names = set(gates)
        elif set(gates) != names:
            raise PackSetRefused("aggregate_gate_names")
    gates = {
        name: all(bool(batch["gates"][name]) for batch in batches)
        for name in sorted(names)
    }
    eligible = all(gates.values())
    result = {
        "batches": len(batches),
        "gates": gates,
        "eligible": eligible,
        "A": None,
        "D": None,
        "total": None,
        "per_batch": [
            {"A": b.get("A"), "D": b.get("D"), "eligible": all(b["gates"].values())}
            for b in batches
        ],
    }
    if not eligible:
        return result
    if not all(_unit(b.get("A")) and _unit(b.get("D")) for b in batches):
        raise PackSetRefused("aggregate_legs")
    a = math.fsum(b["A"] for b in batches) / len(batches)
    d = math.fsum(b["D"] for b in batches) / len(batches)
    result.update(A=a, D=d, total=(1 - value_weight) * a + value_weight * d)
    return result
