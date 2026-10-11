"""Registered, stratum-aware design-decision diagnostics (DEVELOPMENT).

P is the target job population, Q is the diagnostic draw law and w is the
registered evidence weight. They are never substituted for each other. No
function here decides whether a measure enters an official score.
"""

from __future__ import annotations

import math

from carbon.design_search import tasks

SCHEMA = "carbon.design-task.measures.v1"
AGGREGATE_SCHEMA = "carbon.design-task.quantile-aggregate.v1"
UNRESOLVED = ("SELECTED_UNRESOLVED", "ABSTENTION_UNRESOLVED")


def _resolved(outcome):
    return (
        outcome["kind"] not in UNRESOLVED
        and outcome.get("reference_state") != "UNRESOLVED"
        and outcome.get("reference_resolved") is not False
    )


def _number(value, where):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise tasks.TaskError(f"{where} must be finite and non-negative")
    return float(value)


def _quantile(values, probability):
    """Left-continuous weighted inverse CDF; no interpolation."""
    if not values:
        return None
    total = sum(weight for _, weight in values)
    threshold = probability * total
    running = 0.0
    for value, weight in sorted(values):
        running += weight
        if running >= threshold and weight > 0:
            return value
    return max(value for value, weight in values if weight > 0)


def _view(rows, masses, strata, probability, *, evidence_weighted, basis):
    weighted = []
    for name, outcome in rows:
        mass = masses[name] * (strata[name]["w"] if evidence_weighted else 1)
        weighted.append((outcome, mass))
    all_mass = sum(weight for _, weight in weighted)
    decided = [(r, weight) for r, weight in weighted if _resolved(r)]
    decided_mass = sum(weight for _, weight in decided)
    priced = [
        (float(r["regret"]), weight)
        for r, weight in weighted
        if _resolved(r) and r["regret"] is not None
    ]
    priced_mass = sum(weight for _, weight in priced)
    return {
        "basis": basis + "; equal within-stratum jobs",
        "all_mass": all_mass,
        "resolved_mass": decided_mass,
        "priced_mass": priced_mass,
        "false_feasible": (
            sum(weight for r, weight in decided if r["kind"] == "SELECTED_INFEASIBLE")
            / decided_mass
            if decided_mass
            else None
        ),
        "over_caution": (
            sum(weight for r, weight in decided if r["kind"] == "MISSED_OPPORTUNITY")
            / decided_mass
            if decided_mass
            else None
        ),
        "unresolved_rate": (
            sum(weight for r, weight in weighted if not _resolved(r)) / all_mass
            if all_mass
            else None
        ),
        "regret_mean": (
            sum(value * weight for value, weight in priced) / priced_mass
            if priced_mass
            else None
        ),
        "regret_quantile": _quantile(priced, probability) if priced_mass else None,
    }


def per_stratum_measures(records, *, strata, aggregate):
    """Measure tagged job outcomes under separate P and Q views.

    Each record is `{stratum, outcome}` where outcome is `tasks.judge` output.
    `aggregate` must register a quantile probability; no default is chosen.
    Each registered stratum must have at least one observed job. The caller
    supplies real population/draw/evidence values through registration.
    """
    if (
        type(aggregate) is not dict
        or set(aggregate) != {"schema", "probability"}
        or aggregate["schema"] != AGGREGATE_SCHEMA
    ):
        raise tasks.TaskError("registered quantile aggregate required")
    probability = _number(aggregate["probability"], "quantile probability")
    if probability > 1:
        raise tasks.TaskError("quantile probability must be at most one")
    if type(strata) is not dict or not strata:
        raise tasks.TaskError("registered strata required")
    checked = {}
    for name, spec in strata.items():
        if (
            type(name) is not str
            or not name
            or type(spec) is not dict
            or set(spec) != {"p", "q", "w"}
        ):
            raise tasks.TaskError("stratum requires p, q and w")
        checked[name] = {key: _number(spec[key], key) for key in ("p", "q", "w")}
    for key in ("p", "q"):
        if not math.isclose(
            sum(spec[key] for spec in checked.values()), 1.0, abs_tol=1e-9
        ):
            raise tasks.TaskError(f"{key} stratum masses must sum to one")
    if not any(spec["w"] > 0 for spec in checked.values()):
        raise tasks.TaskError("positive evidence weight required")
    grouped = {name: [] for name in checked}
    for record in records:
        if (
            type(record) is not dict
            or set(record) != {"stratum", "outcome"}
            or record["stratum"] not in grouped
        ):
            raise tasks.TaskError("tagged registered outcome required")
        outcome = record["outcome"]
        if (
            type(outcome) is not dict
            or outcome.get("kind") not in tasks.KINDS
            or type(outcome.get("reference_resolved")) is not bool
        ):
            raise tasks.TaskError("known judged outcome required")
        regret = outcome.get("regret")
        if regret is not None:
            _number(regret, "regret")
        grouped[record["stratum"]].append(outcome)
    if any(not rows for rows in grouped.values()):
        raise tasks.TaskError("all registered strata need observed jobs")
    units = {
        o.get("unit")
        for rows in grouped.values()
        for o in rows
        if o.get("regret") is not None
    }
    if len(units) > 1:
        raise tasks.TaskError("regret units differ across jobs")
    flat = [
        (name, outcome) for name, outcomes in grouped.items() for outcome in outcomes
    ]
    per = {}
    for name, outcomes in grouped.items():
        resolved = [outcome for outcome in outcomes if _resolved(outcome)]
        priced = [
            outcome["regret"] for outcome in resolved if outcome["regret"] is not None
        ]
        per[name] = {
            "p": checked[name]["p"],
            "q": checked[name]["q"],
            "w": checked[name]["w"],
            "jobs": len(outcomes),
            "resolved": len(resolved),
            "unresolved": len(outcomes) - len(resolved),
            "false_feasible": (
                sum(o["kind"] == "SELECTED_INFEASIBLE" for o in resolved)
                / len(resolved)
                if resolved
                else None
            ),
            "over_caution": (
                sum(o["kind"] == "MISSED_OPPORTUNITY" for o in resolved) / len(resolved)
                if resolved
                else None
            ),
            "regret": sum(priced) / len(priced) if priced else None,
        }
    # A stratum mass is spread over its observed jobs. This keeps population
    # composition separate from uneven diagnostic sampling counts.
    return {
        "schema": SCHEMA,
        "quantile": {
            "probability": probability,
            "convention": "weighted_inverse_cdf_left",
        },
        "unit": next(iter(units), None),
        "per_stratum": per,
        "P": _view(
            flat,
            {n: checked[n]["p"] / len(grouped[n]) for n in checked},
            checked,
            probability,
            evidence_weighted=False,
            basis="registered P mass",
        ),
        "Q": _view(
            flat,
            {n: checked[n]["q"] / len(grouped[n]) for n in checked},
            checked,
            probability,
            evidence_weighted=False,
            basis="registered Q mass",
        ),
        "weighted_Q": _view(
            flat,
            {n: checked[n]["q"] / len(grouped[n]) for n in checked},
            checked,
            probability,
            evidence_weighted=True,
            basis="registered Q mass times evidence w",
        ),
    }
