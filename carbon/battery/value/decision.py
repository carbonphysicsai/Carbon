"""The fixed-candidate decision: measure, select, verify, and score the outcome.

The same functions run for every model, for the reference and for the
labelled synthetic controls:

- `measure` turns one case's outputs (a model's prediction or the
  reference's) into the decision quantities;
- `assess_predicted` / `select` are the model-driven path. They see only a
  model's predicted quantities, never a reference value;
- `assess_reference` verifies every candidate against the reference, with the
  contract's uncertainty bands. It returns FEASIBLE, INFEASIBLE, UNRESOLVED
  or REFERENCE_UNAVAILABLE, and never forces a borderline case into a label;
- `outcome` scores one selection (or abstention) against the reference;
- `classification` gives the per-candidate agreement: false acceptance,
  false rejection and ranking.

Design feasibility is not model eligibility. A model that correctly predicts
that a protocol plates or overheats has done its job; the protocol, not the
model, is infeasible.
"""

from __future__ import annotations

import math

FEASIBLE = "FEASIBLE"
INFEASIBLE = "INFEASIBLE"
UNRESOLVED = "UNRESOLVED"
UNAVAILABLE = "REFERENCE_UNAVAILABLE"
PASS, FAIL = "PASS", "FAIL"


def measure(contract, outputs):
    """Decision quantities from one case's outputs (model or reference)."""
    objective = contract["objective"]
    threshold = objective["threshold_v"]
    start = objective["charge_start_s"]
    window = objective["window_s"]
    voltage = [float(v) for v in outputs["voltage_v"]]
    step = window / (len(voltage) - 1)
    time_to_cv = None
    for i in range(1, len(voltage)):
        t_i = i * step
        if t_i <= start:
            continue
        if voltage[i] >= threshold:
            a, b = voltage[i - 1], voltage[i]
            fraction = 1.0 if b == a else (threshold - a) / (b - a)
            crossing = (i - 1) * step + step * min(max(fraction, 0.0), 1.0)
            time_to_cv = max(crossing, start) - start
            break
    temperatures = [float(t) for t in outputs["temperature_c"]]
    return {
        "time_to_cv_onset_s": time_to_cv,
        "plating_margin_v": float(outputs["plating_margin_v"]),
        "peak_temperature_c": max(temperatures),
    }


def _constraint_rules(contract):
    rules = {}
    for constraint in contract["constraints"]:
        rules[constraint["id"]] = constraint
    return rules


def _check(contract, quantities, band=None):
    """Per-constraint PASS / FAIL / UNRESOLVED for one condition."""
    rules = _constraint_rules(contract)
    bands = band or {}
    window = contract["objective"]["window_s"] - contract["objective"]["charge_start_s"]
    result = {}
    time = quantities["time_to_cv_onset_s"]
    u = bands.get("time_to_cv_onset_s", 0.0)
    if time is None:
        result["reach_cv_in_window"] = FAIL
    elif time > window - u:
        result["reach_cv_in_window"] = UNRESOLVED
    else:
        result["reach_cv_in_window"] = PASS
    margin = quantities["plating_margin_v"]
    limit = rules["no_plating_onset"]["threshold"]
    u = bands.get("plating_margin_v", 0.0)
    result["no_plating_onset"] = (
        PASS if margin - limit > u else FAIL if limit - margin > u else UNRESOLVED
    )
    if u == 0.0:
        result["no_plating_onset"] = PASS if margin >= limit else FAIL
    peak = quantities["peak_temperature_c"]
    limit = rules["peak_temperature"]["threshold"]
    u = bands.get("peak_temperature_c", 0.0)
    result["peak_temperature"] = (
        PASS if limit - peak > u else FAIL if peak - limit > u else UNRESOLVED
    )
    if u == 0.0:
        result["peak_temperature"] = PASS if peak <= limit else FAIL
    return result


