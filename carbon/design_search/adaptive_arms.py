"""Prospective, development-only adaptive competitors for equal-budget replay.

The policy is sealed before held-out outcomes are read. ``replay`` is a
producer-side diagnostic: its trace contains reference observations and must
never be shown to a miner. No solver or model is invoked by this module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
from collections import defaultdict
from dataclasses import dataclass

from . import budget_registration as budgets
from . import equal_budget

SCHEMA = "carbon.design-search.adaptive-competitors.v1"
POLICY_SCHEMA = "carbon.design-search.adaptive-policy.v1"
ARMS = ("adaptive_solver", "industry_surrogate", "carbon_model")


class AdaptiveArmError(ValueError):
    """A policy, panel or replay violates the prospective contract."""


def _digest(body):
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                body, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
    )


def seal(body, field):
    if type(body) is not dict or field in body:
        raise AdaptiveArmError("unsealed object required")
    return {**body, field: _digest(body)}


def _closed(row, fields, label):
    if type(row) is not dict or set(row) != set(fields):
        raise AdaptiveArmError(f"closed {label} required")


def _number(value, label, *, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise AdaptiveArmError(f"finite {label} required")
    if value < 0 or (positive and value == 0):
        raise AdaptiveArmError(f"nonnegative {label} required")
    return float(value)


def _cost(row, label):
    _closed(row, ("wall_s", "core_s"), label)
    return {key: _number(row[key], f"{label}.{key}") for key in row}


def _sha(value, label):
    if not isinstance(value, str) or not budgets.SHA.fullmatch(value):
        raise AdaptiveArmError(f"{label} must be a sha256 digest")


def validate_policy(policy, challenge):
    _closed(
        policy,
        (
            "schema",
            "challenge",
            "calibration_digest",
            "pre_experiment_receipt",
            "direct",
            "surrogate",
            "model",
            "policy_digest",
        ),
        "policy",
    )
    if policy["schema"] != POLICY_SCHEMA or policy["challenge"] != challenge:
        raise AdaptiveArmError("policy version or Challenge mismatch")
    for key in ("calibration_digest", "pre_experiment_receipt"):
        _sha(policy[key], key)
    if policy["policy_digest"] != _digest(
        {k: v for k, v in policy.items() if k != "policy_digest"}
    ):
        raise AdaptiveArmError("policy digest mismatch")
    direct = policy["direct"]
    _closed(
        direct,
        (
            "method",
            "restarts",
            "stagnation",
            "startup_cost",
            "proposal_cost",
            "cache_lookup_cost",
        ),
        "direct arm",
    )
    if direct["method"] not in ("finite_enumeration", "pattern_multistart"):
        raise AdaptiveArmError("unsupported direct policy")
    if (challenge == "f02") != (direct["method"] == "finite_enumeration"):
        raise AdaptiveArmError(
            "f02 requires finite enumeration; other Challenges require adaptive search"
        )
    for key in ("restarts", "stagnation"):
        if type(direct[key]) is not int or direct[key] <= 0:
            raise AdaptiveArmError(f"positive {key} required")
    for key in ("startup_cost", "proposal_cost", "cache_lookup_cost"):
        _cost(direct[key], key)
    surrogate = policy["surrogate"]
    _closed(
        surrogate,
        (
            "method",
            "initial_designs",
            "length_scale",
            "objective_scale",
            "margin_scales",
            "exploration",
            "startup_cost",
            "proposal_cost",
            "fit_cost_per_observation",
            "cache_lookup_cost",
        ),
        "surrogate arm",
    )
    if surrogate["method"] != "branch_rbf_or_exact_lookup":
        raise AdaptiveArmError(
            "surrogate must use exact lookup or branch-wise response surface"
        )
    if (
        type(surrogate["initial_designs"]) is not int
        or surrogate["initial_designs"] <= 0
    ):
        raise AdaptiveArmError("positive initial design count required")
    for key in ("length_scale", "objective_scale"):
        _number(surrogate[key], key, positive=True)
    _number(surrogate["exploration"], "exploration")
    if type(surrogate["margin_scales"]) is not dict or not surrogate["margin_scales"]:
        raise AdaptiveArmError("per-quantity margin scales required")
    for name, scale in surrogate["margin_scales"].items():
        if not isinstance(name, str) or not name:
            raise AdaptiveArmError("named margin required")
        _number(scale, name, positive=True)
    for key in (
        "startup_cost",
        "proposal_cost",
        "fit_cost_per_observation",
        "cache_lookup_cost",
    ):
        _cost(surrogate[key], key)
    _closed(policy["model"], ("cache_lookup_cost",), "model prior cost")
    _cost(policy["model"]["cache_lookup_cost"], "model cache lookup")


def _margins(raw, names, challenge):
    if challenge == "battery-v3":
        _closed(raw, ("5", "15", "25", "35", "40"), "battery band margins")
        groups = raw.values()
    else:
        groups = (raw,)
    missing = False
    breach = False
    for group in groups:
        _closed(group, names, "mandatory margins")
        for value in group.values():
            if value is None:
                missing = True
            else:
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise AdaptiveArmError("finite or unresolved margin required")
                breach |= value < 0
    return "INFEASIBLE" if breach else "UNRESOLVED" if missing else "FEASIBLE"


def validate(panel, registration):
    _closed(
        panel,
        ("schema", "base_panel", "policy", "jobs", "adaptive_digest"),
        "adaptive panel",
    )
    if panel["schema"] != SCHEMA or panel["adaptive_digest"] != _digest(
        {k: v for k, v in panel.items() if k != "adaptive_digest"}
    ):
        raise AdaptiveArmError("adaptive panel version or digest mismatch")
    base = panel["base_panel"]
    equal_budget._validate(base)
    registered = budgets.validate(registration)
    challenge = base["challenge"]
    if base["budgets"] != [
        registered.cap(challenge, tier).time_compute for tier in budgets.TIERS
    ]:
        raise AdaptiveArmError("panel ladder differs from registered budgets")
    if base["registrations"]["cost_plan"] != registered.registration_id:
        raise AdaptiveArmError("panel cost plan differs from registration")
    validate_policy(panel["policy"], challenge)
    if type(panel["jobs"]) is not list or len(panel["jobs"]) != len(base["jobs"]):
        raise AdaptiveArmError("one action grammar per base job required")
    by_id = {job["job_id"]: job for job in base["jobs"]}
    seen = set()
    names = set(panel["policy"]["surrogate"]["margin_scales"])
    for job in panel["jobs"]:
        _closed(
            job,
            (
                "job_id",
                "axes",
                "actions",
                "starts",
                "common_cache",
                "cache_source",
                "condition_panel_digest",
                "cache_acquisition",
            ),
            "adaptive job",
        )
        job_id = job["job_id"]
        if job_id not in by_id or job_id in seen:
            raise AdaptiveArmError("unknown or duplicate job")
        seen.add(job_id)
        _sha(job["condition_panel_digest"], "complete condition panel")
        base_rows = {row["design_id"]: row for row in by_id[job_id]["candidates"]}
        axes = job["axes"]
        if type(axes) is not list or not axes:
            raise AdaptiveArmError("registered action axes required")
        axis_names = []
        for axis in axes:
            _closed(axis, ("name", "type", "values"), "action axis")
            if axis["type"] not in ("ordinal", "categorical") or not isinstance(
                axis["name"], str
            ):
                raise AdaptiveArmError("typed action axis required")
            if (
                type(axis["values"]) is not list
                or len(axis["values"]) < 2
                or len(set(map(str, axis["values"]))) != len(axis["values"])
            ):
                raise AdaptiveArmError("unique axis lattice required")
            if axis["type"] == "ordinal" and any(
                type(v) not in (int, float) or not math.isfinite(v)
                for v in axis["values"]
            ):
                raise AdaptiveArmError("finite ordinal values required")
            if axis["type"] == "categorical" and any(
                not isinstance(v, str) or not v for v in axis["values"]
            ):
                raise AdaptiveArmError("named categorical values required")
            axis_names.append(axis["name"])
        if len(set(axis_names)) != len(axis_names):
            raise AdaptiveArmError("duplicate action axis")
        actions = job["actions"]
        if type(actions) is not list or len(actions) != len(base_rows):
            raise AdaptiveArmError("every base design needs one action")
        if challenge == "f02" and len(actions) != 9:
            raise AdaptiveArmError("registered f02 contract has nine finite actions")
        action_ids = set()
        coordinates = set()
        for action in actions:
            _closed(
                action,
                (
                    "design_id",
                    "branch",
                    "coordinates",
                    "margins",
                    "unresolved_cause",
                    "warm_start_from",
                    "attempts",
                ),
                "action",
            )
            design_id = action["design_id"]
            if design_id not in base_rows or design_id in action_ids:
                raise AdaptiveArmError("unknown or duplicate action")
            action_ids.add(design_id)
            if not isinstance(action["branch"], str) or not action["branch"]:
                raise AdaptiveArmError("branch identity required")
            _closed(action["coordinates"], axis_names, "action coordinates")
            key = (
                action["branch"],
                tuple(str(action["coordinates"][name]) for name in axis_names),
            )
            if key in coordinates:
                raise AdaptiveArmError("duplicate canonical action")
            coordinates.add(key)
            for axis in axes:
                coordinate = action["coordinates"][axis["name"]]
                if axis["type"] == "ordinal" and (
                    type(coordinate) not in (int, float)
                    or not math.isfinite(coordinate)
                ):
                    raise AdaptiveArmError("typed ordinal coordinate required")
                if axis["type"] == "categorical" and type(coordinate) is not str:
                    raise AdaptiveArmError("typed categorical coordinate required")
                if coordinate not in axis["values"]:
                    raise AdaptiveArmError("off-lattice action")
            verdict = _margins(action["margins"], names, challenge)
            if verdict != base_rows[design_id]["reference"]["status"]:
                raise AdaptiveArmError("margins and settled reference disagree")
            cause = action["unresolved_cause"]
            if verdict == "UNRESOLVED":
                if cause not in ("FAILED_INFRA", "REFERENCE_UNRESOLVED"):
                    raise AdaptiveArmError("typed unresolved cause required")
            elif cause is not None:
                raise AdaptiveArmError("settled action cannot carry unresolved cause")
            attempts = action["attempts"]
            if type(attempts) is not list or not attempts:
                raise AdaptiveArmError("ordered complete-panel attempts required")
            for number, attempt in enumerate(attempts):
                _closed(attempt, ("kind", "cost", "planning_bound"), "solver attempt")
                if attempt["kind"] not in (
                    "failed_infra",
                    "failed_reference",
                    "invalid_geometry",
                    "refinement",
                    "final",
                ) or (attempt["kind"] == "final") != (number == len(attempts) - 1):
                    raise AdaptiveArmError(
                        "one final attempt must follow failures/refinements"
                    )
                actual = _cost(attempt["cost"], "attempt cost")
                bound = _cost(attempt["planning_bound"], "attempt planning bound")
                if any(
                    actual[unit] <= 0 or bound[unit] < actual[unit]
                    for unit in ("wall_s", "core_s")
                ):
                    raise AdaptiveArmError("each attempt needs a positive bounded cost")
            for unit in ("wall_s", "core_s"):
                if not math.isclose(
                    sum(attempt["cost"][unit] for attempt in attempts),
                    base_rows[design_id]["solve_cost"][unit],
                    rel_tol=0,
                    abs_tol=1e-9,
                ):
                    raise AdaptiveArmError(
                        "attempts must equal charged full-panel cost"
                    )
                if not math.isclose(
                    sum(attempt["planning_bound"][unit] for attempt in attempts),
                    base_rows[design_id]["planning_bound"][unit],
                    rel_tol=0,
                    abs_tol=1e-9,
                ):
                    raise AdaptiveArmError(
                        "attempt bounds must equal full-panel planning bound"
                    )
        if (
            type(job["starts"]) is not list
            or not job["starts"]
            or len(set(job["starts"])) != len(job["starts"])
        ):
            raise AdaptiveArmError("registered starts required")
        if any(item not in action_ids for item in job["starts"]):
            raise AdaptiveArmError("start outside bank")
        cache = job["common_cache"]
        if type(cache) is not list:
            raise AdaptiveArmError("common cache list required")
        cache_ids = set()
        by_action = {action["design_id"]: action for action in actions}
        for entry in cache:
            _closed(entry, ("design_id", "reference", "margins"), "exact cache entry")
            design_id = entry["design_id"]
            if design_id not in action_ids or design_id in cache_ids:
                raise AdaptiveArmError("cache outside bank or duplicate cache entry")
            cache_ids.add(design_id)
            if (
                entry["reference"] != base_rows[design_id]["reference"]
                or entry["margins"] != by_action[design_id]["margins"]
            ):
                raise AdaptiveArmError("exact cache and current reference disagree")
        source = job["cache_source"]
        if cache:
            _closed(
                source,
                (
                    "source_digest",
                    "rights",
                    "decision_rule_id",
                    "condition_panel_digest",
                ),
                "cache source",
            )
            _sha(source["source_digest"], "cache source")
            if (
                source["source_digest"] == base["source_digest"]
                or source["rights"] != "PUBLIC_DEVELOPMENT"
                or source["decision_rule_id"] != base["decision_rule_id"]
                or source["condition_panel_digest"] != job["condition_panel_digest"]
            ):
                raise AdaptiveArmError(
                    "cache must be a separate, rights-cleared exact-condition prior"
                )
        elif source is not None:
            raise AdaptiveArmError("cache source without cache contents")
        for action in actions:
            if (
                action["warm_start_from"] is not None
                and action["warm_start_from"] not in cache_ids
            ):
                raise AdaptiveArmError(
                    "warm-start provenance must be a common permitted prior"
                )
        _cost(job["cache_acquisition"], "shared cache acquisition")
    return registered


def _distance(a, b, axes):
    total = 0.0
    for axis in axes:
        x, y = (row["coordinates"][axis["name"]] for row in (a, b))
        if axis["type"] == "categorical":
            total += float(x != y)
        else:
            lo, hi = min(axis["values"]), max(axis["values"])
            total += ((x - y) / (hi - lo)) ** 2 if hi > lo else 0.0
    return math.sqrt(total)


def _better(a, b, direction):
    return (a < b) if direction == "min" else (a > b)


def _flatten(margins, challenge):
    if challenge == "battery-v3":
        return {
            name: min(
                (band[name] for band in margins.values() if band[name] is not None),
                default=None,
            )
            for name in next(iter(margins.values()))
        }
    return margins


def _next_direct(remaining, observed, actions, axes, config, direction, starts, state):
    if config["method"] == "finite_enumeration":
        return min(
            remaining,
            key=lambda item: tuple(
                axis["values"].index(actions[item]["coordinates"][axis["name"]])
                for axis in axes
            ),
        )
    for item in starts:
        if item in remaining:
            return item
    feasible = [
        (key, row["reference"]["value"])
        for key, row in observed.items()
        if row["reference"]["status"] == "FEASIBLE"
    ]
    if feasible:
        incumbent = min(
            feasible, key=lambda pair: pair[1] if direction == "min" else -pair[1]
        )[0]
        branch = actions[incumbent]["branch"]
        local = [item for item in remaining if actions[item]["branch"] == branch]
        if local and not state["global_only"] and not state["force_global_next"]:
            return min(
                local,
                key=lambda item: (
                    _distance(actions[item], actions[incumbent], axes),
                    item,
                ),
            )
    # Deterministic maximin challenger across branches after stagnation.
    return min(
        remaining,
        key=lambda item: (
            -min(
                (
                    _distance(actions[item], actions[prior], axes)
                    + (actions[item]["branch"] != actions[prior]["branch"])
                    for prior in observed
                ),
                default=0,
            ),
            item,
        ),
    )


def _next_surrogate(
    remaining, observed, actions, axes, config, direction, starts, challenge
):
    for item in starts[: config["initial_designs"]]:
        if item in remaining:
            return item
    if len(observed) < config["initial_designs"]:
        return min(
            remaining,
            key=lambda item: (
                -min(
                    (
                        _distance(actions[item], actions[prior], axes)
                        for prior in observed
                    ),
                    default=0,
                ),
                item,
            ),
        )
    feasible = [
        row["reference"]["value"]
        for row in observed.values()
        if row["reference"]["status"] == "FEASIBLE"
    ]
    incumbent = (
        (min(feasible) if direction == "min" else max(feasible)) if feasible else None
    )

    def acquisition(item):
        branch = actions[item]["branch"]
        neighbours = [
            (prior, row)
            for prior, row in observed.items()
            if actions[prior]["branch"] == branch
            and row["reference"]["status"] != "UNRESOLVED"
            and all(
                value is not None
                for value in _flatten(row["margins"], challenge).values()
            )
        ]
        if not neighbours:
            return (float("inf"), item)
        weighted = []
        for prior, row in neighbours:
            dist = _distance(actions[item], actions[prior], axes)
            weight = math.exp(-0.5 * (dist / config["length_scale"]) ** 2)
            weighted.append((weight, dist, prior, row))
        total = sum(x[0] for x in weighted)
        if total == 0:
            nearest = min(weighted, key=lambda row: (row[1], row[2]))
            weighted = [(1.0, nearest[1], nearest[2], nearest[3])]
            total = 1.0
        feasible_neighbours = [
            (w, row["reference"]["value"])
            for w, _, _, row in weighted
            if row["reference"]["status"] == "FEASIBLE"
        ]
        predicted = (
            sum(w * value for w, value in feasible_neighbours)
            / sum(w for w, _ in feasible_neighbours)
            if feasible_neighbours
            else None
        )
        margins = {
            name: sum(
                w * _flatten(row["margins"], challenge)[name]
                for w, _, _, row in weighted
            )
            / total
            for name in config["margin_scales"]
        }
        # Each hard observable is modelled separately in its registered unit.
        safety = min(
            margins[name] / scale for name, scale in config["margin_scales"].items()
        )
        uncertainty = min(dist for _, dist, _, _ in weighted)
        improvement = (
            0.0
            if incumbent is None or predicted is None
            else (
                (incumbent - predicted)
                if direction == "min"
                else (predicted - incumbent)
            )
            / config["objective_scale"]
        )
        return (
            min(0.0, safety) + improvement + config["exploration"] * uncertainty,
            item,
        )

    return max(sorted(remaining, reverse=True), key=acquisition)


@dataclass(frozen=True)
class Replay:
    result: dict
    trace: tuple[dict, ...]


def _run(base_job, action_job, policy, cap, arm, direction, challenge):
    config = (
        policy["direct"]
        if arm == "adaptive_solver"
        else policy["surrogate"] if arm == "industry_surrogate" else policy["model"]
    )
    ledger = budgets.BudgetLedger(cap)
    rows = {row["design_id"]: row for row in base_job["candidates"]}
    actions = {row["design_id"]: row for row in action_job["actions"]}
    # This is the complete policy-visible action surface. Cost and unqueried
    # reference observables remain exclusively in the producer-side referee.
    search_actions = {
        design_id: {
            "design_id": design_id,
            "branch": action["branch"],
            "coordinates": action["coordinates"],
        }
        for design_id, action in actions.items()
    }
    observed = {}
    trace = []
    remaining = set(rows)
    state = {
        "stagnation": 0,
        "restarts": 0,
        "best": None,
        "global_only": False,
        "force_global_next": False,
    }

    def record(kind, design_id=None, provenance=None):
        entry = {
            "sequence": len(trace),
            "event": kind,
            "policy_digest": policy["policy_digest"],
            "observed_prefix_digest": _digest(observed),
            "candidate_digest": (
                None if design_id is None else _digest(search_actions[design_id])
            ),
            "panel_digest": action_job["condition_panel_digest"],
            "provenance": provenance,
            "cumulative": {
                "wall_s": ledger.wall_s,
                "core_s": ledger.core_s,
                "solver_evaluations": ledger.solver_evaluations,
            },
        }
        trace.append(entry)
        return entry

    if not ledger.charge_overhead(action_job["cache_acquisition"]):
        record("STOP_CACHE_ACQUISITION_OVER_BUDGET")
        return Replay(
            _result(observed, ledger, direction, "OVER_BUDGET_BEFORE_SEARCH"),
            tuple(trace),
        )
    record("CACHE_ACQUISITION", provenance="common_public_development")
    startup = (
        base_job["screen_cost"]["model"]
        if arm == "carbon_model"
        else config["startup_cost"]
    )
    if not ledger.charge_overhead(startup):
        record("STOP_STARTUP_OVER_BUDGET")
        return Replay(
            _result(observed, ledger, direction, "OVER_BUDGET_BEFORE_SEARCH"),
            tuple(trace),
        )
    record("ARM_STARTUP", provenance="registered_cold_start")
    for cached in action_job["common_cache"]:
        design_id = cached["design_id"]
        if design_id not in remaining:
            continue
        if not ledger.charge_overhead(config["cache_lookup_cost"]):
            record("STOP_CACHE_LOOKUP_OVER_BUDGET")
            return Replay(
                _result(observed, ledger, direction, "BUDGET_STOP"), tuple(trace)
            )
        record("CACHE_LOOKUP", design_id, "common_exact_cache")
        observed[design_id] = {
            "reference": cached["reference"],
            "margins": cached["margins"],
        }
        remaining.remove(design_id)
        record("SETTLED_CACHE_HIT", design_id, "common_exact_cache")["observation"] = (
            rows[design_id]["reference"]
        )
    starts = action_job["starts"]
    stop_status = None
    while remaining:
        # Charge all optimiser/fitting work before inspecting another reference.
        if arm == "industry_surrogate":
            fit = {
                unit: config["fit_cost_per_observation"][unit] * len(observed)
                for unit in ("wall_s", "core_s")
            }
            if not ledger.charge_overhead(fit):
                record("STOP_FIT_OVER_BUDGET")
                stop_status = "BUDGET_STOP"
                break
            record("SURROGATE_FIT", provenance="branch_objective_and_all_hard_margins")
        proposal = (
            {"wall_s": 0.0, "core_s": 0.0}
            if arm == "carbon_model"
            else {
                unit: config["proposal_cost"][unit] * len(remaining)
                for unit in ("wall_s", "core_s")
            }
        )
        if not ledger.charge_overhead(proposal):
            record("STOP_PROPOSAL_OVER_BUDGET")
            stop_status = "BUDGET_STOP"
            break
        if arm == "adaptive_solver":
            design_id = _next_direct(
                remaining,
                observed,
                search_actions,
                action_job["axes"],
                config,
                direction,
                starts,
                state,
            )
            state["force_global_next"] = False
        elif arm == "industry_surrogate":
            design_id = _next_surrogate(
                remaining,
                observed,
                search_actions,
                action_job["axes"],
                config,
                direction,
                starts,
                challenge,
            )
        else:
            design_id = min(
                remaining, key=lambda item: (rows[item]["screen_rank"]["model"], item)
            )
        record(
            "PROPOSAL",
            design_id,
            "registered_start" if design_id in starts else "observed_prefix_policy",
        )
        row = rows[design_id]
        attempts = actions[design_id]["attempts"]
        if (
            ledger.solver_evaluations + len(attempts) > cap.solver_evaluations
            or ledger.wall_s + row["planning_bound"]["wall_s"] > cap.wall_s + 1e-12
            or ledger.core_s + row["planning_bound"]["core_s"] > cap.core_s + 1e-12
        ):
            record("STOP_SOLVE_OVER_BUDGET", design_id)
            stop_status = "BUDGET_STOP"
            break
        for attempt in attempts:
            if not ledger.charge_solver_attempt(
                attempt["planning_bound"], attempt["cost"]
            ):
                raise AdaptiveArmError("validated complete-panel preflight failed")
            part = record("SOLVER_ATTEMPT", design_id, attempt["kind"])
            part["cost"] = attempt["cost"]
            part["planning_bound"] = attempt["planning_bound"]
        observed[design_id] = {
            "reference": row["reference"],
            "margins": actions[design_id]["margins"],
        }
        remaining.remove(design_id)
        entry = record("SETTLED_SOLVER_ATTEMPT", design_id, "full_condition_panel")
        entry["observation"] = row["reference"]
        entry["unresolved_cause"] = actions[design_id]["unresolved_cause"]
        entry["attempts"] = len(attempts)
        source = actions[design_id]["warm_start_from"]
        entry["warm_start_from_digest"] = (
            None if source is None else _digest(search_actions[source])
        )
        if arm == "adaptive_solver":
            value = (
                row["reference"]["value"]
                if row["reference"]["status"] == "FEASIBLE"
                else None
            )
            if value is not None and (
                state["best"] is None or _better(value, state["best"], direction)
            ):
                state["best"] = value
                state["stagnation"] = 0
            else:
                state["stagnation"] += 1
            if state["stagnation"] >= config["stagnation"]:
                state["restarts"] += 1
                state["stagnation"] = 0
                state["force_global_next"] = True
                if state["restarts"] >= config["restarts"]:
                    state["global_only"] = True
                    record("GLOBAL_EXPLORATION_AFTER_RESTART_LIMIT")
    status = stop_status or (
        "EXHAUSTIVE"
        if arm == "adaptive_solver" and config["method"] == "finite_enumeration"
        else "BANK_EXHAUSTED"
    )
    return Replay(_result(observed, ledger, direction, status), tuple(trace))


def _result(observed, ledger, direction, status):
    feasible = [
        row["reference"]["value"]
        for row in observed.values()
        if row["reference"]["status"] == "FEASIBLE"
    ]
    value = (
        (min(feasible) if direction == "min" else max(feasible)) if feasible else None
    )
    return {
        "best_verified_value": value,
        "status": status,
        "verified_count": len(observed),
        "solver_attempts": ledger.solver_evaluations,
        "spent_wall_s": ledger.wall_s,
        "spent_core_s": ledger.core_s,
    }


def replay(panel, registration, tier):
    """Return aggregate arm outcomes and producer-only ordered proposal traces."""
    registered = validate(panel, registration)
    if tier not in budgets.TIERS:
        raise AdaptiveArmError("registered budget tier required")
    base = panel["base_panel"]
    cap = registered.cap(base["challenge"], tier)
    jobs = {job["job_id"]: job for job in panel["jobs"]}
    result = []
    traces = []
    for base_job in base["jobs"]:
        arm_results = {}
        for arm in ARMS:
            output = _run(
                base_job,
                jobs[base_job["job_id"]],
                panel["policy"],
                cap,
                arm,
                base["objective"]["direction"],
                base["challenge"],
            )
            arm_results[arm] = output.result
            traces.append(
                {"job_id": base_job["job_id"], "arm": arm, "events": list(output.trace)}
            )
        result.append({"cluster_id": base_job["cluster_id"], "arms": arm_results})
    return {
        "schema": "carbon.design-search.adaptive-replay.v1",
        "adaptive_digest": panel["adaptive_digest"],
        "budget_registration_digest": registered.registration_digest,
        "tier": tier,
        "results": result,
        "producer_only_traces": traces,
    }


def _mean(values):
    return sum(values) / len(values) if values else None


def _quantile(values, probability):
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    low, high = math.floor(index), math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def _aggregate(rows, direction):
    summary = {}
    for arm in ARMS:
        results = [row["arms"][arm] for row in rows]
        values = [
            item["best_verified_value"]
            for item in results
            if item["best_verified_value"] is not None
        ]
        summary[arm] = {
            "feasible_fraction": len(values) / len(results),
            "best_verified_value_conditional": _mean(values),
            "solver_attempts_mean": _mean(
                [item["solver_attempts"] for item in results]
            ),
            "wall_s_mean": _mean([item["spent_wall_s"] for item in results]),
            "core_s_mean": _mean([item["spent_core_s"] for item in results]),
            "budget_stop_fraction": _mean(
                [
                    item["status"] in ("BUDGET_STOP", "OVER_BUDGET_BEFORE_SEARCH")
                    for item in results
                ]
            ),
        }
    comparisons = {}
    for opponent in ("adaptive_solver", "industry_surrogate"):
        pairs = [
            (
                row["arms"]["carbon_model"]["best_verified_value"],
                row["arms"][opponent]["best_verified_value"],
            )
            for row in rows
        ]
        pairs = [
            (model, other)
            for model, other in pairs
            if model is not None and other is not None
        ]
        sign = 1 if direction == "max" else -1
        differences = [sign * (model - other) for model, other in pairs]
        comparisons[opponent] = {
            "paired_count": len(pairs),
            "model_advantage_buyer_units_conditional": _mean(differences),
            "p_model_strictly_better_conditional": _mean(
                [delta > 0 for delta in differences]
            ),
        }
    summary["model_comparisons"] = comparisons
    return summary


def compare(panel, registration, *, confidence, bootstrap_replicates, seed):
    """Allow-listed aggregate curves; no job IDs, proposals or references."""
    registered = validate(panel, registration)
    if type(confidence) not in (int, float) or not 0 < confidence < 1:
        raise AdaptiveArmError("confidence must be between zero and one")
    if type(bootstrap_replicates) is not int or bootstrap_replicates < 100:
        raise AdaptiveArmError("at least 100 bootstrap replicates required")
    if type(seed) is not int:
        raise AdaptiveArmError("integer bootstrap seed required")
    base = panel["base_panel"]
    header = {
        "schema": "carbon.design-search.adaptive-aggregate.v1",
        "challenge": base["challenge"],
        "adaptive_digest": panel["adaptive_digest"],
        "policy_digest": panel["policy"]["policy_digest"],
        "budget_registration_digest": registered.registration_digest,
        "evidence_class": "DEVELOPMENT",
    }
    if any(
        row["reference"]["status"] == "UNRESOLVED"
        for job in base["jobs"]
        for row in job["candidates"]
    ):
        return {**header, "status": "UNRESOLVED_PANEL", "curves": []}
    clusters = defaultdict(list)
    for job in base["jobs"]:
        clusters[job["cluster_id"]].append(job["job_id"])
    curves = []
    for tier in budgets.TIERS:
        raw = replay(panel, registration, tier)
        rows = raw["results"]
        estimate = _aggregate(rows, base["objective"]["direction"])
        interval = None
        if len(clusters) >= 2:
            rng = random.Random(seed)
            by_cluster = defaultdict(list)
            for row in rows:
                by_cluster[row["cluster_id"]].append(row)
            cluster_ids = sorted(clusters)
            draws = []
            for _ in range(bootstrap_replicates):
                sample = [rng.choice(cluster_ids) for _ in cluster_ids]
                draws.append(
                    _aggregate(
                        [row for cluster in sample for row in by_cluster[cluster]],
                        base["objective"]["direction"],
                    )
                )
            tail = (1 - confidence) / 2
            interval = {}
            for arm in ARMS:
                interval[arm] = {}
                for metric in estimate[arm]:
                    values = [
                        draw[arm][metric]
                        for draw in draws
                        if draw[arm][metric] is not None
                    ]
                    interval[arm][metric] = (
                        None
                        if not values
                        else [_quantile(values, tail), _quantile(values, 1 - tail)]
                    )
            interval["model_comparisons"] = {}
            for opponent in ("adaptive_solver", "industry_surrogate"):
                interval["model_comparisons"][opponent] = {}
                for metric in estimate["model_comparisons"][opponent]:
                    values = [
                        draw["model_comparisons"][opponent][metric]
                        for draw in draws
                        if draw["model_comparisons"][opponent][metric] is not None
                    ]
                    interval["model_comparisons"][opponent][metric] = (
                        None
                        if not values
                        else [_quantile(values, tail), _quantile(values, 1 - tail)]
                    )
        cap = registered.cap(base["challenge"], tier)
        curves.append(
            {
                "tier": tier,
                "budget": {
                    "solver_evaluations": cap.solver_evaluations,
                    "wall_s": cap.wall_s,
                    "core_s": cap.core_s,
                },
                "estimates": estimate,
                "cluster_bootstrap_ci": interval,
            }
        )
    return {
        **header,
        "status": "OK",
        "job_count": len(base["jobs"]),
        "independent_clusters": len(clusters),
        "confidence": confidence,
        "bootstrap_replicates": bootstrap_replicates,
        "bootstrap_seed": seed,
        "curves": curves,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("panel", help="sealed development adaptive panel")
    parser.add_argument("--budget-registration", required=True)
    parser.add_argument("--confidence", required=True, type=float)
    parser.add_argument("--bootstrap-replicates", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument(
        "--producer-trace", help="optional restricted local JSON trace path"
    )
    args = parser.parse_args(argv)
    with open(args.panel, encoding="utf-8") as stream:
        panel = json.load(stream)
    with open(args.budget_registration, encoding="utf-8") as stream:
        registration = json.load(stream)
    report = compare(
        panel,
        registration,
        confidence=args.confidence,
        bootstrap_replicates=args.bootstrap_replicates,
        seed=args.seed,
    )
    if args.producer_trace is not None:
        descriptor = os.open(
            args.producer_trace, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(
                {tier: replay(panel, registration, tier) for tier in budgets.TIERS},
                stream,
                indent=2,
                sort_keys=True,
            )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
