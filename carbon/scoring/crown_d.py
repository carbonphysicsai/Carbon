"""Crown-time D: the design value of a challenger that could take the crown (pure logic, custody only).

When a challenger could change the crown, OUR fixed optimizer (`pool_model_search.model_search`, the proof settings)
runs on the challenger's model and picks one design per target. That pick gets one reference solve (an injected
solver wrapper; nothing here solves). The solved result is scored against the version's sealed "zero": per target, the
best of three cheap baselines (the registered shortcut's solved pick, a TRAIN-only fit's solved pick, the best TRAIN
design), computed once per exam version and registered by sha256.

- `CrownDRule`: the version's registered block. Every field is an owner / Validator value with no default; a None
  (HUMAN_INPUT) refuses, so a version without a complete block never runs crown-time D.
- `zero_record` / `attach_zero`: the sealed zero, checked against the registered sha and the targets.
- `pick`: the fixed optimizer's one design per target.
- `dedupe_key`: picks within half a grid cell of the unit box share one solve.
- `needs_fine`: the coarse result is too close to a limit or to the zero to trust, so the fine rung is solved.
- `target_d`: one target's D in [0, 1]; `decide`: the challenger's D, or a hold, per the scope's hold rule.

Signed objective: s = +objective for sense "max", -objective for "min", so larger s is always better.

Fail closed: a malformed rule, zero or result raises `CrownDRefused` with a closed snake_case `code` (Carbon's material,
never the candidate's failure). A HOLD or CROWN_DEFERRED_D_BUDGET keeps the king's crown; an unmeasured D is never
scored as 0. Nothing here prints, logs or returns a hidden value beyond what the caller passed in; the miner's view
(queue state and position) is built elsewhere and never carries a pick, a solve value or the zero.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, fields

from carbon.scoring import pool_model_search
from carbon.scoring.pool_grader import u_value
from carbon.scoring.pool_solver_reference import _check_problem, _margins, _unit

ZERO_SCHEMA = "carbon.crown-d.zero.v1"
ZERO_SOURCES = ("shortcut", "fit_pick", "train_best")

SOLVED = "SOLVED"
PENDING = "PENDING"
FAILED_INFRA = "FAILED_INFRA"
REFERENCE_FAILED = "REFERENCE_FAILED"
HOLD = "HOLD"
CROWN_DEFERRED_D_BUDGET = "CROWN_DEFERRED_D_BUDGET"
RESULT_STATES = (SOLVED, PENDING, FAILED_INFRA, REFERENCE_FAILED)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_CODE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,127}")


class CrownDRefused(ValueError):
    """A crown-time D rule, zero or result cannot give a sound decision: Carbon's material, never a candidate's."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _require(condition, code):
    if not condition:
        raise CrownDRefused(code)


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


# --- the registered rule ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CrownDRule:
    """The version's registered crown-time D block (owner / Validator values; no defaults)."""

    zero_sha256: str  # sha256 of the sealed zero record's canonical JSON
    weekly_solves: int | None  # reference solves per ISO week (the queue spends it)
    hold_seconds: (
        int | None
    )  # how long a challenger's crown decision may wait on a running or retrying solve
    coarse_rung: str | None  # registered rung names for the solver wrapper
    fine_rung: str | None
    dedupe_grid: (
        float | None
    )  # unit-box cell size for sharing one solve between near-identical picks
    min_targets: (
        int | None
    )  # fewest solved targets a D may rest on after reference failures


def check_rule(rule):
    """Refuse an incomplete or out-of-range rule. Returns the rule."""
    _require(isinstance(rule, CrownDRule), "crown_d_rule_required")
    for field in fields(CrownDRule):
        _require(
            getattr(rule, field.name) is not None,
            f"crown_d_{field.name}_is_human_input",
        )
    _require(
        type(rule.zero_sha256) is str
        and _SHA256.fullmatch(rule.zero_sha256) is not None,
        "crown_d_zero_sha256_invalid",
    )
    _require(
        type(rule.weekly_solves) is int and rule.weekly_solves >= 1,
        "crown_d_weekly_solves_invalid",
    )
    _require(
        type(rule.hold_seconds) is int and rule.hold_seconds >= 60,
        "crown_d_hold_seconds_invalid",
    )
    _require(
        type(rule.coarse_rung) is str
        and type(rule.fine_rung) is str
        and rule.coarse_rung
        and rule.fine_rung
        and rule.coarse_rung != rule.fine_rung,
        "crown_d_rungs_must_be_distinct_names",
    )
    _require(
        type(rule.dedupe_grid) is float and 0.0 < rule.dedupe_grid <= 0.1,
        "crown_d_dedupe_grid_invalid",
    )
    _require(
        type(rule.min_targets) is int and rule.min_targets >= 1,
        "crown_d_min_targets_invalid",
    )
    return rule


