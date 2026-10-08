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

The original v1 interface accepts precomputed predictions. Runnable v2 tasks
add a versioned action grammar, canonical lattice bank, registered optimizer,
and counted model-query budget. `run_optimizer` commits before reference
access. The reference's verdict on the bank is
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
import math
import statistics
from decimal import ROUND_HALF_DOWN, Decimal, InvalidOperation

SCHEMA = "carbon.design-task.v1"
RUNNABLE_SCHEMA = "carbon.design-task.v2"
GRAMMAR_SCHEMA = "carbon.action-grammar.v1"
COMMIT_SCHEMA = "carbon.design-task.commitment.v1"
SENSES = ("min", "max")
AGGREGATES = ("worst", "mean", "quantile")
QUANTILE_RULE = "inverse_cdf_left.v1"
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
        raise TaskError(
            f"{where}: sense must be min|max, aggregate worst|mean|quantile"
        )
    if not spec.get("quantity") or "unit" not in spec:
        raise TaskError(f"{where}: quantity and unit are required")
    if spec["aggregate"] == "quantile":
        probability = spec.get("probability")
        if (
            type(probability) not in (int, float)
            or not math.isfinite(probability)
            or not 0 <= probability <= 1
            or spec.get("rule") != QUANTILE_RULE
        ):
            raise TaskError(
                f"{where}: quantile needs probability in [0,1] and registered rule"
            )
    elif "probability" in spec or "rule" in spec:
        raise TaskError(f"{where}: quantile fields require quantile aggregation")
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
    actions=None,
):
    """A validated task with its registration digest.

    `conditions` are `{id, stratum}`; `strata` maps a stratum to `{p, q, w}`;
    `candidates` are ids in frozen bank order. Without `actions`, the original
    v1 identity fields stay opaque. With `actions`, v2 validates the typed
    grammar and optimizer in identity and binds canonical actions to the bank.
    """
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
    runnable = actions is not None
    if runnable:
        _validate_runnable(identity, candidates, actions)
    body = {
        "schema": RUNNABLE_SCHEMA if runnable else SCHEMA,
        "task_id": task_id,
        "identity": dict(identity),
        "conditions": [dict(c) for c in conditions],
        "strata": {k: dict(v) for k, v in strata.items()},
        "candidates": list(candidates),
        "bank_digest": digest(
            {"candidates": list(candidates), "actions": actions}
            if runnable
            else list(candidates)
        ),
        "objective": _quantity(objective, "objective"),
        "limits": [dict(limit) for limit in limits],
        "secondary": None if secondary is None else _quantity(secondary, "secondary"),
        "tie_rule": tie_rule,
    }
    if runnable:
        body["actions"] = {c: dict(actions[c]) for c in candidates}
    # Freeze nested caller-owned registration values before hashing. A caller
    # changing its original dict must not change a previously registered task.
    body = json.loads(json.dumps(body))
    return {**body, "task_digest": digest(body)}


def _verify_task_digest(task_):
    if digest({k: v for k, v in task_.items() if k != "task_digest"}) != task_.get(
        "task_digest"
    ):
        raise TaskError("registered task was altered")


def _number(value, where):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TaskError(f"{where}: finite number required")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise TaskError(f"{where}: finite number required") from exc
    if not result.is_finite():
        raise TaskError(f"{where}: finite number required")
    return result


