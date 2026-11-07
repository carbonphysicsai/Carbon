"""Crown-time D: the design value of a challenger that could take the crown (pure logic, custody only).

When a challenger could change the crown, OUR fixed optimizer (the one the version registers: `cmaes_proof_v1` =
`pool_model_search.model_search` at the proof settings, or `de_polish_v1` = `pool_model_search.model_search_de` at the
registered model-call budget) runs on the challenger's model and picks one design per target. That pick gets one reference solve (an injected
solver wrapper; nothing here solves). The solved result is scored against the version's sealed "zero": per target, the
best of three cheap baselines (the registered shortcut's solved pick, a TRAIN-only fit's solved pick, the best TRAIN
design), computed once per exam version and registered by sha256.

- `CrownDRule`: the version's registered block. Every field is an owner / Validator value with no default; a None
  (HUMAN_INPUT) refuses, so a version without a complete block never runs crown-time D.
- `zero_record` / `attach_zero`: the sealed zero, checked against the registered sha, the targets and the optimizer
  it was built with (the zero's picks must come from the same search the miner faces).
- `pick`: the fixed optimizer's one design per target, on the contender's model rebuilt with the registered seed
  (`pick_rebuild_seed`, option C of D_CROWN_COST_OPTIONS_20261107: one rebuild, not ten); `pick_key` names a pick so
  an identical model + seed + target is never searched twice (the king's picks are reused).
- `draw_targets`: the epoch's k of the version's N pool tasks (option D), drawn with a custody key; the king and every
  contender in one epoch face the same k.
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
import hmac
import json
import math
import re
from dataclasses import dataclass, fields

from carbon.scoring import pool_model_search
from carbon.scoring.pool_grader import u_value
from carbon.scoring.pool_solver_reference import _check_problem, _margins, _unit

ZERO_SCHEMA_V1 = (
    "carbon.crown-d.zero.v1"  # no optimizer field: built with cmaes_proof_v1
)
ZERO_SCHEMA = "carbon.crown-d.zero.v2"  # names the optimizer its picks were made with
CMAES_PROOF = "cmaes_proof_v1"
DE_POLISH = pool_model_search.DE_NAME  # "de_polish_v1"
OPTIMIZERS = (CMAES_PROOF, DE_POLISH)
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
    optimizer: str | None = None  # OPTIMIZERS; None (HUMAN_INPUT) refuses
    pick_rebuild_seed: int | None = (
        None  # the rebuild whose model the picks come from (Validator; option C)
    )
    tasks_per_epoch: int | None = (
        None  # k of the version's N pool tasks drawn per epoch (owner; option D)
    )
    model_call_budget: int | None = (
        None  # de_polish_v1 only: model calls per target (owner value); unused (None) for cmaes_proof_v1
    )


def check_rule(rule):
    """Refuse an incomplete or out-of-range rule. Returns the rule."""
    _require(isinstance(rule, CrownDRule), "crown_d_rule_required")
    for field in fields(CrownDRule):
        if field.name == "model_call_budget":
            continue  # checked per optimizer below
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
    _require(
        type(rule.pick_rebuild_seed) is int and rule.pick_rebuild_seed >= 0,
        "crown_d_pick_rebuild_seed_invalid",
    )
    _require(
        type(rule.tasks_per_epoch) is int and rule.tasks_per_epoch >= 1,
        "crown_d_tasks_per_epoch_invalid",
    )
    _require(rule.optimizer in OPTIMIZERS, "crown_d_optimizer_unknown")
    if rule.optimizer == DE_POLISH:
        _require(
            rule.model_call_budget is not None,
            "crown_d_model_call_budget_is_human_input",
        )
        _require(
            type(rule.model_call_budget) is int and rule.model_call_budget >= 1,
            "crown_d_model_call_budget_invalid",
        )
    else:
        _require(
            rule.model_call_budget is None,
            "crown_d_model_call_budget_not_used_by_cmaes_proof_v1",
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
    optimizer: str = CMAES_PROOF  # the optimizer the zero's picks were made with

    def entry(self, target_id):
        for tid, entry in self.targets:
            if tid == target_id:
                return entry
        raise CrownDRefused("crown_d_zero_has_no_entry_for_target")


def zero_record(document):
    """Parse the sealed per-version zero: schema ZERO_SCHEMA (v2, names its `optimizer`) or ZERO_SCHEMA_V1 (no
    optimizer field; built with cmaes_proof_v1). A target with s_ref <= s_zero has no room above its zero, so it could
    carry no information: refused, not silently dropped."""
    _require(
        type(document) is dict and {"schema", "targets"} <= set(document),
        "crown_d_zero_malformed",
    )
    _require(
        document["schema"] in (ZERO_SCHEMA, ZERO_SCHEMA_V1),
        "crown_d_zero_schema_unknown",
    )
    if document["schema"] == ZERO_SCHEMA_V1:
        _require(set(document) == {"schema", "targets"}, "crown_d_zero_malformed")
        optimizer = CMAES_PROOF
    else:
        _require(
            set(document) == {"schema", "optimizer", "targets"},
            "crown_d_zero_malformed",
        )
        optimizer = document["optimizer"]
        _require(optimizer in OPTIMIZERS, "crown_d_zero_optimizer_unknown")
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
    return ZeroRecord(targets=tuple(entries), sha256=sha, optimizer=optimizer)


def attach_zero(rule, document, problems):
    """The zero record, only if it is the registered one and covers every problem's target."""
    check_rule(rule)
    record = zero_record(document)
    _require(record.sha256 == rule.zero_sha256, "crown_d_zero_sha256_mismatch")
    _require(
        record.optimizer == rule.optimizer, "crown_d_zero_built_with_another_optimizer"
    )
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