# --- the sealed zero -------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ZeroEntry:
    s_zero: float  # signed objective of the best cheap baseline
    s_ref: float  # signed objective of the reference optimum (D = 1)
    source: str  # which baseline set the zero (ZERO_SOURCES)


@dataclass(frozen=True)
class ZeroRecord:
    targets: tuple  # sorted ((target_id, ZeroEntry), ...)
    sha256: str  # of the document's canonical JSON

    def entry(self, target_id):
        for tid, entry in self.targets:
            if tid == target_id:
                return entry
        raise CrownDRefused("crown_d_zero_has_no_entry_for_target")


def zero_record(document):
    """Parse the sealed per-version zero (schema ZERO_SCHEMA). A target with s_ref <= s_zero has no room above its
    zero, so it could carry no information: refused, not silently dropped."""
    _require(
        type(document) is dict and set(document) == {"schema", "targets"},
        "crown_d_zero_malformed",
    )
    _require(document["schema"] == ZERO_SCHEMA, "crown_d_zero_schema_unknown")
    targets = document["targets"]
    _require(type(targets) is dict and targets, "crown_d_zero_has_no_targets")
    entries = []
    for target_id in sorted(targets):
        row = targets[target_id]
        _require(type(target_id) is str and target_id, "crown_d_zero_target_id_invalid")
        _require(
            type(row) is dict and set(row) == {"s_zero", "s_ref", "source"},
            "crown_d_zero_malformed",
        )
        _require(
            _finite(row["s_zero"]) and _finite(row["s_ref"]),
            "crown_d_zero_values_not_finite",
        )
        _require(row["s_ref"] > row["s_zero"], "crown_d_zero_s_ref_not_above_s_zero")
        _require(row["source"] in ZERO_SOURCES, "crown_d_zero_source_unknown")
        entries.append(
            (
                target_id,
                ZeroEntry(float(row["s_zero"]), float(row["s_ref"]), row["source"]),
            )
        )
    try:
        sha = hashlib.sha256(_canonical(document)).hexdigest()
    except (TypeError, ValueError):
        raise CrownDRefused("crown_d_zero_malformed") from None
    return ZeroRecord(targets=tuple(entries), sha256=sha)


def attach_zero(rule, document, problems):
    """The zero record, only if it is the registered one and covers every problem's target."""
    check_rule(rule)
    record = zero_record(document)
    _require(record.sha256 == rule.zero_sha256, "crown_d_zero_sha256_mismatch")
    known = {tid for tid, _ in record.targets}
    _require(
        all(p.target_id in known for p in problems), "crown_d_zero_missing_a_target"
    )
    return record


# --- the pick and its dedupe key -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Pick:
    target_id: str
    design: tuple  # raw design
    model_feasible: (
        bool  # the model's own predictions meet every limit (the solve decides truth)
    )


def pick(problem, evaluator, *, host_class):
    """The fixed optimizer's one design on the challenger's model (proof settings; custody host enforced there).

    The optimizer is FIXED: seed 0 and the box centre start (`pool_model_search.proof_problem`); any other setting
    refuses, so the only thing that differs between contenders is their model."""
    _require(
        problem.seed == pool_model_search.PROOF_SEED
        and tuple(problem.start) == (0.5,) * len(problem.box),
        "crown_d_pick_not_the_fixed_optimizer",
    )
    result = pool_model_search.model_search(problem, evaluator, host_class=host_class)
    return Pick(
        target_id=result.target_id,
        design=tuple(result.pick.design),
        model_feasible=bool(result.pick.model_feasible),
    )


def dedupe_key(challenge_id, version, target_id, rung, problem, design, grid):
    """One key per (Challenge, version, target, rung, grid cell): picks within half a cell share one solve."""
    _check_problem(problem)
    _require(type(grid) is float and 0.0 < grid <= 0.1, "crown_d_dedupe_grid_invalid")
    _require(
        all(type(v) is str and v for v in (challenge_id, target_id, rung))
        and (type(version) is str and version or type(version) is int),
        "crown_d_dedupe_ids_invalid",
    )
    _require(
        len(design) == len(problem.box) and all(_finite(x) for x in design),
        "crown_d_design_invalid",
    )
    unit = _unit(problem, design)
    _require(all(0.0 <= x <= 1.0 for x in unit), "crown_d_design_outside_the_box")
    cells = [round(x / grid) for x in unit]
    return hashlib.sha256(
        _canonical([challenge_id, version, target_id, rung, cells])
    ).hexdigest()


# --- scoring one target ----------------------------------------------------------------------------------------------