def _violations(contract, quantities):
    """How far a condition misses each failed constraint (positive numbers)."""
    rules = _constraint_rules(contract)
    out = {}
    if quantities["time_to_cv_onset_s"] is None:
        out["reach_cv_in_window"] = "NOT_REACHED_IN_WINDOW"
    shortfall = rules["no_plating_onset"]["threshold"] - quantities["plating_margin_v"]
    if shortfall > 0:
        out["no_plating_onset"] = shortfall
    excess = quantities["peak_temperature_c"] - rules["peak_temperature"]["threshold"]
    if excess > 0:
        out["peak_temperature"] = excess
    return out


def _objective(per_condition):
    times = [q["time_to_cv_onset_s"] for q in per_condition]
    if any(t is None for t in times):
        return None
    return max(times)


def assess_predicted(contract, scenario, candidates, quantities):
    """A model's view of every candidate. `quantities[(candidate, index)]`
    holds the model's predicted quantities; no reference value is used."""
    out = {}
    for candidate in candidates:
        per = [
            quantities[(candidate["id"], i)] for i in range(len(scenario["conditions"]))
        ]
        checks = [_check(contract, q) for q in per]
        feasible = all(v == PASS for c in checks for v in c.values())
        out[candidate["id"]] = {
            "feasible": feasible,
            "objective": _objective(per),
            "checks": checks,
        }
    return out


def _tie_key(candidate, objective):
    return (objective, candidate["c1"], candidate["c2"], candidate["id"])


def select(candidates, predicted):
    """The deterministic selector: the lowest predicted objective among the
    candidates predicted feasible, ties by lower c1 then c2; None abstains."""
    pool = [
        (_tie_key(c, predicted[c["id"]]["objective"]), c["id"])
        for c in candidates
        if predicted[c["id"]]["feasible"]
        and predicted[c["id"]]["objective"] is not None
    ]
    return min(pool)[1] if pool else None


def assess_reference(contract, scenario, candidates, references):
    """Reference verification of every candidate, with the uncertainty bands.

    `references[(candidate, index)]` is a reference record (with `status` and
    `outputs`) or missing. A missing or failed reference makes the candidate
    REFERENCE_UNAVAILABLE, never INFEASIBLE.
    """
    bands = contract["reference"]["uncertainty"]["bands"]
    out = {}
    for candidate in candidates:
        records = [
            references.get((candidate["id"], i))
            for i in range(len(scenario["conditions"]))
        ]
        if any(r is None or r.get("status") != "OK" for r in records):
            out[candidate["id"]] = {"status": UNAVAILABLE, "objective": None}
            continue
        per = [measure(contract, r["outputs"]) for r in records]
        checks = [_check(contract, q, bands) for q in per]
        values = [v for c in checks for v in c.values()]
        status = (
            INFEASIBLE
            if FAIL in values
            else UNRESOLVED if UNRESOLVED in values else FEASIBLE
        )
        out[candidate["id"]] = {
            "status": status,
            "objective": _objective(per),
            "checks": checks,
            "violations": [_violations(contract, q) for q in per],
            "quantities": per,
        }
    return out


def best_in_set(candidates, reference):
    """The best reference-FEASIBLE candidate in the tested set, or None.
    Not a global optimum: only the frozen candidates were tested."""
    pool = [
        (_tie_key(c, reference[c["id"]]["objective"]), c["id"])
        for c in candidates
        if reference[c["id"]]["status"] == FEASIBLE
    ]
    return min(pool)[1] if pool else None