def _validate_grammar(grammar):
    if not isinstance(grammar, dict) or set(grammar) != {
        "schema",
        "version",
        "variables",
        "rules",
    }:
        raise TaskError("action grammar needs schema, version, variables and rules")
    if (
        grammar["schema"] != GRAMMAR_SCHEMA
        or not isinstance(grammar["version"], str)
        or not grammar["version"]
    ):
        raise TaskError("unsupported action grammar")
    variables = grammar["variables"]
    if not isinstance(variables, list) or not variables:
        raise TaskError("action grammar needs variables")
    names = []
    for var in variables:
        if (
            not isinstance(var, dict)
            or not isinstance(var.get("name"), str)
            or not var["name"]
        ):
            raise TaskError("invalid action variable")
        names.append(var["name"])
        kind = var.get("type")
        if kind in ("number", "integer"):
            if set(var) != {"name", "type", "min", "max", "step"}:
                raise TaskError("numeric variable needs min, max and step")
            lo, hi, step = (_number(var[k], k) for k in ("min", "max", "step"))
            if lo > hi or step <= 0 or (hi - lo) % step != 0:
                raise TaskError(
                    "numeric lattice bounds must align with a positive step"
                )
            if kind == "integer" and any(
                x != x.to_integral_value() for x in (lo, hi, step)
            ):
                raise TaskError("integer lattice requires integer bounds and step")
        elif kind == "enum":
            if (
                set(var) != {"name", "type", "values"}
                or not isinstance(var["values"], list)
                or not var["values"]
            ):
                raise TaskError("enum variable needs values")
            if any(not isinstance(x, str) for x in var["values"]) or len(
                set(var["values"])
            ) != len(var["values"]):
                raise TaskError("enum values must be distinct strings")
        else:
            raise TaskError("unsupported action variable type")
    if len(set(names)) != len(names):
        raise TaskError("action variable names must be distinct")
    if not isinstance(grammar["rules"], list):
        raise TaskError("action grammar rules must be a list")
    numeric = {v["name"] for v in variables if v["type"] != "enum"}
    for rule in grammar["rules"]:
        if (
            not isinstance(rule, dict)
            or set(rule) != {"kind", "coefficients", "op", "value"}
            or rule["kind"] != "linear"
        ):
            raise TaskError("unsupported action validity rule")
        if (
            rule["op"] not in OPS
            or not isinstance(rule["coefficients"], dict)
            or not rule["coefficients"]
            or not set(rule["coefficients"]) <= numeric
        ):
            raise TaskError("invalid linear validity rule")
        _number(rule["value"], "rule value")
        for coefficient in rule["coefficients"].values():
            _number(coefficient, "rule coefficient")


def snap_action(grammar, action):
    """Canonical lattice action, or TaskError for bounds/validity failures."""
    _validate_grammar(grammar)
    if not isinstance(action, dict) or set(action) != {
        v["name"] for v in grammar["variables"]
    }:
        raise TaskError("action does not match registered variables")
    snapped = {}
    for var in grammar["variables"]:
        name = var["name"]
        raw = action[name]
        if var["type"] == "enum":
            if raw not in var["values"]:
                raise TaskError(f"{name}: invalid enum value")
            snapped[name] = raw
            continue
        value = _number(raw, name)
        lo, hi, step = (_number(var[k], k) for k in ("min", "max", "step"))
        if value < lo or value > hi:
            raise TaskError(f"{name}: outside bounds")
        index = ((value - lo) / step).to_integral_value(rounding=ROUND_HALF_DOWN)
        point = lo + index * step
        snapped[name] = int(point) if var["type"] == "integer" else float(point)
    for rule in grammar["rules"]:
        lhs = sum(
            _number(coef, "coefficient") * _number(snapped[name], name)
            for name, coef in rule["coefficients"].items()
        )
        rhs = _number(rule["value"], "rule value")
        if not (lhs <= rhs if rule["op"] == "<=" else lhs >= rhs):
            raise TaskError("action violates registered validity rule")
    return snapped


