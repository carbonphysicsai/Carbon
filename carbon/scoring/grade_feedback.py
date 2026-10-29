"""Private-exam Ladder feedback: the one document a miner sees for a grade.

OWNER-GRADE-FEEDBACK-LADDER-01 (build spec LADDER_AND_CAP_BUILD_SPEC_20261020
section A). From one graded private-exam result per miner, Challenge and exam
version, the miner sees only a closed document:

- ``total``, rounded down to the step (v2, OWNER-FULL-EXAM-BANK-01: the total
  alone; v1 also showed A and D);
- ``status``: IMPROVED, NO_IMPROVEMENT, GATE_FAILED or NOT_SCORED;
- ``gate_names``, drawn only from the closed gate registry (the Challenge's
  registered hard gates);
- ``exam_version``, and the document's ``schema``.

The step is max(eta = 0.02, the Challenge's registered rebuild noise). Shown
values change only when a new total reaches the previous best shown total
plus the step within the same exam version; otherwise the previous shown
values repeat. A new exam version starts a fresh ladder. Nothing else from the
exam (per-case values, case ids, which cases failed, the picked design,
references, unrounded legs) can appear: the output is built field by field
from an allow-list, never by removing fields.

The ladder's state is the miner's **best** document (its last IMPROVED one),
kept apart from what each submission shows: NO_IMPROVEMENT and GATE_FAILED
repeat the best values; NOT_SCORED (indeterminate evidence, a diagnostic-only
result, infrastructure, an ineligible or invalid outcome) shows no total, A
or D at all, so a result that does not count reveals no grade (Validator,
2026-10-20; the cap releases its slot on that condition). ``next_best`` keeps
the state.

Values are rounded *down* to the step grid with exact decimal arithmetic, so a
shown value never exceeds what was earned and never depends on float error.
v4 (OWNER-DOOR-LOOKUPS-AND-PART-FEEDBACK-01; PART_FEEDBACK_GRANULARITY_20261029
sections 1 and 2) is v3 plus the miner's own per-part feedback: ``parts`` (the A and
D halves and each registered component of those legs, floored to the part step with
hysteresis), ``gates`` (every registered hard gate, pass or fail) and
``minimums_missed`` (leg names only). It is built from the same allow-list; the closed
``NEVER_SHOWN`` list names what can never appear. v1, v2 and v3 documents are never
rewritten.

This module is pure: storing the best document and serving documents to the
miner belong to the serving lane.
"""

from __future__ import annotations

import math
import re
from decimal import ROUND_FLOOR, Decimal

