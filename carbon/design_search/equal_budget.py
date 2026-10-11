"""Development-only equal-time-and-compute design-search replay.

The solver is the sole referee. Screening ranks are committed inputs, not
reference values. This extends Track B's cost and reference separation to a
three-arm, paired budget comparison; it performs no solve or model inference.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
from collections import defaultdict

from . import budget_registration, track_b

SCHEMA = "carbon.design-search.equal-budget-panel.v1"
REPORT_SCHEMA = "carbon.design-search.equal-budget-report.v1"
CHALLENGES = {"battery-v3", "motor", "f02", "f13", "metagrating-3d"}
ARMS = ("solver_alone", "model_then_solver", "baseline_then_solver")


class EqualBudgetError(ValueError):
    pass


def _finite_nonnegative(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise EqualBudgetError(f"{name} must be finite and nonnegative")
    return float(value)


def _cost(value, name):
    if type(value) is not dict or set(value) != {"wall_s", "core_s"}:
        raise EqualBudgetError(f"{name} requires wall_s and core_s")
    return (
        _finite_nonnegative(value["wall_s"], f"{name}.wall_s"),
        _finite_nonnegative(value["core_s"], f"{name}.core_s"),
    )


def _digest(body):
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(encoded.encode()).hexdigest()


def seal(body):
    """Bind a development replay input to its registered source and contents."""
    if type(body) is not dict or "panel_digest" in body:
        raise EqualBudgetError("unsealed panel body required")
    return {**body, "panel_digest": _digest(body)}


def _validate(panel):
    if type(panel) is not dict or set(panel) != {
        "schema",
        "evidence_class",
        "challenge",
        "source_digest",
        "decision_rule_id",
        "objective",
        "cost_basis",
        "execution_plan",
        "budgets",
        "jobs",
        "registrations",
        "panel_digest",
    }:
        raise EqualBudgetError("closed equal-budget panel schema required")
    if panel["schema"] != SCHEMA or panel["evidence_class"] != "DEVELOPMENT":
        raise EqualBudgetError("development panel required")
    if panel["challenge"] not in CHALLENGES:
        raise EqualBudgetError("unsupported Challenge")
    if panel["panel_digest"] != _digest(
        {k: v for k, v in panel.items() if k != "panel_digest"}
    ):
        raise EqualBudgetError("panel digest mismatch")
    if not isinstance(panel["source_digest"], str) or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", panel["source_digest"]
    ):
        raise EqualBudgetError("registered source digest required")
    if not isinstance(panel["decision_rule_id"], str) or not panel["decision_rule_id"]:
        raise EqualBudgetError("decision rule required")
    objective = panel["objective"]
    expected_objective = (
        {"direction", "unit", "index_weights"}
        if panel["challenge"] == "battery-v3"
        else {"direction", "unit"}
    )
    if type(objective) is not dict or set(objective) != expected_objective:
        raise EqualBudgetError("objective direction and unit required")
    if objective["direction"] not in ("min", "max") or not objective["unit"]:
        raise EqualBudgetError("objective direction or unit invalid")
    if panel["challenge"] == "battery-v3":
        weights = objective["index_weights"]
        if type(weights) is not dict or set(weights) != {"5", "15", "25", "35", "40"}:
            raise EqualBudgetError("battery v3 five-band weights required")
        if any(
            _finite_nonnegative(value, "index weight") <= 0
            for value in weights.values()
        ) or not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-12):
            raise EqualBudgetError("positive normalized index weights required")
    if panel["cost_basis"] not in ("MEASURED", "ASSUMPTION"):
        raise EqualBudgetError("cost basis must be explicit")
    if panel["execution_plan"] != "SERIAL_COMPLETE_PANELS":
        raise EqualBudgetError("serial complete-panel execution plan required")
    registrations = panel["registrations"]
    if (
        type(registrations) is not dict
        or set(registrations)
        != {"solver_search", "model_screen", "baseline_screen", "cost_plan"}
        or any(
            not isinstance(value, str) or not value for value in registrations.values()
        )
    ):
        raise EqualBudgetError(
            "four registered search and cost-plan identities required"
        )
    budgets = panel["budgets"]
    if type(budgets) is not list or not budgets:
        raise EqualBudgetError("budget ladder required")
    for budget in budgets:
        wall, core = _cost(budget, "budget")
        if wall == 0 or core == 0:
            raise EqualBudgetError("positive time and compute budgets required")
    jobs = panel["jobs"]
    if type(jobs) is not list or not jobs:
        raise EqualBudgetError("jobs required")
    seen_jobs = set()
    for job in jobs:
        if type(job) is not dict or set(job) != {
            "job_id",
            "cluster_id",
            "candidates",
            "solver_order",
            "screen_cost",
        }:
            raise EqualBudgetError("closed job schema required")
        if not job["job_id"] or job["job_id"] in seen_jobs or not job["cluster_id"]:
            raise EqualBudgetError("duplicate job or missing cluster")
        seen_jobs.add(job["job_id"])
        candidates = job["candidates"]
        if type(candidates) is not list or not candidates:
            raise EqualBudgetError("candidate bank required")
        ids = [row.get("design_id") for row in candidates]
        if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(
            set(ids)
        ):
            raise EqualBudgetError("candidate IDs must be unique")
        if (
            type(job["solver_order"]) is not list
            or set(job["solver_order"]) != set(ids)
            or len(job["solver_order"]) != len(ids)
        ):
            raise EqualBudgetError(
                "registered solver order must cover the bank exactly"
            )
        screens = job["screen_cost"]
        if type(screens) is not dict or set(screens) != {"model", "baseline"}:
            raise EqualBudgetError("both screening costs required")
        for name in screens:
            _cost(screens[name], f"{name} screen")
        ranks = {name: [] for name in ("model", "baseline")}
        for row in candidates:
            if type(row) is not dict or set(row) != {
                "design_id",
                "reference",
                "solve_cost",
                "planning_bound",
                "screen_rank",
            }:
                raise EqualBudgetError("closed candidate schema required")
            reference = row["reference"]
            reference_fields = (
                {"status", "value", "per_index"}
                if panel["challenge"] == "battery-v3"
                else {"status", "value"}
            )
            if type(reference) is not dict or set(reference) != reference_fields:
                raise EqualBudgetError("reference status and value required")
            if reference["status"] not in ("FEASIBLE", "INFEASIBLE", "UNRESOLVED"):
                raise EqualBudgetError("reference status invalid")
            if reference["status"] == "FEASIBLE":
                if type(reference["value"]) not in (int, float) or not math.isfinite(
                    reference["value"]
                ):
                    raise EqualBudgetError("feasible value must be finite")
            elif reference["value"] is not None:
                raise EqualBudgetError("only feasible candidates have values")
            if panel["challenge"] == "battery-v3":
                bands = reference["per_index"]
                if type(bands) is not dict or set(bands) != set(weights):
                    raise EqualBudgetError("every battery band required")
                for band in bands.values():
                    if (
                        type(band) is not dict
                        or set(band) != {"status", "value"}
                        or band["status"]
                        not in ("FEASIBLE", "INFEASIBLE", "UNRESOLVED")
                    ):
                        raise EqualBudgetError("battery band verdict required")
                    if band["status"] == "FEASIBLE":
                        if type(band["value"]) not in (int, float) or not math.isfinite(
                            band["value"]
                        ):
                            raise EqualBudgetError("finite per-band value required")
                    elif band["value"] is not None:
                        raise EqualBudgetError("only feasible bands have values")
                statuses = {band["status"] for band in bands.values()}
                expected_status = (
                    "INFEASIBLE"
                    if "INFEASIBLE" in statuses
                    else "UNRESOLVED" if "UNRESOLVED" in statuses else "FEASIBLE"
                )
                if reference["status"] != expected_status:
                    raise EqualBudgetError(
                        "any-band breach or unresolved band must govern map"
                    )
                if expected_status == "FEASIBLE" and not math.isclose(
                    reference["value"],
                    sum(weights[index] * bands[index]["value"] for index in weights),
                    rel_tol=0,
                    abs_tol=1e-9,
                ):
                    raise EqualBudgetError(
                        "weighted map value differs from per-band values"
                    )
            actual = _cost(row["solve_cost"], "solve cost")
            bound = _cost(row["planning_bound"], "planning bound")
            if any(a <= 0 or b < a for a, b in zip(actual, bound)):
                raise EqualBudgetError("planning bound must cover positive solve cost")
            rank = row["screen_rank"]
            if type(rank) is not dict or set(rank) != {"model", "baseline"}:
                raise EqualBudgetError("both committed screen rankings required")
            for name, values in ranks.items():
                if type(rank[name]) is not int or rank[name] < 0:
                    raise EqualBudgetError("screen ranks must be nonnegative integers")
                values.append(rank[name])
        if any(len(set(values)) != len(values) for values in ranks.values()):
            raise EqualBudgetError("screen ranks must be unique per job")


def _best(rows, direction):
    feasible = [r for r in rows if r["reference"]["status"] == "FEASIBLE"]
    if not feasible:
        return None
    sign = 1 if direction == "min" else -1
    return min(feasible, key=lambda r: (sign * r["reference"]["value"], r["design_id"]))


def _one(job, budget, direction, *, cap=None):
    rows = {row["design_id"]: row for row in job["candidates"]}
    reference = track_b.Reference(
        {
            (job["job_id"], design_id): track_b.Case(
                row["reference"], row["solve_cost"]["core_s"], "development-panel"
            )
            for design_id, row in rows.items()
        },
        evidence_class="DEVELOPMENT",
        source="digest-bound-panel",
    )
    true_best = _best(job["candidates"], direction)
    results = {}
    for arm in ARMS:
        ledger = budget_registration.BudgetLedger(
            cap
            if cap is not None
            else budget_registration.BudgetCap(len(rows), budget[0], budget[1])
        )
        if arm == "solver_alone":
            order = job["solver_order"]
            overhead = {"wall_s": 0.0, "core_s": 0.0}
        else:
            kind = "model" if arm == "model_then_solver" else "baseline"
            order = sorted(rows, key=lambda i: (rows[i]["screen_rank"][kind], i))
            overhead = job["screen_cost"][kind]
        if not ledger.charge_overhead(overhead):
            results[arm] = {
                "value": None,
                "regret": None,
                "verified_count": 0,
                "spent_wall_s": 0.0,
                "spent_core_s": 0.0,
                "status": "OVER_BUDGET_BEFORE_SEARCH",
            }
            continue
        verified = []
        for design_id in order:
            row = rows[design_id]
            if not ledger.charge_solver_attempt(
                row["planning_bound"], row["solve_cost"]
            ):
                break  # hard stop before an unaffordable complete solve
            observed = reference.case((job["job_id"], design_id)).quantities
            verified.append({"design_id": design_id, "reference": observed})
        best = _best(verified, direction)
        regret = None
        if best is not None and true_best is not None:
            sign = 1 if direction == "min" else -1
            regret = max(
                0.0,
                sign * (best["reference"]["value"] - true_best["reference"]["value"]),
            )
        results[arm] = {
            "value": None if best is None else best["reference"]["value"],
            "regret": regret,
            "verified_count": ledger.solver_evaluations,
            "spent_wall_s": ledger.wall_s,
            "spent_core_s": ledger.core_s,
            "status": "RAN",
        }
    return results


def _mean(values):
    return None if not values else sum(values) / len(values)


def _quantile(values, probability):
    ordered = sorted(values)
    index = probability * (len(ordered) - 1)
    lo = math.floor(index)
    hi = math.ceil(index)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)


def _summarize(results, direction):
    metrics = {}
    for arm in ARMS:
        values = [row[arm]["value"] for row in results if row[arm]["value"] is not None]
        regrets = [
            row[arm]["regret"] for row in results if row[arm]["regret"] is not None
        ]
        metrics[arm] = {
            "mean_best_verified_value_conditional": _mean(values),
            "mean_regret_conditional": _mean(regrets),
            "feasible_pick_fraction": len(values) / len(results),
            "mean_verified_count": _mean(
                [row[arm]["verified_count"] for row in results]
            ),
            "over_budget_before_search_fraction": _mean(
                [
                    float(row[arm]["status"] == "OVER_BUDGET_BEFORE_SEARCH")
                    for row in results
                ]
            ),
        }
    sign = 1 if direction == "min" else -1
    wins = []
    for row in results:
        model = row["model_then_solver"]["value"]
        solver = row["solver_alone"]["value"]
        wins.append(
            float(
                (model is not None and solver is None)
                or (
                    model is not None
                    and solver is not None
                    and sign * model < sign * solver
                )
            )
        )
    metrics["p_model_beats_solver"] = _mean(wins)
    paired = [
        row["model_then_solver"]["value"] - row["solver_alone"]["value"]
        for row in results
        if row["model_then_solver"]["value"] is not None
        and row["solver_alone"]["value"] is not None
    ]
    metrics["paired_verified_value_count"] = len(paired)
    # The mean is unavailable if an arm has no verified feasible pick on any
    # job. Reporting a conditional subset would silently change the buyer job.
    metrics["paired_verified_value_delta"] = (
        _mean(paired) if len(paired) == len(results) else None
    )
    return metrics


def compare(panel, *, bootstrap_replicates, confidence, seed, registration=None):
    """Return paired, cluster-bootstrap curves; no inference or solver calls."""
    _validate(panel)
    validate_registration = budget_registration.validate
    if panel["challenge"] == "metagrating-3d":
        from .metagrating_budget import validate as validate_registration

    registered = None if registration is None else validate_registration(registration)
    if registered is not None:
        expected = [
            registered.cap(panel["challenge"], tier).time_compute
            for tier in budget_registration.TIERS
        ]
        if panel["budgets"] != expected:
            raise EqualBudgetError("panel ladder differs from registered budgets")
        if panel["registrations"]["cost_plan"] != registered.registration_id:
            raise EqualBudgetError("panel cost plan differs from registration")
    if type(bootstrap_replicates) is not int or bootstrap_replicates < 100:
        raise EqualBudgetError("at least 100 bootstrap replicates required")
    if type(confidence) not in (int, float) or not 0 < confidence < 1:
        raise EqualBudgetError("confidence must be between zero and one")
    if type(seed) is not int:
        raise EqualBudgetError("bootstrap seed must be an integer")
    if any(
        row["reference"]["status"] == "UNRESOLVED"
        for job in panel["jobs"]
        for row in job["candidates"]
    ):
        unresolved_report = {
            "schema": REPORT_SCHEMA,
            "status": "UNRESOLVED_PANEL",
            "challenge": panel["challenge"],
            "panel_digest": panel["panel_digest"],
            "unresolved_candidates": sum(
                row["reference"]["status"] == "UNRESOLVED"
                for job in panel["jobs"]
                for row in job["candidates"]
            ),
            "curves": [],
        }
        if registered is not None:
            unresolved_report.update(
                budget_registration_digest=registered.registration_digest,
                budget_registration_id=registered.registration_id,
                budget_basis=registration["challenge_budgets"][panel["challenge"]][
                    "basis"
                ],
            )
        return unresolved_report
    clusters = defaultdict(list)
    for job in panel["jobs"]:
        clusters[job["cluster_id"]].append(job)
    cluster_ids = sorted(clusters)
    direction = panel["objective"]["direction"]
    curves = []
    for position, budget in enumerate(panel["budgets"]):
        limit = _cost(budget, "budget")
        tier = budget_registration.TIERS[position] if registered is not None else None
        cap = None if registered is None else registered.cap(panel["challenge"], tier)
        by_cluster = {
            cluster_id: [
                _one(job, limit, direction, cap=cap) for job in clusters[cluster_id]
            ]
            for cluster_id in cluster_ids
        }
        observed = _summarize(
            [row for group in by_cluster.values() for row in group], direction
        )
        intervals = None
        if len(cluster_ids) >= 2:
            rng = random.Random(seed)
            draws = []
            for _ in range(bootstrap_replicates):
                sample = [rng.choice(cluster_ids) for _ in cluster_ids]
                draws.append(
                    _summarize(
                        [row for cluster in sample for row in by_cluster[cluster]],
                        direction,
                    )
                )
            tail = (1 - confidence) / 2
            intervals = {}
            for arm in ARMS:
                intervals[arm] = {}
                for metric in observed[arm]:
                    values = [
                        draw[arm][metric]
                        for draw in draws
                        if draw[arm][metric] is not None
                    ]
                    intervals[arm][metric] = (
                        None
                        if not values
                        else [_quantile(values, tail), _quantile(values, 1 - tail)]
                    )
            wins = [draw["p_model_beats_solver"] for draw in draws]
            intervals["p_model_beats_solver"] = [
                _quantile(wins, tail),
                _quantile(wins, 1 - tail),
            ]
            paired_deltas = [draw["paired_verified_value_delta"] for draw in draws]
            intervals["paired_verified_value_delta"] = (
                None
                if observed["paired_verified_value_delta"] is None
                else [
                    _quantile(paired_deltas, tail),
                    _quantile(paired_deltas, 1 - tail),
                ]
            )
        curve = {"budget": budget, "estimates": observed, "bootstrap_ci": intervals}
        if cap is not None:
            curve.update(tier=tier, solver_evaluation_limit=cap.solver_evaluations)
        curves.append(curve)
    report = {
        "schema": REPORT_SCHEMA,
        "status": "OK",
        "challenge": panel["challenge"],
        "panel_digest": panel["panel_digest"],
        "source_digest": panel["source_digest"],
        "decision_rule_id": panel["decision_rule_id"],
        "objective": panel["objective"],
        "registrations": panel["registrations"],
        "execution_plan": panel["execution_plan"],
        "cost_basis": panel["cost_basis"],
        "job_count": len(panel["jobs"]),
        "independent_clusters": len(cluster_ids),
        "confidence": confidence,
        "bootstrap_replicates": bootstrap_replicates,
        "bootstrap_seed": seed,
        "curves": curves,
    }
    if registered is not None:
        report.update(
            budget_registration_digest=registered.registration_digest,
            budget_registration_id=registered.registration_id,
            budget_basis=registration["challenge_budgets"][panel["challenge"]]["basis"],
        )
    return report


def main(argv=None):
    """Read one explicit DEVELOPMENT panel and print aggregate replay curves."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("panel", help="digest-bound development panel JSON")
    parser.add_argument("--bootstrap-replicates", type=int, required=True)
    parser.add_argument("--confidence", type=float, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument(
        "--budget-registration", help="prospective three-tier development budget JSON"
    )
    args = parser.parse_args(argv)
    with open(args.panel, encoding="utf-8") as stream:
        panel = json.load(stream)
    registration = None
    if args.budget_registration is not None:
        with open(args.budget_registration, encoding="utf-8") as stream:
            registration = json.load(stream)
    print(
        json.dumps(
            compare(
                panel,
                bootstrap_replicates=args.bootstrap_replicates,
                confidence=args.confidence,
                seed=args.seed,
                registration=registration,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