def _validate_runnable(identity, candidates, actions):
    if any(not isinstance(candidate, str) or not candidate for candidate in candidates):
        raise TaskError("runnable candidate ids must be non-empty strings")
    grammar = identity["action_grammar"]
    _validate_grammar(grammar)
    optimizer = identity["optimizer"]
    if (
        not isinstance(optimizer, dict)
        or optimizer.get("version") != "v1"
        or optimizer.get("class") not in ("exhaustive", "multi_start_local")
    ):
        raise TaskError("unsupported registered optimizer")
    if optimizer["class"] == "exhaustive":
        if set(optimizer) != {"class", "version"}:
            raise TaskError("exhaustive optimizer has unexpected fields")
    elif (
        set(optimizer) != {"class", "version", "starts"}
        or not isinstance(optimizer["starts"], list)
        or not optimizer["starts"]
        or any(not isinstance(start, str) for start in optimizer["starts"])
        or len(set(optimizer["starts"])) != len(optimizer["starts"])
        or not set(optimizer["starts"]) <= set(candidates)
    ):
        raise TaskError("multi-start optimizer needs distinct registered bank starts")
    budget, seed = identity["query_budget"], identity["seed"]
    if isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0:
        raise TaskError("query budget must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise TaskError("seed must be a non-negative integer")
    if not isinstance(actions, dict) or set(actions) != set(candidates):
        raise TaskError("actions must cover the finite bank exactly")
    seen = set()
    for candidate in candidates:
        canonical = snap_action(grammar, actions[candidate])
        if canonical != actions[candidate]:
            raise TaskError("bank actions must already be canonical")
        key = digest(canonical)
        if key in seen:
            raise TaskError("bank actions must be distinct after snapping")
        seen.add(key)


def _aggregate(spec, values):
    if spec["aggregate"] == "mean":
        return statistics.fmean(values)
    if spec["aggregate"] == "quantile":
        index = max(0, math.ceil(spec["probability"] * len(values)) - 1)
        return sorted(values)[index]
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
    if task_["schema"] == RUNNABLE_SCHEMA:
        raise TaskError("runnable tasks require run_optimizer for budget accounting")
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


def run_optimizer(task_, predictor, *, model_id):
    """Execute a registered optimizer on model predictions only."""
    from carbon.design_search.optimizer import run_optimizer as execute

    return execute(task_, predictor, model_id=model_id)


def audit_optimizer(primary_task, audit_task, predictor, *, model_id):
    """Run a second registered path without changing the primary pick."""
    from carbon.design_search.optimizer import audit_optimizer as execute

    return execute(primary_task, audit_task, predictor, model_id=model_id)


def reference_state(task_, truth):
    if any(row["feasible"] is True for row in truth.values()):
        return "FEASIBLE_EXISTS"
    if all(row["feasible"] is False for row in truth.values()):
        return "NONE_FEASIBLE"
    return "UNRESOLVED"


def judge(task_, commitment, reference):
    """A committed pick judged on reference quantities (bands applied):
    includes kind, full-bank reference resolution, best, regret and unit."""
    _verify_task_digest(task_)
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
        "task_digest": task_["task_digest"],
        "selected": pick,
        "best": best,
        "reference_state": state,
        "reference_resolved": resolved,
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
    decided = [
        o
        for o in outcomes
        if o["kind"] not in unresolved and o.get("reference_resolved", True)
    ]
    priced = [o["regret"] for o in decided if o["regret"] is not None]
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


def common_resolved_mask(question_ids, outcomes_by_model):
    """Compare models only on questions with resolved truth for every model.

    Missing or partial reference outcomes are explicitly reported for each
    model. A resolved-looking outcome without an explicit reference_resolved
    flag is fail-closed as unresolved.
    """
    ids = list(question_ids)
    if len(set(ids)) != len(ids) or not ids or not outcomes_by_model:
        raise TaskError("distinct question ids and model outcomes are required")
    expected = set(ids)
    for model, outcomes in outcomes_by_model.items():
        if not isinstance(outcomes, dict) or set(outcomes) - expected:
            raise TaskError(f"{model}: outcomes contain unregistered questions")
    for question in ids:
        identities = {
            outcomes[question].get("task_digest")
            for outcomes in outcomes_by_model.values()
            if question in outcomes
            and outcomes[question].get("task_digest") is not None
        }
        if len(identities) > 1:
            raise TaskError(
                f"{question}: compared models used different task identities"
            )
    included = [
        question
        for question in ids
        if all(
            outcomes_by_model[model].get(question, {}).get("reference_resolved") is True
            and outcomes_by_model[model][question].get("kind")
            not in ("SELECTED_UNRESOLVED", "ABSTENTION_UNRESOLVED")
            for model in outcomes_by_model
        )
    ]
    unresolved = {
        model: [
            question
            for question in ids
            if outcomes.get(question, {}).get("reference_resolved") is not True
            or outcomes.get(question, {}).get("kind")
            in ("SELECTED_UNRESOLVED", "ABSTENTION_UNRESOLVED")
        ]
        for model, outcomes in outcomes_by_model.items()
    }
    return {
        "included": included,
        "excluded": [question for question in ids if question not in included],
        "unresolved_by_model": unresolved,
        "measures_by_model": {
            model: measures([outcomes[question] for question in included])
            for model, outcomes in outcomes_by_model.items()
        },
    }