SCHEMA = "carbon.private-exam.ladder-feedback.v2"
SCHEMA_V1 = "carbon.private-exam.ladder-feedback.v1"
#: v3 names the submission a document is about (its recipe digest) and the epoch it
#: was graded in, in the owning hotkey's own feedback only, so a page shows a grade
#: only on the submit it belongs to. v2 is unchanged and still emitted when a
#: caller names neither.
SCHEMA_V3 = "carbon.private-exam.ladder-feedback.v3"
ETA = 0.02
FIELDS = frozenset({"schema", "exam_version", "status", "total", "gate_names"})
FIELDS_V3 = FIELDS | {"recipe_digest", "epoch"}
#: A v3 NOT_SCORED document also says why, so a miner can tell a leg below its registered
#: minimum from a candidate fault or an infrastructure failure (additive: absent on other
#: statuses and on legacy rows; readers tolerate absence). ``leg`` is the registered leg
#: NAME, only for LEG_MINIMUM_FAILED, never a number.
FIELDS_V3_NOT_SCORED = FIELDS_V3 | {"reason", "leg"}
#: v4 = v3 plus the per-part feedback. ``parts`` is {"A", "D", "components"} (None
#: unless the result counts), ``gates`` maps every registered hard gate to "pass" or
#: "fail" (None for a result that does not count), and ``minimums_missed`` lists leg
#: NAMES below their registered minimum (never a number or a margin).
SCHEMA_V4 = "carbon.private-exam.ladder-feedback.v4"
FIELDS_V4 = FIELDS_V3 | {"parts", "gates", "minimums_missed"}
FIELDS_V4_NOT_SCORED = FIELDS_V4 | {"reason", "leg"}
#: The part step is p = max(PART_FLOOR, PART_FACTOR * s), with s the total's step.
#: PROVISIONAL disclosure settings, testnet only (OWNER-OVERNIGHT-DELEGATION-01); the
#: invariant test pins p >= 2 * s so a merge cannot show a part finer than the total.
PART_FLOOR = 0.05
PART_FACTOR = 2
PARTS_FIELDS = frozenset({"A", "D", "components"})
GATE_VERDICTS = ("pass", "fail")
#: What a v4 document can never carry (closed list; the document is built from an
#: allow-list, and the tests plant each of these on a graded result to prove it).
NEVER_SHOWN = (
    "per_case_values",
    "case_ids",
    "target_ids",
    "draw_ids",
    "positions_or_conditions",
    "which_cases_failed",
    "picked_design",
    "reference_values",
    "pool",
    "set_level_split",
    "feasible_target_counts",
    "unrounded_values",
    "another_hotkeys_anything",
)
REASONS = (
    "LEG_MINIMUM_FAILED",
    "CANDIDATE_INVALID",
    "DECISION_INELIGIBLE",
    "FAILED_INFRA",
    "INDETERMINATE",
)
_REASON_OF_STATUS = {
    "REQUIRED_LEG_MINIMUM_FAILED": "LEG_MINIMUM_FAILED",
    "CANDIDATE_INVALID": "CANDIDATE_INVALID",
    "DECISION_OUTCOME_INELIGIBLE": "DECISION_INELIGIBLE",
    "FAILED_INFRA": "FAILED_INFRA",
}
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
STATUSES = ("IMPROVED", "NO_IMPROVEMENT", "GATE_FAILED", "NOT_SCORED")
#: Scoring statuses that carry a total (development now; official later).
_SCORED = frozenset({"SCORED_DEVELOPMENT_CANDIDATE"})
_GATE_FAILED = frozenset({"MANDATORY_GATE_FAILED"})


class LadderFeedbackRefused(ValueError):
    """The graded result or the ladder state cannot produce safe feedback."""


def step(rebuild_noise=None):
    """max(eta, the registered rebuild noise); eta when none is registered."""
    if rebuild_noise is None:
        return ETA
    if (
        type(rebuild_noise) not in (int, float)
        or not math.isfinite(rebuild_noise)
        or rebuild_noise < 0
    ):
        raise LadderFeedbackRefused("rebuild_noise")
    return max(ETA, float(rebuild_noise))


def floor_to_step(value, rebuild_noise=None):
    """``value`` rounded down to the Ladder step (``step(rebuild_noise)``), exactly:
    what the Ladder itself shows for a total."""
    return _floor(value, step(rebuild_noise))


def _floor(value, grid):
    """``value`` rounded down to a multiple of ``grid``, exactly."""
    if type(value) not in (int, float) or not math.isfinite(value):
        raise LadderFeedbackRefused("value")
    q = Decimal(repr(float(value))) / Decimal(repr(float(grid)))
    return float(q.to_integral_value(rounding=ROUND_FLOOR) * Decimal(repr(float(grid))))


def shape(document):
    """``SCHEMA`` or ``SCHEMA_V3`` when ``document`` has exactly that version's
    fields, else None."""
    if type(document) is not dict:
        return None
    if set(document) == FIELDS and document.get("schema") == SCHEMA:
        return SCHEMA
    if set(document) == FIELDS_V3 and document.get("schema") == SCHEMA_V3:
        return SCHEMA_V3
    if document.get("schema") == SCHEMA_V4:
        not_scored = document.get("status") == "NOT_SCORED"
        fields = FIELDS_V4_NOT_SCORED if not_scored else FIELDS_V4
        if set(document) == fields and (
            not not_scored
            or (
                document["reason"] in REASONS
                and (
                    document["leg"] is None
                    if document["reason"] != "LEG_MINIMUM_FAILED"
                    else document["leg"] is None or type(document["leg"]) is str
                )
            )
        ):
            return SCHEMA_V4
        return None
    if (
        set(document) == FIELDS_V3_NOT_SCORED
        and document.get("schema") == SCHEMA_V3
        and document.get("status") == "NOT_SCORED"
        and document.get("reason") in REASONS
        and (
            document["leg"] is None
            if document["reason"] != "LEG_MINIMUM_FAILED"
            else document["leg"] is None or type(document["leg"]) is str
        )
    ):
        return SCHEMA_V3
    return None


