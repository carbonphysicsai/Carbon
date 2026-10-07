"""Challenge-neutral design tasks: an engineering decision as one immutable task.

A task is what an engineer decides, registered before any model or reference
is consulted (CHALLENGE-DESIGN-OPTIMIZERS-01's shared decision contract, #759):

- **Identity.** Challenge and decision-contract versions, the action grammar
  identity, the finite bank (candidate ids in their frozen order, with a
  digest), the optimizer id and version, its query budget and seed, the
  observer version and the reference-bank identity. `task_digest` hashes
  all of it.
- **Conditions and strata.** Each condition names its stratum; each stratum
  carries its population mass `p`, diagnostic sampling `q` and evidence
  weight `w`, kept separate. Every hard limit is checked at every condition
  before anything is ranked (no average rescues a breach).
- **Objective.** A physical quantity with its unit, sense and aggregate over
  conditions (worst or mean), and an optional lexicographic secondary.
- **Hard limits and bands.** Each limit has a quantity, unit, operator and
  value, and an optional reference band: a reference value within the band
  of the limit is UNRESOLVED for that limit, never a pass or a fail.
- **Tie rule.** Objective, then the secondary, then the frozen bank order
  (`tie_rule: "secondary_then_bank_order"`), the only rule implemented.

The fixed optimizer (`select`) is exhaustive over the bank on the model's
predicted quantities: feasible only when every limit holds at every
condition; abstain when nothing is predicted feasible. `commit` records the
pick with the task digest before any reference access, and `judge` refuses
a commitment for another task. The reference's verdict on the bank is
FEASIBLE_EXISTS, NONE_FEASIBLE or UNRESOLVED. Regret is in the objective's
unit, against the best reference-feasible candidate of the same bank, and
only when every candidate is resolved. A reference-infeasible pick is a
false-feasible: counted, not priced. Missing reference evidence never reads
as feasible, and is never a candidate's scientific failure.

Every value that would gate a score (bands, budgets, weights, thresholds)
comes from the task's registration; nothing here chooses one. DEVELOPMENT;
no LIVE authority.
"""

from __future__ import annotations

import hashlib
import json
import statistics

SCHEMA = "carbon.design-task.v1"
COMMIT_SCHEMA = "carbon.design-task.commitment.v1"
SENSES = ("min", "max")
AGGREGATES = ("worst", "mean")
OPS = ("<=", ">=")
TIE_RULES = ("secondary_then_bank_order",)
REFERENCE_STATES = ("FEASIBLE_EXISTS", "NONE_FEASIBLE", "UNRESOLVED")
KINDS = (
    "SELECTED_FEASIBLE",
    "SELECTED_INFEASIBLE",
    "SELECTED_UNRESOLVED",
    "MISSED_OPPORTUNITY",
    "CORRECT_ABSTENTION",
    "ABSTENTION_UNRESOLVED",
)
IDENTITY_FIELDS = (
    "challenge",
    "contract_version",
    "action_grammar",
    "optimizer",
    "query_budget",
    "seed",
    "observer_version",
    "reference_bank",
)


class TaskError(ValueError):
    pass


def digest(value):
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _quantity(spec, where):
    if spec.get("sense") not in SENSES or spec.get("aggregate") not in AGGREGATES:
        raise TaskError(f"{where}: sense must be min|max, aggregate worst|mean")
    if not spec.get("quantity") or "unit" not in spec:
        raise TaskError(f"{where}: quantity and unit are required")
    return dict(spec)


def task(
    task_id,
    *,
    identity,
    conditions,
    strata,
    candidates,
    objective,
    limits,
    secondary=None,
    tie_rule="secondary_then_bank_order",
):
    """A validated, immutable task. `identity` holds `IDENTITY_FIELDS`
    (opaque registered values); `conditions` are `{id, stratum}`; `strata`
    maps a stratum to `{p, q, w}`; `candidates` are ids in the bank's frozen
    order; `limits` are `{quantity, unit, op, value, band?}`."""
    missing = [f for f in IDENTITY_FIELDS if f not in identity]
    if missing:
        raise TaskError("identity lacks " + ", ".join(missing))
    if not conditions or not candidates:
        raise TaskError("a task needs conditions and candidates")
    if len(set(candidates)) != len(candidates):
        raise TaskError("candidate ids must be distinct")
    ids = [c["id"] for c in conditions]
    if len(set(ids)) != len(ids):
        raise TaskError("condition ids must be distinct")
    for c in conditions:
        if c.get("stratum") not in strata:
            raise TaskError(f"condition {c.get('id')} has no registered stratum")
    for name, s in strata.items():
        if set(s) != {"p", "q", "w"}:
            raise TaskError(f"stratum {name} must give p, q and w")
    for limit in limits:
        if limit.get("op") not in OPS or not limit.get("quantity"):
            raise TaskError("a limit is {quantity, unit, op <=|>=, value, band?}")
        if "unit" not in limit or "value" not in limit:
            raise TaskError("a limit needs its unit and value")
        if limit.get("band", 0) < 0:
            raise TaskError("a band is non-negative")
    if tie_rule not in TIE_RULES:
        raise TaskError(f"tie rule must be one of {TIE_RULES}")
    body = {
        "schema": SCHEMA,
        "task_id": task_id,
        "identity": dict(identity),
        "conditions": [dict(c) for c in conditions],
        "strata": {k: dict(v) for k, v in strata.items()},
        "candidates": list(candidates),
        "bank_digest": digest(list(candidates)),
        "objective": _quantity(objective, "objective"),
        "limits": [dict(limit) for limit in limits],
        "secondary": None if secondary is None else _quantity(secondary, "secondary"),
        "tie_rule": tie_rule,
    }
    return {**body, "task_digest": digest(body)}


