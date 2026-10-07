"""Challenge-neutral design tasks: an engineering decision as a quiz item.

registry: docs/development/evidence/motor-design-tasks-v1/registry.json.

A task states what an engineer decides: the operating `conditions` a design
must serve, a finite `candidates` set, an `objective` (a physical quantity,
its unit, its sense and its aggregate over conditions), hard `constraints`
that must hold at every condition, and an optional `secondary` quantity that
breaks ties. A model never chooses how to decide. Its predicted quantities go
through one fixed optimizer (`select`): exhaustive over the candidates,
feasible only when every constraint holds at every condition, best objective,
ties by the secondary and then the candidate id, abstain when nothing is
predicted feasible. The pick is judged on reference quantities (`judge`), and
regret is in the objective's own unit.

Missing evidence never reads as feasible (`reference_comparison`'s rule): a
candidate with any missing condition is unresolved, and regret is defined
only when every candidate is resolved. Every margin, band and threshold that
would gate a score stays HUMAN_INPUT. DEVELOPMENT; no LIVE authority.
"""

from __future__ import annotations

import statistics

SCHEMA = "carbon.design-task.v1"
SENSES = ("min", "max")
AGGREGATES = ("worst", "mean")
OPS = ("<=", ">=")
KINDS = (
    "SELECTED_FEASIBLE",
    "SELECTED_INFEASIBLE",
    "SELECTED_UNRESOLVED",
    "MISSED_OPPORTUNITY",
    "CORRECT_ABSTENTION",
)


class TaskError(ValueError):
    pass


def _quantity(spec, where):
    if spec.get("sense") not in SENSES or spec.get("aggregate") not in AGGREGATES:
        raise TaskError(f"{where}: sense must be min|max, aggregate worst|mean")
    if not spec.get("quantity") or "unit" not in spec:
        raise TaskError(f"{where}: quantity and unit are required")
    return dict(spec)


def task(task_id, *, conditions, candidates, objective, constraints, secondary=None):
    """A validated task. Candidates and conditions are ids; the quantities
    for each (candidate, condition) pair come from the model or the
    reference."""
    if not conditions or not candidates:
        raise TaskError("a task needs conditions and candidates")
    if len(set(candidates)) != len(candidates):
        raise TaskError("candidate ids must be distinct")
    for c in constraints:
        if c.get("op") not in OPS or not c.get("quantity"):
            raise TaskError("a constraint is {quantity, unit, op <=|>=, limit}")
    return {
        "schema": SCHEMA,
        "task_id": task_id,
        "conditions": list(conditions),
        "candidates": list(candidates),
        "objective": _quantity(objective, "objective"),
        "constraints": [dict(c) for c in constraints],
        "secondary": None if secondary is None else _quantity(secondary, "secondary"),
    }


def _aggregate(spec, values):
    if spec["aggregate"] == "mean":
        return statistics.fmean(values)
    return max(values) if spec["sense"] == "min" else min(values)


def _holds(constraint, value):
    if constraint["op"] == "<=":
        return value <= constraint["limit"]
    return value >= constraint["limit"]


def assess(task_, values):
    """Per candidate: `feasible` (True, False, or None when unresolved),
    `objective` and `secondary` (aggregated over conditions; None unless
    every condition is present). A violated constraint at any present
    condition makes the candidate infeasible even if others are missing."""
    out = {}
    for cand in task_["candidates"]:
        rows = [values.get((cand, cond)) for cond in task_["conditions"]]
        present = [r for r in rows if r is not None]
        violated = any(
            not _holds(c, r[c["quantity"]])
            for r in present
            for c in task_["constraints"]
        )
        complete = len(present) == len(rows)
        feasible = False if violated else (True if complete else None)

        def agg(spec, rows=rows, complete=complete):
            if spec is None or not complete:
                return None
            return _aggregate(spec, [r[spec["quantity"]] for r in rows])

        out[cand] = {
            "feasible": feasible,
            "objective": agg(task_["objective"]),
            "secondary": agg(task_["secondary"]),
        }
    return out


def _signed(spec, value):
    return value if spec["sense"] == "min" else -value


def select(task_, assessed):
    """The fixed optimizer: the best predicted-feasible candidate, or None."""
    feasible = [c for c in task_["candidates"] if assessed[c]["feasible"] is True]
    if not feasible:
        return None
    secondary = task_["secondary"]

    def key(c):
        row = assessed[c]
        tie = 0.0 if secondary is None else _signed(secondary, row["secondary"])
        return (_signed(task_["objective"], row["objective"]), tie, c)

    return min(feasible, key=key)


def judge(task_, predicted, reference):
    """The model's pick under the fixed optimizer, judged on the reference:
    `{kind, selected, best, regret, unit}`. Regret is the objective's
    shortfall from the best reference-feasible candidate, in its unit, for a
    SELECTED_FEASIBLE pick when every candidate is resolved; otherwise None.
    A SELECTED_INFEASIBLE pick is a false-feasible: counted, not priced. An
    abstention where the reference is incomplete and shows nothing feasible
    is SELECTED_UNRESOLVED, never a clean abstention."""
    pick = select(task_, assess(task_, predicted))
    truth = assess(task_, reference)
    resolved = all(row["feasible"] is not None for row in truth.values())
    best = select(task_, truth) if resolved else None
    any_feasible = any(row["feasible"] is True for row in truth.values())
    regret = None
    if pick is None:
        if any_feasible:
            kind = "MISSED_OPPORTUNITY"
        elif resolved:
            kind = "CORRECT_ABSTENTION"
        else:
            kind = "SELECTED_UNRESOLVED"
    elif truth[pick]["feasible"] is True:
        kind = "SELECTED_FEASIBLE"
        if best is not None:
            objective = task_["objective"]
            regret = _signed(objective, truth[pick]["objective"]) - _signed(
                objective, truth[best]["objective"]
            )
    elif truth[pick]["feasible"] is False:
        kind = "SELECTED_INFEASIBLE"
    else:
        kind = "SELECTED_UNRESOLVED"
    return {
        "kind": kind,
        "selected": pick,
        "best": best,
        "regret": regret,
        "unit": task_["objective"]["unit"],
    }


def measures(outcomes):
    """Over a model's judged tasks: `false_feasible` (share of decisions
    whose pick is reference-infeasible), `over_caution` (share of missed
    opportunities), `regret` (mean over priced picks, in the objective's
    unit) and `unresolved` (count, excluded from the rates). Rates are None
    with no decision."""
    decided = [o for o in outcomes if o["kind"] != "SELECTED_UNRESOLVED"]
    priced = [o["regret"] for o in outcomes if o["regret"] is not None]
    n = len(decided)
    return {
        "false_feasible": (
            sum(o["kind"] == "SELECTED_INFEASIBLE" for o in decided) / n if n else None
        ),
        "over_caution": (
            sum(o["kind"] == "MISSED_OPPORTUNITY" for o in decided) / n if n else None
        ),
        "regret": statistics.fmean(priced) if priced else None,
        "unresolved": len(outcomes) - n,
    }