def _signed(problem, outputs):
    names = {problem.objective} | {limit.output for limit in problem.limits}
    _require(
        type(outputs) is dict
        and all(n in outputs and _finite(outputs[n]) for n in names),
        "crown_d_outputs_missing_or_not_finite",
    )
    value = float(outputs[problem.objective])
    return value if problem.sense == "max" else -value


def _within(distance, u):
    # U = 0 means the output is exact: only the sign matters, nothing is ever "within U".
    return u > 0.0 and abs(distance) <= u


def needs_fine(problem, zero_entry, outputs):
    """True when the coarse result is within U of any limit or of the zero: the coarse rung cannot settle it."""
    _check_problem(problem)
    s = _signed(problem, outputs)
    for index, margin in _margins(problem, outputs).items():
        name = problem.limits[index].output
        if _within(margin, u_value(problem.u[name], outputs[name])):
            return True
    u_obj = u_value(problem.u[problem.objective], outputs[problem.objective])
    return _within(s - zero_entry.s_zero, u_obj)


def target_d(problem, zero_entry, outputs):
    """0 if the solved design breaks a limit or is not above the zero; else its share of the zero-to-reference room."""
    _check_problem(problem)
    s = _signed(problem, outputs)
    if (
        any(m < 0.0 for m in _margins(problem, outputs).values())
        or s <= zero_entry.s_zero
    ):
        return 0.0
    share = (s - zero_entry.s_zero) / (zero_entry.s_ref - zero_entry.s_zero)
    return min(1.0, max(0.0, share))


# --- the challenger's decision ---------------------------------------------------------------------------------------


def _check_result(result):
    _require(
        type(result) is dict and result.get("state") in RESULT_STATES,
        "crown_d_result_state_unknown",
    )
    state = result["state"]
    if state == SOLVED:
        _require(
            set(result) == {"state", "outputs", "d"}
            and _finite(result["d"])
            and 0.0 <= result["d"] <= 1.0,
            "crown_d_solved_result_invalid",
        )
    elif state == REFERENCE_FAILED:
        _require(
            set(result) == {"state", "code"}
            and type(result["code"]) is str
            and _CODE.fullmatch(result["code"]),
            "crown_d_reference_failed_needs_a_code",
        )
    else:
        _require(set(result) == {"state"}, "crown_d_result_invalid")
    return state


def decide(rule, *, results, expected_targets, requested_at, now, budget_deferred):
    """The challenger's crown-time D, or a hold (scope: "Hold on a pending D").

    `results`: {target_id: {"state": SOLVED, "outputs", "d"} | {"state": PENDING} | {"state": FAILED_INFRA}
    | {"state": REFERENCE_FAILED, "code"}}; `expected_targets`: every target the version registers. A target with no
    result yet is PENDING (it can never silently leave the mean); a result for an unexpected target refuses. REFERENCE_FAILED targets are dropped and counted, never scored as 0.
    HOLD and CROWN_DEFERRED_D_BUDGET keep the king's crown (the status quo) and never score D as 0; only this
    challenger's crown decision waits. A hold is bounded by `rule.hold_seconds` from `requested_at`.
    """
    check_rule(rule)
    _require(type(results) is dict and results, "crown_d_results_required")
    _require(type(budget_deferred) is bool, "crown_d_budget_deferred_must_be_bool")
    _require(
        _finite(requested_at) and _finite(now) and now >= requested_at,
        "crown_d_clock_invalid",
    )
    _require(
        type(expected_targets) in (list, tuple, frozenset, set)
        and expected_targets
        and set(results) <= set(expected_targets),
        "crown_d_results_not_the_expected_targets",
    )
    results = {
        tid: results.get(tid, {"state": PENDING}) for tid in sorted(expected_targets)
    }
    states = {tid: _check_result(r) for tid, r in results.items()}
    solved = [results[tid]["d"] for tid, s in states.items() if s == SOLVED]
    dropped = sum(1 for s in states.values() if s == REFERENCE_FAILED)
    if all(s in (SOLVED, REFERENCE_FAILED) for s in states.values()):
        if len(solved) >= rule.min_targets:
            return {
                "state": SOLVED,
                "d": math.fsum(solved) / len(solved),
                "targets": len(solved),
                "dropped": dropped,
            }
        return {
            "state": FAILED_INFRA,
            "reason": "too_few_targets_after_reference_failures",
        }
    if budget_deferred and any(s == PENDING for s in states.values()):
        return {"state": CROWN_DEFERRED_D_BUDGET}
    elapsed = now - requested_at
    if elapsed < rule.hold_seconds:
        return {
            "state": HOLD,
            "seconds_left": math.ceil(rule.hold_seconds - elapsed),
        }
    return {"state": FAILED_INFRA, "reason": "hold_bound_reached"}