def _aggregate(spec, values):
    if spec["aggregate"] == "mean":
        return statistics.fmean(values)
    return max(values) if spec["sense"] == "min" else min(values)


def _verdict(limit, value, banded):
    """True (holds), False (breached) or None (within the reference band)."""
    margin = limit["value"] - value if limit["op"] == "<=" else value - limit["value"]
    band = limit.get("band", 0.0) if banded else 0.0
    if abs(margin) <= band and band > 0:
        return None
    return margin >= 0


def assess(task_, values, *, reference=False):
    """Per candidate: `feasible` (True, False or None when unresolved),
    `objective` and `secondary` (aggregated over conditions; None unless
    every condition is present). `values[(candidate, condition)]` maps
    quantities. With `reference=True` the limits' bands apply. A breach at
    any present condition makes the candidate infeasible even if others are
    missing or unresolved."""
    conditions = [c["id"] for c in task_["conditions"]]
    out = {}
    for cand in task_["candidates"]:
        rows = [values.get((cand, cond)) for cond in conditions]
        present = [r for r in rows if r is not None]
        verdicts = [
            _verdict(limit, r[limit["quantity"]], reference)
            for r in present
            for limit in task_["limits"]
        ]
        complete = len(present) == len(rows)
        if False in verdicts:
            feasible = False
        elif complete and None not in verdicts:
            feasible = True
        else:
            feasible = None

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
    """The fixed optimizer: the best feasible candidate under the tie rule,
    or None (abstain)."""
    order = {c: i for i, c in enumerate(task_["candidates"])}
    feasible = [c for c in task_["candidates"] if assessed[c]["feasible"] is True]
    if not feasible:
        return None
    secondary = task_["secondary"]

    def key(c):
        row = assessed[c]
        tie = 0.0 if secondary is None else _signed(secondary, row["secondary"])
        return (_signed(task_["objective"], row["objective"]), tie, order[c])

    return min(feasible, key=key)


def commit(task_, predicted, *, model_id):
    """The model's pick, recorded with the task digest before any reference
    access. `predicted` covers what the model returned; a candidate it did
    not predict cannot be selected."""
    selected = select(task_, assess(task_, predicted))
    body = {
        "schema": COMMIT_SCHEMA,
        "task_digest": task_["task_digest"],
        "model_id": model_id,
        "selected": selected,
        "predictions_digest": digest(
            sorted([list(k), v] for k, v in predicted.items())
        ),
    }
    return {**body, "commitment_digest": digest(body)}


def reference_state(task_, truth):
    if any(row["feasible"] is True for row in truth.values()):
        return "FEASIBLE_EXISTS"
    if all(row["feasible"] is False for row in truth.values()):
        return "NONE_FEASIBLE"
    return "UNRESOLVED"


def judge(task_, commitment, reference):
    """A committed pick judged on reference quantities (bands applied):
    `{kind, selected, best, reference_state, regret, unit}`."""
    body = {k: v for k, v in commitment.items() if k != "commitment_digest"}
    if digest(body) != commitment.get("commitment_digest"):
        raise TaskError("the commitment was altered")
    if commitment["task_digest"] != task_["task_digest"]:
        raise TaskError("the commitment is for another task")
    pick = commitment["selected"]
    truth = assess(task_, reference, reference=True)
    state = reference_state(task_, truth)
    resolved = all(row["feasible"] is not None for row in truth.values())
    best = select(task_, truth) if resolved else None
    regret = None
    if pick is None:
        kind = {
            "FEASIBLE_EXISTS": "MISSED_OPPORTUNITY",
            "NONE_FEASIBLE": "CORRECT_ABSTENTION",
            "UNRESOLVED": "ABSTENTION_UNRESOLVED",
        }[state]
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
        "reference_state": state,
        "regret": regret,
        "unit": task_["objective"]["unit"],
    }


def measures(outcomes):
    """Over a model's judged tasks: `false_feasible` (share of resolved
    decisions whose pick is reference-infeasible), `over_caution` (share of
    missed opportunities), `regret` (mean over priced picks, in the
    objective's unit) and `unresolved` (count, excluded from the rates).
    Rates are None with no resolved decision. How an unresolved decision is
    scored is the Challenge's registered policy, not this function's."""
    unresolved = ("SELECTED_UNRESOLVED", "ABSTENTION_UNRESOLVED")
    decided = [o for o in outcomes if o["kind"] not in unresolved]
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