def part_step(rebuild_noise=None):
    """The part step p = max(0.05, 2 * s), s being the total's step: a part is never
    shown finer than the total (PROVISIONAL disclosure setting, testnet only)."""
    return grid_of_parts(step(rebuild_noise))


def shown_part(value, previous, grid):
    """What the miner sees for one part (PART_FEEDBACK_GRANULARITY section 2).

    ``previous`` is the part's last shown value (None before the first). A new value
    is shown only when the true ``value`` has moved a full step from it, up or down;
    otherwise ``previous`` repeats. A shown value is ``value`` floored to the grid.
    Plain rounding would flip a part at a grid edge on a tiny change, which is the
    signal a hill-climbing attacker uses."""
    if type(value) not in (int, float) or not math.isfinite(value):
        raise LadderFeedbackRefused("part_value")
    if previous is None:
        return _floor(value, grid)
    if type(previous) not in (int, float) or not math.isfinite(previous):
        raise LadderFeedbackRefused("part_state")
    if abs(Decimal(repr(float(value))) - Decimal(repr(float(previous)))) >= Decimal(
        repr(float(grid))
    ):
        return _floor(value, grid)
    return float(previous)


def _registry(parts_registry):
    """``{"A": (metric, ...), "D": (metric, ...)}`` as registered by the score
    pack's legs; anything else is refused."""
    if (
        type(parts_registry) is not dict
        or set(parts_registry) != {"A", "D"}
        or not all(
            type(names) in (list, tuple)
            and all(type(name) is str and name for name in names)
            and len(set(names)) == len(names)
            for names in parts_registry.values()
        )
    ):
        raise LadderFeedbackRefused("parts_registry")
    return {leg: tuple(names) for leg, names in parts_registry.items()}


def _parts(graded, registry, state, grid):
    """The ``parts`` block of a result that counts, read only from the graded
    result's registered legs and components, each through the hysteresis."""
    legs = graded.get("legs")
    if type(legs) is not dict or not {"A", "D"} <= set(legs):
        raise LadderFeedbackRefused("parts_legs")
    state = {} if state is None else state
    if type(state) is not dict or not set(state) <= PARTS_FIELDS:
        raise LadderFeedbackRefused("parts_state")
    components = graded.get("components")
    registered = {name for names in registry.values() for name in names}
    if components is not None and type(components) is not dict:
        raise LadderFeedbackRefused("parts_components")
    previous = state.get("components") or {}
    if type(previous) is not dict:
        raise LadderFeedbackRefused("parts_state")
    shown = {}
    for name in sorted(registered):
        value = (components or {}).get(name)
        # A component the result does not carry (a set-level aggregate carries only
        # the halves) is not shown; one that is null is not shown either.
        if type(value) in (int, float) and math.isfinite(value):
            shown[name] = shown_part(value, previous.get(name), grid)
    return {
        "A": shown_part(legs["A"], state.get("A"), grid),
        "D": shown_part(legs["D"], state.get("D"), grid),
        "components": shown,
    }


def _gate_verdicts(gates, registry):
    """Every registered hard gate as "pass" or "fail". An unregistered gate, a
    missing one or any other verdict is refused."""
    if type(gates) is not dict or set(gates) != set(registry):
        raise LadderFeedbackRefused("gate_registry")
    out = {}
    for name in sorted(registry):
        verdict = gates[name]
        if verdict not in ("PASS", "FAIL"):
            raise LadderFeedbackRefused("gate_verdict")
        out[name] = verdict.lower()
    return out


def _minimums_missed(graded, leg_minimums):
    """The registered leg NAMES below their registered minimum, in pack order
    (empty while no minimum is set): names only, never a number or a margin."""
    legs, missed = graded.get("legs"), []
    if type(legs) is dict and type(leg_minimums) is dict:
        for name, value in legs.items():
            minimum = leg_minimums.get(name)
            if (
                type(name) is str
                and type(value) in (int, float)
                and type(minimum) in (int, float)
                and value < minimum
            ):
                missed.append(name)
    return missed