def outcome(contract, candidates, selection, reference, baseline_id):
    """Score one selection (or abstention) against the reference."""
    costs = contract["mistake_costs"]
    unit = contract["minimum_useful_improvement_s"]
    best = best_in_set(candidates, reference)
    any_unresolved = any(
        reference[c["id"]]["status"] in (UNRESOLVED, UNAVAILABLE) for c in candidates
    )
    base = reference[baseline_id]
    result = {
        "selected": selection,
        "best_in_tested_set": best,
        "best_objective_s": None if best is None else reference[best]["objective"],
        "baseline": baseline_id,
        "baseline_status": base["status"],
    }
    if selection is None:
        if best is None:
            kind = "ABSTENTION_UNRESOLVED" if any_unresolved else "CORRECT_ABSTENTION"
            loss = None if any_unresolved else 0.0
        else:
            kind, loss = "MISSED_OPPORTUNITY", costs["missed_opportunity"]
        return {**result, "kind": kind, "decision_loss": loss}
    verified = reference[selection]
    result["selected_status"] = verified["status"]
    if verified["status"] == FEASIBLE:
        objective = verified["objective"]
        gap = objective - result["best_objective_s"]
        improvement = (
            base["objective"] - objective if base["status"] == FEASIBLE else None
        )
        return {
            **result,
            "kind": "SELECTED_FEASIBLE",
            "verified_objective_s": objective,
            "gap_to_best_in_set_s": gap,
            "improvement_vs_baseline_s": improvement,
            "useful_improvement": (
                None
                if improvement is None
                else improvement >= contract["minimum_useful_improvement_s"]
            ),
            "decision_loss": costs["regret_per_minimum_useful_improvement"]
            * gap
            / unit,
        }
    if verified["status"] == INFEASIBLE:
        return {
            **result,
            "kind": "SELECTED_INFEASIBLE",
            "violations": verified["violations"],
            "decision_loss": costs["false_acceptance"],
        }
    # Unresolved or unavailable at the reference: never scored either way.
    kind = (
        "SELECTED_UNRESOLVED"
        if verified["status"] == UNRESOLVED
        else "SELECTED_REFERENCE_UNAVAILABLE"
    )
    return {**result, "kind": kind, "decision_loss": None}


def kendall_tau_b(xs, ys):
    """Kendall's tau-b of two equal-length sequences; None if undefined."""
    n = len(xs)
    concordant = discordant = ties_x = ties_y = 0
    for i in range(n):
        for j in range(i + 1, n):
            dx = (xs[i] > xs[j]) - (xs[i] < xs[j])
            dy = (ys[i] > ys[j]) - (ys[i] < ys[j])
            if dx == 0 and dy == 0:
                continue
            if dx == 0:
                ties_x += 1
            elif dy == 0:
                ties_y += 1
            elif dx == dy:
                concordant += 1
            else:
                discordant += 1
    denominator = math.sqrt(
        (concordant + discordant + ties_x) * (concordant + discordant + ties_y)
    )
    if denominator == 0:
        return None
    return (concordant - discordant) / denominator


def classification(candidates, predicted, reference):
    """Per-candidate agreement with the reference (resolved candidates only)."""
    false_accept = false_reject = resolved = 0
    for candidate in candidates:
        status = reference[candidate["id"]]["status"]
        if status not in (FEASIBLE, INFEASIBLE):
            continue
        resolved += 1
        says = predicted[candidate["id"]]["feasible"]
        if says and status == INFEASIBLE:
            false_accept += 1
        if not says and status == FEASIBLE:
            false_reject += 1
    feasible = [
        c
        for c in candidates
        if reference[c["id"]]["status"] == FEASIBLE
        and predicted[c["id"]]["objective"] is not None
    ]
    tau = (
        kendall_tau_b(
            [predicted[c["id"]]["objective"] for c in feasible],
            [reference[c["id"]]["objective"] for c in feasible],
        )
        if len(feasible) >= 2
        else None
    )
    best = best_in_set(candidates, reference)
    predicted_best = (
        min((_tie_key(c, predicted[c["id"]]["objective"]), c["id"]) for c in feasible)[
            1
        ]
        if feasible
        else None
    )
    return {
        "resolved_candidates": resolved,
        "false_acceptances": false_accept,
        "false_rejections": false_reject,
        "rank_tau_among_feasible": tau,
        "top1_among_feasible": None if best is None else predicted_best == best,
    }