def pick(problem, evaluator, *, host_class, rule):
    """The registered optimizer's one design on the challenger's model (custody host enforced there).

    The optimizer is FIXED per version (`rule.optimizer`), so the only thing that differs between contenders is their
    model. `cmaes_proof_v1`: seed 0 and the box centre start (`pool_model_search.proof_problem`), the proof settings,
    unchanged. `de_polish_v1`: seed 0 (public, fixed) and `rule.model_call_budget` model calls (at least one DE
    generation, 16 per design input). Any other setting refuses."""
    check_rule(rule)
    if rule.optimizer == DE_POLISH:
        _require(
            problem.seed == pool_model_search.PROOF_SEED,
            "crown_d_pick_not_the_fixed_optimizer",
        )
        _require(
            rule.model_call_budget >= 16 * len(problem.box),
            "crown_d_model_call_budget_below_one_de_generation",
        )
        result = pool_model_search.model_search_de(
            problem, evaluator, host_class=host_class, budget=rule.model_call_budget
        )
    else:
        _require(
            problem.seed == pool_model_search.PROOF_SEED
            and tuple(problem.start) == (0.5,) * len(problem.box),
            "crown_d_pick_not_the_fixed_optimizer",
        )
        result = pool_model_search.model_search(
            problem, evaluator, host_class=host_class
        )
    return Pick(
        target_id=result.target_id,
        design=tuple(result.pick.design),
        model_feasible=bool(result.pick.model_feasible),
    )


def pick_key(challenge_id, version, target_id, problem, rule, *, model_sha256):
    """One key per (Challenge, version, target, problem, optimizer settings, rebuilt model): the same model rebuilt
    with the same seed searched by the same fixed optimizer gives the same pick, so a cached pick is exact (the king's
    picks are searched once per version, not once per contender)."""
    check_rule(rule)
    _check_problem(problem)
    _require(
        type(model_sha256) is str and _SHA256.fullmatch(model_sha256) is not None,
        "crown_d_model_sha256_invalid",
    )
    _require(
        all(type(v) is str and v for v in (challenge_id, target_id))
        and (type(version) is str and version or type(version) is int),
        "crown_d_pick_ids_invalid",
    )
    settings = [
        rule.optimizer,
        rule.model_call_budget,
        rule.pick_rebuild_seed,
        repr(problem),  # frozen dataclass: fixed, box, limits, U, seed, start
    ]
    return hashlib.sha256(
        _canonical([challenge_id, version, target_id, model_sha256, settings])
    ).hexdigest()


def draw_targets(rule, key, *, challenge_id, version, epoch, targets):
    """The epoch's k = `rule.tasks_per_epoch` of the version's pool `targets` (option D): each target ranked by
    HMAC-SHA256(key, [Challenge, version, epoch, target]), the k lowest kept, returned sorted. `key` is a custody
    secret (>= 32 bytes; the Validator's), so no miner can tell the epoch's k in advance; the same key and epoch give
    the same k for the king and every contender. Refuses k > N: a version must register at least k tasks.
    """
    check_rule(rule)
    _require(type(key) is bytes and len(key) >= 32, "crown_d_draw_key_invalid")
    _require(
        type(epoch) is str and epoch and type(challenge_id) is str and challenge_id,
        "crown_d_draw_ids_invalid",
    )
    pool = sorted(set(targets))
    _require(
        pool and len(pool) == len(targets) and all(type(t) is str and t for t in pool),
        "crown_d_draw_targets_invalid",
    )
    _require(rule.tasks_per_epoch <= len(pool), "crown_d_tasks_per_epoch_above_pool")
    rank = {
        t: hmac.new(
            key, _canonical([challenge_id, version, epoch, t]), "sha256"
        ).digest()
        for t in pool
    }
    return tuple(
        sorted(sorted(pool, key=lambda t: (rank[t], t))[: rule.tasks_per_epoch])
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