def _reason(graded, leg_minimums):
    """``(reason, leg)`` for a result that does not count. The leg is the first
    registered leg (in the pack's order) whose value is below its minimum, and only for
    LEG_MINIMUM_FAILED; it is None when the minimums are not supplied."""
    reason = _REASON_OF_STATUS.get(graded["status"], "INDETERMINATE")
    leg = None
    legs = graded.get("legs")
    if (
        reason == "LEG_MINIMUM_FAILED"
        and type(legs) is dict
        and type(leg_minimums) is dict
    ):
        for name, value in legs.items():
            minimum = leg_minimums.get(name)
            if (
                type(name) is str
                and type(value) in (int, float)
                and type(minimum) in (int, float)
                and value < minimum
            ):
                leg = name
                break
    return reason, leg


def _document(exam_version, status, values, gate_names, about=None, why=None):
    document = {
        "schema": SCHEMA,
        "exam_version": exam_version,
        "status": status,
        "total": values.get("total"),
        "gate_names": list(gate_names),
    }
    expected = FIELDS
    if about is not None:
        document.update(schema=SCHEMA_V3, **about)
        expected = FIELDS_V3
        if status == "NOT_SCORED" and why is not None:
            document.update(reason=why[0], leg=why[1])
            expected = FIELDS_V3_NOT_SCORED
    if set(document) != expected or status not in STATUSES:
        raise LadderFeedbackRefused("document_fields")
    return document


def _document_v4(
    exam_version, status, total, failed, about, *, parts, gates, missed, why=None
):
    """A v4 document, field by field from the allow-list (never by removing fields)."""
    document = {
        "schema": SCHEMA_V4,
        "exam_version": exam_version,
        "status": status,
        "total": total,
        "gate_names": list(failed),
        **about,
        "parts": parts,
        "gates": gates,
        "minimums_missed": list(missed),
    }
    expected = FIELDS_V4
    if status == "NOT_SCORED":
        document.update(reason=why[0], leg=why[1])
        expected = FIELDS_V4_NOT_SCORED
    if set(document) != expected or status not in STATUSES:
        raise LadderFeedbackRefused("document_fields")
    return document


def next_best(best, document):
    """The ladder state after ``document``: it replaces ``best`` only when it
    improved, and a document for another exam version starts a fresh state."""
    if document["status"] == "IMPROVED":
        return document
    if best is not None and best["exam_version"] != document["exam_version"]:
        return None
    return best


def ladder_feedback(
    graded,
    *,
    best,
    exam_version,
    gate_registry,
    rebuild_noise,
    recipe_digest=None,
    epoch=None,
    leg_minimums=None,
    parts_registry=None,
    parts_state=None,
):
    """The miner's feedback document for one graded result.

    ``graded`` is the ScoreEngine's row for the miner's model (``status``,
    ``score``, ``legs``, ``gates``); ``best`` the miner's best document for
    this Challenge (its last IMPROVED one, see ``next_best``), or None;
    ``gate_registry`` the Challenge's closed set of registered gate names;
    ``rebuild_noise`` its registered value, or None when none is registered.
    It has no default, so a caller that forgets it fails instead of silently
    showing values finer than the registered noise allows.

    With ``recipe_digest`` and ``epoch`` (both or neither) the document is v3 and
    names the submission it is about; without them it is v2, unchanged. A
    ``best`` of either version is accepted: the best carries a total, never a
    submission's identity.

    With ``parts_registry`` (the score pack's registered component names per leg,
    ``{"A": [...], "D": [...]}``) the document is v4: v3 plus the per-part feedback.
    ``parts_state`` is the miner's last shown ``parts`` for this exam (None before the
    first), the hysteresis state; a v4 document names its submission, so ``recipe_digest``
    and ``epoch`` are required with it.
    """
    if (recipe_digest is None) != (epoch is None):
        raise LadderFeedbackRefused("about")
    registry4 = None if parts_registry is None else _registry(parts_registry)
    if registry4 is not None and recipe_digest is None:
        raise LadderFeedbackRefused("about")
    about = None
    if recipe_digest is not None:
        if (
            type(recipe_digest) is not str
            or _DIGEST.fullmatch(recipe_digest) is None
            or type(epoch) is not int
            or epoch < 0
        ):
            raise LadderFeedbackRefused("about")
        about = {"recipe_digest": recipe_digest, "epoch": epoch}
    if type(exam_version) is not str or not exam_version:
        raise LadderFeedbackRefused("exam_version")
    registry = frozenset(gate_registry)
    if not registry or not all(type(name) is str and name for name in registry):
        raise LadderFeedbackRefused("gate_registry")
    if best is not None and (shape(best) is None or best["status"] != "IMPROVED"):
        raise LadderFeedbackRefused("best")
    grid = step(rebuild_noise)
    # A new exam version starts a fresh ladder.
    if best is not None and best["exam_version"] != exam_version:
        best = None
    none = {"total": None}
    shown = {"total": best["total"]} if best is not None else none
    if type(graded) is not dict or type(graded.get("status")) is not str:
        raise LadderFeedbackRefused("graded")
    status = graded["status"]
    if registry4 is not None:
        return _feedback_v4(
            graded,
            status,
            best=best,
            shown=shown,
            exam_version=exam_version,
            gate_registry=registry,
            registry=registry4,
            grid=grid,
            about=about,
            leg_minimums=leg_minimums,
            parts_state=parts_state,
        )
    if status in _GATE_FAILED:
        gates = graded.get("gates")
        if type(gates) is not dict or not set(gates) <= registry:
            raise LadderFeedbackRefused("gate_registry")
        failed = sorted(name for name, verdict in gates.items() if verdict == "FAIL")
        if not failed:
            raise LadderFeedbackRefused("gate_failed_without_gate")
        return _document(exam_version, "GATE_FAILED", shown, failed, about)
    if status not in _SCORED:
        # A result that does not count reveals no grade.
        return _document(
            exam_version, "NOT_SCORED", none, (), about, _reason(graded, leg_minimums)
        )
    total = graded.get("score")
    rounded = {"total": _floor(total, grid)}
    if shown["total"] is not None and not total >= shown["total"] + grid:
        return _document(exam_version, "NO_IMPROVEMENT", shown, (), about)
    return _document(exam_version, "IMPROVED", rounded, (), about)


def _feedback_v4(
    graded,
    status,
    *,
    best,
    shown,
    exam_version,
    gate_registry,
    registry,
    grid,
    about,
    leg_minimums,
    parts_state,
):
    """The v4 document for one graded result, by status (PART_FEEDBACK_GRANULARITY
    section 1): IMPROVED and NO_IMPROVEMENT show the total (the ladder rule as in v3),
    the parts and the gates; GATE_FAILED shows the gates only, no numbers; NOT_SCORED
    shows its reason (and the leg's name) only."""
    if status in _GATE_FAILED:
        verdicts = _gate_verdicts(graded.get("gates"), gate_registry)
        failed = sorted(name for name, verdict in verdicts.items() if verdict == "fail")
        if not failed:
            raise LadderFeedbackRefused("gate_failed_without_gate")
        return _document_v4(
            exam_version, "GATE_FAILED", None, failed, about,
            parts=None, gates=verdicts, missed=[],
        )  # fmt: skip
    if status not in _SCORED:
        reason, leg = _reason(graded, leg_minimums)
        return _document_v4(
            exam_version, "NOT_SCORED", None, (), about,
            parts=None, gates=None, missed=[] if leg is None else [leg], why=(reason, leg),
        )  # fmt: skip
    verdicts = _gate_verdicts(graded.get("gates"), gate_registry)
    if any(verdict != "pass" for verdict in verdicts.values()):
        raise LadderFeedbackRefused("scored_with_failed_gate")
    parts = _parts(graded, registry, parts_state, grid_of_parts(grid))
    missed = _minimums_missed(graded, leg_minimums)
    total = graded.get("score")
    if shown["total"] is not None and not total >= shown["total"] + grid:
        return _document_v4(
            exam_version, "NO_IMPROVEMENT", shown["total"], (), about,
            parts=parts, gates=verdicts, missed=missed,
        )  # fmt: skip
    return _document_v4(
        exam_version, "IMPROVED", _floor(total, grid), (), about,
        parts=parts, gates=verdicts, missed=missed,
    )  # fmt: skip


def grid_of_parts(total_step):
    """The part step for a total step ``s``: max(0.05, 2 * s)."""
    return max(PART_FLOOR, PART_FACTOR * total_step)
