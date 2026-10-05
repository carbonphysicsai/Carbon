"""Track B: equal-cost design search against solvers (TRACK-B-HARNESS-01).

Challenge-neutral. A Challenge supplies a ``Problem`` (its registered finite
designs, its conditions with their groups, and its decision rule), its
predictors (the solver itself through a replayed or counted reference, its
analytical and learned models) and a reference for verification. The harness
answers the Test Lead's two questions (OWNER-GRAPHITE-TEST-WAVE-01 §5 as
refined on 2026-10-04) and never lets one cost view decide both:

- **Q1, alignment** (``alignment``): models at an equal search budget, the
  same method and query allowance, one-time costs excluded. The per-model
  decision quality feeds ``score_value``.
- **Q2, economic value** (``economic``): every arm, including the solver, at
  an equal total cost per decision B, one-time costs charged in full and
  amortised over a registered decision-count ladder N. An arm whose amortised
  one-time cost alone exceeds B is ``OVER_BUDGET_BEFORE_SEARCH`` at that N.
  The equal-query view is diagnostic, and the break-even N is computed.

Custody follows the motor and cooling studies: every arm writes an immutable,
digest-addressed commitment before verification exists, and verification
refuses to start until every commitment is on disk and unaltered. The solver
arm reaches the reference only through its own case-keyed cache during its
own search; a model arm never reaches it. Verification is charged to the
``VERIFICATION`` line, identically for every arm.

The decision rule is PB-INV: the design predicted feasible at every condition
with the lowest worst-case (largest) objective, ties by the lower design.
Representative and boundary-stress groups are reported separately in every
view; the registered contract (every condition) is reported as its own scope.

This module does not change, and is not bound by, the pinned modules
``methods.py``, ``experiment.py``, ``aggregate_methods.py``, ``campaign.py``
and ``reference_comparison.py``; it only calls them.

DEVELOPMENT only: no LIVE path, no score, gate or tolerance.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import cost, methods
from . import reference_comparison as rc

COMMITMENT_SCHEMA = "carbon.design-search.track-b-commitment.v1"
RESULT_SCHEMA = "carbon.design-search.track-b-result.v1"
MODE = "PB-INV"
GROUPS = ("REPRESENTATIVE", "BOUNDARY_STRESS")
CONTRACT_SCOPE = "CONTRACT_ALL_CONDITIONS"
SOLVER, MODEL = "SOLVER", "MODEL"
OVER_BUDGET = "OVER_BUDGET_BEFORE_SEARCH"
DEFAULT_LADDER = (1, 10, 100, 1000)


class TrackBError(ValueError):
    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def _digest(value):
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Design:
    design_id: str
    values: tuple


@dataclass(frozen=True)
class Condition:
    condition_id: str
    group: str
    values: tuple

    def __post_init__(self):
        if self.group not in GROUPS:
            raise TrackBError("unknown_condition_group", self.group)


@dataclass(frozen=True)
class Problem:
    """A Challenge's registered finite design decision."""

    challenge: str
    designs: tuple
    conditions: tuple
    #: predicted or reference quantities -> meets every constraint
    passes: Callable
    #: quantities -> the per-condition objective, lower is better
    objective: Callable
    #: where models infer and the harness measures CPU
    host_route: str

    def __post_init__(self):
        ids = [d.design_id for d in self.designs]
        values = [d.values for d in self.designs]
        if len(set(ids)) != len(ids) or len(set(values)) != len(values):
            raise TrackBError("designs_not_unique")
        cids = [c.condition_id for c in self.conditions]
        if len(set(cids)) != len(cids) or not self.conditions:
            raise TrackBError("conditions_not_unique")
        if values != sorted(values):
            raise TrackBError("designs_not_in_value_order")

    def point(self, design, condition):
        return (*design.values, *condition.values)

    def points(self):
        return {self.point(d, c): (d, c) for d in self.designs for c in self.conditions}


@dataclass(frozen=True)
class Case:
    """One reference case: its quantities (None when the reference failed)
    and what it cost to produce."""

    quantities: dict | None
    core_seconds: float
    route: str
    basis: str = "ALLOCATED_CPU_X_WALL"


class Reference:
    """A finite reference keyed by point: replayed records or imported
    counted evidence. It never solves anything itself."""

    def __init__(self, cases, *, evidence_class, source):
        self._cases = dict(cases)
        self.evidence_class = evidence_class
        self.source = source

    def case(self, point):
        if point not in self._cases:
            raise TrackBError("reference_case_missing", repr(point))
        return self._cases[point]


@dataclass(frozen=True)
class Predictor:
    """What an arm predicts with.

    A MODEL predicts through ``infer(points) -> [quantities | None]`` and is
    charged its measured inference CPU. A SOLVER predicts through
    ``reference`` and is charged each case's recorded cost on a cache miss.
    ``one_time`` lists ``(category, route, core_seconds, basis, note)`` costs
    paid once before any decision (training data, fitting).
    ``planning_core_seconds`` is the pre-declared per-point charge used to
    stop a search before it overspends; actual charges are recorded as they
    happen.
    """

    name: str
    kind: str
    planning_core_seconds: float
    planning_route: str
    infer: Callable | None = None
    reference: Reference | None = None
    one_time: tuple = ()

    def __post_init__(self):
        if self.kind not in (SOLVER, MODEL):
            raise TrackBError("unknown_predictor_kind", self.kind)
        if (self.kind == SOLVER) != (self.reference is not None):
            raise TrackBError("only_the_solver_reaches_the_reference", self.name)
        if (self.kind == MODEL) != (self.infer is not None):
            raise TrackBError("a_model_predicts_by_inference", self.name)
        if self.kind == SOLVER and self.one_time:
            raise TrackBError("the_solver_has_no_one_time_cost", self.name)
        for category, *_ in self.one_time:
            if category not in cost.ONE_TIME:
                raise TrackBError("one_time_category", category)


@dataclass(frozen=True)
class Arm:
    arm_id: str
    predictor: Predictor
    method: str
    parameters: dict = field(default_factory=dict)


# --------------------------------------------------------------------------
# Search


def fixed_grid(view, oracle):
    """Every design at every condition, in design order, while affordable."""

    return _exhaustive(view, oracle, list(view.designs))


def random_subset(view, oracle, *, seed):
    """Designs in a seeded random order, each at every condition, while
    affordable; the seed is declared before the run."""

    order = list(view.designs)
    random.Random(seed).shuffle(order)
    return _exhaustive(view, oracle, order)


def _exhaustive(view, oracle, order):
    best = None
    width = len(view.conditions)
    for design in order:
        if oracle.used + width > oracle.budget:
            break
        rows = oracle.query([(*design, *c) for c in view.conditions])
        if all(view.passes(q) for q in rows):
            key = (max(view.objective(q) for q in rows), design)
            best = key if best is None or key < best else best
    return [] if best is None else [view.select_design(best[1], best[0])]


#: Track B's search methods: the two neutral exhaustive searches here and
#: the registered methods in ``methods.py``, run unchanged.
LOCAL_METHODS = {
    "fixed_grid": (fixed_grid, set()),
    "random_subset": (random_subset, {"seed"}),
}


def run_method(name, parameters, view, oracle):
    if name in LOCAL_METHODS:
        function, names = LOCAL_METHODS[name]
        if type(parameters) is not dict or set(parameters) != names:
            raise TrackBError("parameters_not_exactly_the_methods", name)
        if "seed" in names and type(parameters["seed"]) is not int:
            raise TrackBError("seed_must_be_an_integer")
        return function(view, oracle, **parameters)
    return methods.run(name, parameters, view, oracle)


def _view(problem):
    def passes(q):
        return q is not None and bool(problem.passes(q))

    def objective(q):
        return math.inf if q is None else float(problem.objective(q))

    return methods.View(
        mode=MODE,
        designs=tuple(d.values for d in problem.designs),
        conditions=tuple(c.values for c in problem.conditions),
        verification_budget=1,
        passes=passes,
        objective=objective,
        margin=lambda q: 0.0,
        select_design=lambda design, worst: {"design": design, "worst": worst},
        select_point=lambda design, condition, q: None,
    )


class _Oracle:
    """One arm's query channel, charging every query to the ledger.

    ``allowance`` is ``("points", n)`` (an equal query budget) or
    ``("cost", remaining)`` in the study unit (an equal cost budget). Under a
    cost allowance ``budget`` is the points already used plus the points the
    remaining allowance buys at the predictor's planning charge.
    """

    def __init__(self, problem, arm, ledger, allowance, plan_unit_cost, clock):
        self.problem = problem
        self.arm = arm
        self.ledger = ledger
        self.kind, self.allowance = allowance
        self.plan_unit_cost = plan_unit_cost
        self.clock = clock
        self.points = problem.points()
        self.cache = {}
        self.log = []

    @property
    def used(self):
        return len(self.log)

    @property
    def budget(self):
        if self.kind == "points":
            return self.allowance
        if self.plan_unit_cost <= 0:
            return self.used + len(self.points)
        return self.used + max(
            0, math.floor(self.allowance / self.plan_unit_cost + 1e-9)
        )

    def query(self, points):
        points = [tuple(p) for p in points]
        seen = {entry["point"] for entry in self.log}
        repeated = len(set(points)) != len(points) or bool(seen & set(points))
        # A model may not repeat a point (as the motor and cooling oracles
        # rule). The solver may: a repeat is a cache hit, charged its lookup
        # and still counted as an evaluation (§5).
        if repeated and self.arm.predictor.kind == MODEL:
            raise TrackBError("duplicate_query", self.arm.arm_id)
        if any(p not in self.points for p in points):
            raise TrackBError("undeclared_query_point", self.arm.arm_id)
        if self.used + len(points) > self.budget:
            raise TrackBError("query_exceeds_allowance", self.arm.arm_id)
        predictor = self.arm.predictor
        if predictor.kind == MODEL:
            start = self.clock()
            results = list(predictor.infer(points))
            spent = max(0.0, self.clock() - start)
            if len(results) != len(points):
                raise TrackBError("inference_count_mismatch", predictor.name)
            self.ledger.add(
                cost.Charge(
                    self.arm.arm_id,
                    "inference",
                    self.problem.host_route,
                    spent,
                    "MEASURED_CPU",
                    f"{len(points)} points",
                )
            )
        else:
            results = []
            for point in points:
                if point in self.cache:
                    start = self.clock()
                    results.append(self.cache[point])
                    self.ledger.add(
                        cost.Charge(
                            self.arm.arm_id,
                            "cache_lookup",
                            self.problem.host_route,
                            max(0.0, self.clock() - start),
                            "MEASURED_CPU",
                        )
                    )
                    continue
                case = predictor.reference.case(point)
                self.ledger.add(
                    cost.Charge(
                        self.arm.arm_id,
                        "in_search_solve",
                        case.route,
                        case.core_seconds,
                        case.basis,
                    )
                )
                self.cache[point] = case.quantities
                results.append(case.quantities)
        if self.kind == "cost":
            self.allowance -= self.plan_unit_cost * len(points)
        for point, q in zip(points, results):
            design, condition = self.points[point]
            self.log.append(
                {
                    "point": point,
                    "design_id": design.design_id,
                    "condition_id": condition.condition_id,
                    "predicted_pass": q is not None and bool(self.problem.passes(q)),
                    "predicted_objective": (
                        None if q is None else float(self.problem.objective(q))
                    ),
                }
            )
        return results


# --------------------------------------------------------------------------
# Custody


def _write_once(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, indent=2, sort_keys=True) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(text)


def _commit(problem, arm, selection, oracle, directory, label):
    by_values = {d.values: d for d in problem.designs}
    design = None if selection is None else by_values[tuple(selection["design"])]
    body = {
        "schema": COMMITMENT_SCHEMA,
        "challenge": problem.challenge,
        "label": label,
        "arm_id": arm.arm_id,
        "predictor": arm.predictor.name,
        "predictor_kind": arm.predictor.kind,
        "method": arm.method,
        "parameters": arm.parameters,
        "status": "ABSTAIN" if design is None else "PROPOSAL",
        "design_id": None if design is None else design.design_id,
        "predicted_worst_objective": None if design is None else selection["worst"],
        "queries": [
            {k: v for k, v in entry.items() if k != "point"} for entry in oracle.log
        ],
    }
    document = {**body, "commitment_digest": _digest(body)}
    _write_once(Path(directory) / f"{label}--{arm.arm_id}.commitment.json", document)
    return document


def _load_commitments(directory, expected):
    """Every expected commitment, read back from disk and checked."""

    loaded = {}
    for key, document in expected.items():
        path = (
            Path(directory)
            / f"{document['label']}--{document['arm_id']}.commitment.json"
        )
        if not path.is_file():
            raise TrackBError("commitment_missing_before_verification", key)
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        body = {k: v for k, v in on_disk.items() if k != "commitment_digest"}
        if on_disk != document or on_disk["commitment_digest"] != _digest(body):
            raise TrackBError("commitment_altered", key)
        loaded[key] = on_disk
    return loaded


# --------------------------------------------------------------------------
# Verification and metrics


def _reference_rows(problem, reference, ledger):
    """The full finite set at the reference, charged to VERIFICATION once."""

    rows = {}
    for design in problem.designs:
        for condition in problem.conditions:
            case = reference.case(problem.point(design, condition))
            ledger.add(
                cost.Charge(
                    cost.VERIFICATION,
                    "verification",
                    case.route,
                    case.core_seconds,
                    case.basis,
                )
            )
            q = case.quantities
            verdict = (
                "REFERENCE_UNAVAILABLE"
                if q is None
                else ("FEASIBLE" if problem.passes(q) else "INFEASIBLE")
            )
            rows[(design.design_id, condition.condition_id)] = {
                "design_id": design.design_id,
                "condition_id": condition.condition_id,
                "group": condition.group,
                "verdict": verdict,
                "objective": None if q is None else float(problem.objective(q)),
            }
    return rows


def _scopes(problem):
    scopes = {CONTRACT_SCOPE: [c.condition_id for c in problem.conditions]}
    for group in GROUPS:
        ids = [c.condition_id for c in problem.conditions if c.group == group]
        if ids:
            scopes[group] = ids
    return scopes


def _comparators(problem, rows):
    out = {}
    for scope, ids in _scopes(problem).items():
        out[scope] = rc.finite_comparator(
            designs=[
                {"design_id": d.design_id, "values": list(d.values)}
                for d in problem.designs
            ],
            rows=[rows[(d.design_id, c)] for d in problem.designs for c in ids],
            conditions_per_design=len(ids),
            objective=lambda evidence: max(row["objective"] for row in evidence),
            objective_field="worst_objective",
            definition=f"best reference-feasible design over {scope}",
            limitations="registered finite design set only",
            accounting={"conditions": ids},
        )
    return out


def _arm_metrics(problem, commitment, rows, comparators):
    out = {}
    for scope, ids in _scopes(problem).items():
        comparator = comparators[scope]
        if commitment["status"] == "ABSTAIN":
            outcome, selected = "ABSTAIN", None
        else:
            evidence = [rows[(commitment["design_id"], c)] for c in ids]
            outcome = rc.classify_condition_evidence(evidence)
            selected = (
                max(row["objective"] for row in evidence)
                if outcome == "CONFIRMED_FEASIBLE"
                else None
            )
        regret = rc.regret(
            proposal_outcome=outcome,
            selected_objective=selected,
            comparator=comparator,
            objective_field="worst_objective",
            value_field="regret",
            selected_field="selected_worst_objective",
            comparator_field="comparator_worst_objective",
            difference_field="difference_from_best_observed",
        )
        in_scope = [q for q in commitment["queries"] if q["condition_id"] in ids]
        point_false_accepts = sum(
            q["predicted_pass"]
            and rows[(q["design_id"], q["condition_id"])]["verdict"] == "INFEASIBLE"
            for q in in_scope
        )
        feasible_ids = {
            item["design_id"]
            for item in comparator["designs"]
            if item["proposal_outcome"] == "CONFIRMED_FEASIBLE"
        }
        predicted_fail = {q["design_id"] for q in in_scope if not q["predicted_pass"]}
        out[scope] = {
            "proposal_outcome": outcome,
            "false_feasible": commitment["status"] == "PROPOSAL"
            and outcome == "CONFIRMED_INFEASIBLE",
            "point_false_accepts": point_false_accepts,
            "missed_feasible_designs": sorted(feasible_ids & predicted_fail),
            "abstained_while_feasible_exists": commitment["status"] == "ABSTAIN"
            and bool(feasible_ids),
            "unresolved": outcome == "UNRESOLVED",
            "regret": regret,
            "correct_decision": regret["status"] == "DEFINED_FINITE_SET"
            and regret["regret"] <= 0,
        }
    return out


# --------------------------------------------------------------------------
# Runs


def _planned_cost(predictor, unit, rates, conversions):
    planned = cost.Charge(
        "plan",
        "inference",
        predictor.planning_route,
        predictor.planning_core_seconds,
        "MEASURED_CPU",
    )
    return cost.amount([planned], unit, rates=rates, conversions=conversions)


def _one_time_charges(arm):
    return [
        cost.Charge(arm.arm_id, category, route, core_seconds, basis, note)
        for category, route, core_seconds, basis, note in arm.predictor.one_time
    ]


def _search(problem, arm, ledger, allowance, unit, rates, conversions, clock):
    plan = _planned_cost(arm.predictor, unit, rates, conversions)
    oracle = _Oracle(problem, arm, ledger, allowance, plan, clock)
    start = clock()
    selection = run_method(arm.method, arm.parameters, _view(problem), oracle)
    search_cpu = max(0.0, clock() - start)
    return (selection[0] if selection else None), oracle, search_cpu


def _check_arms(arms):
    ids = [arm.arm_id for arm in arms]
    if len(set(ids)) != len(ids) or not ids:
        raise TrackBError("arm_ids_not_unique")
    for arm_id in ids:
        if "--" in arm_id or "/" in arm_id:
            raise TrackBError("arm_id_characters", arm_id)


def alignment(
    problem,
    models,
    *,
    method,
    parameters,
    query_allowance,
    reference,
    directory,
    unit,
    rates=(),
    conversions=(),
    clock=time.process_time,
):
    """Q1: every model with the same method and query allowance, one-time
    costs excluded. Returns per-model decision quality for ``score_value``."""

    arms = [Arm(m.name, m, method, dict(parameters)) for m in models]
    _check_arms(arms)
    if any(arm.predictor.kind != MODEL for arm in arms):
        raise TrackBError("alignment_compares_models_only")
    ledger = cost.Ledger()
    label = "alignment"
    commitments = {}
    for arm in arms:
        selection, oracle, _ = _search(
            problem,
            arm,
            ledger,
            ("points", query_allowance),
            unit,
            rates,
            conversions,
            clock,
        )
        commitments[arm.arm_id] = _commit(
            problem, arm, selection, oracle, directory, label
        )
    commitments = _load_commitments(directory, commitments)
    rows = _reference_rows(problem, reference, ledger)
    comparators = _comparators(problem, rows)
    results = {}
    for arm in arms:
        commitment = commitments[arm.arm_id]
        results[arm.arm_id] = {
            "commitment_digest": commitment["commitment_digest"],
            "status": commitment["status"],
            "design_id": commitment["design_id"],
            "queries_used": len(commitment["queries"]),
            "per_decision_cost": cost.price(
                ledger.charges(arm.arm_id), unit, rates=rates, conversions=conversions
            ),
            "scopes": _arm_metrics(problem, commitment, rows, comparators),
        }
    return {
        "schema": RESULT_SCHEMA,
        "question": "Q1_ALIGNMENT",
        "challenge": problem.challenge,
        "rule": (
            "equal search budget: same method and query allowance; one-time "
            "training and data costs excluded"
        ),
        "method": method,
        "parameters": parameters,
        "query_allowance": query_allowance,
        "reference": {
            "evidence_class": reference.evidence_class,
            "source": reference.source,
        },
        "arms": results,
        "comparators": _comparator_summary(comparators),
        "verification_cost": cost.price(
            ledger.charges(cost.VERIFICATION),
            unit,
            rates=rates,
            conversions=conversions,
        ),
        "ledger": ledger.as_list(),
    }


def economic(
    problem,
    arms,
    *,
    budget,
    unit,
    reference,
    directory,
    ladder=DEFAULT_LADDER,
    diagnostic_query_allowance=None,
    rates=(),
    conversions=(),
    clock=time.process_time,
):
    """Q2: every arm at an equal total cost per decision ``budget`` (in
    ``unit``), one-time costs amortised over each decision count N."""

    _check_arms(arms)
    solvers = [arm for arm in arms if arm.predictor.kind == SOLVER]
    if len(solvers) != 1:
        raise TrackBError("economic_view_needs_exactly_one_solver_arm")
    if not ladder or any(type(n) is not int or n < 1 for n in ladder):
        raise TrackBError("decision_count_ladder")
    if not (type(budget) in (int, float) and budget > 0 and math.isfinite(budget)):
        raise TrackBError("decision_budget")
    ledger = cost.Ledger()
    one_time = {}
    for arm in arms:
        charges = _one_time_charges(arm)
        for charge in charges:
            ledger.add(charge)
        one_time[arm.arm_id] = cost.price(
            charges, unit, rates=rates, conversions=conversions
        )
    expected = {}
    plans = {}
    for n in ladder:
        label = f"economic-N{n}"
        for arm in arms:
            priced = one_time[arm.arm_id]
            key = (n, arm.arm_id)
            if priced["value"] is None:
                plans[key] = {"status": priced["status"]}
                continue
            amortised = priced["value"] / n
            if amortised > budget:
                plans[key] = {"status": OVER_BUDGET, "amortised_one_time": amortised}
                continue
            run_arm = Arm(f"{arm.arm_id}", arm.predictor, arm.method, arm.parameters)
            arm_ledger = cost.Ledger()
            selection, oracle, _ = _search(
                problem,
                run_arm,
                arm_ledger,
                ("cost", budget - amortised),
                unit,
                rates,
                conversions,
                clock,
            )
            expected[key] = _commit(
                problem, run_arm, selection, oracle, directory, label
            )
            plans[key] = {
                "status": "SEARCHED",
                "amortised_one_time": amortised,
                "charges": arm_ledger.charges(),
            }
    diagnostic = {}
    if diagnostic_query_allowance is not None:
        for arm in arms:
            key = ("diagnostic", arm.arm_id)
            arm_ledger = cost.Ledger()
            selection, oracle, _ = _search(
                problem,
                arm,
                arm_ledger,
                ("points", diagnostic_query_allowance),
                unit,
                rates,
                conversions,
                clock,
            )
            expected[key] = _commit(
                problem, arm, selection, oracle, directory, "diagnostic-equal-query"
            )
            diagnostic[arm.arm_id] = arm_ledger.charges()
    commitments = _load_commitments(directory, expected)
    rows = _reference_rows(problem, reference, ledger)
    comparators = _comparators(problem, rows)

    def outcome(key, charges, amortised):
        commitment = commitments[key]
        per_decision = cost.price(charges, unit, rates=rates, conversions=conversions)
        metrics = _arm_metrics(problem, commitment, rows, comparators)
        total = (
            None if per_decision["value"] is None else per_decision["value"] + amortised
        )
        return {
            "commitment_digest": commitment["commitment_digest"],
            "status": commitment["status"],
            "design_id": commitment["design_id"],
            "queries_used": len(commitment["queries"]),
            "per_decision_search_cost": per_decision,
            "amortised_one_time_cost": amortised,
            "total_cost_per_decision": total,
            # Stopping uses the planning charge, so a search whose actual
            # charges ran above B is flagged rather than hidden.
            "actual_cost_exceeds_budget": (
                None if total is None or key[0] == "diagnostic" else total > budget
            ),
            "cost_to_correct_decision": (
                total if metrics[CONTRACT_SCOPE]["correct_decision"] else None
            ),
            "scopes": metrics,
        }

    views = {}
    for n in ladder:
        row = {}
        for arm in arms:
            key = (n, arm.arm_id)
            plan = plans[key]
            if plan["status"] != "SEARCHED":
                row[arm.arm_id] = plan
                continue
            row[arm.arm_id] = outcome(key, plan["charges"], plan["amortised_one_time"])
        views[str(n)] = row
    diagnostic_view = {
        arm_id: outcome(("diagnostic", arm_id), charges, 0.0)
        for arm_id, charges in diagnostic.items()
    }
    return {
        "schema": RESULT_SCHEMA,
        "question": "Q2_ECONOMIC_VALUE",
        "challenge": problem.challenge,
        "rule": (
            "equal total cost per decision, one-time costs charged in full and "
            "amortised over the decision count N; verification charged to no arm"
        ),
        "unit": unit.as_dict(),
        "decision_budget": budget,
        "ladder": list(ladder),
        "reference": {
            "evidence_class": reference.evidence_class,
            "source": reference.source,
        },
        "one_time_cost": one_time,
        "views": {
            "equal_cost_deciding": views,
            "equal_query_diagnostic": {
                "query_allowance": diagnostic_query_allowance,
                "arms": diagnostic_view,
            },
            "amortised_break_even": break_even(views, one_time, solvers[0].arm_id),
        },
        "comparators": _comparator_summary(comparators),
        "verification_cost": cost.price(
            ledger.charges(cost.VERIFICATION),
            unit,
            rates=rates,
            conversions=conversions,
        ),
        "ledger": ledger.as_list(),
    }


def break_even(views, one_time, solver_id):
    """Per model arm: the decision count after which its one-time cost plus
    per-decision search cost undercuts the solver arm's per-decision cost.

    Per-decision costs come from the largest N at which both arms searched.
    The count is computed, never assumed; ``NEVER`` when the model's
    per-decision cost is not below the solver's. Decision quality at that N is
    reported beside it, because a cheaper wrong decision is no break-even.
    """

    out = {}
    counts = sorted((int(n) for n in views), reverse=True)
    arm_ids = sorted({a for row in views.values() for a in row} - {solver_id})
    for arm_id in arm_ids:
        found = None
        for n in counts:
            mine, solver = views[str(n)][arm_id], views[str(n)][solver_id]
            if mine.get("status") in ("PROPOSAL", "ABSTAIN") and solver.get(
                "status"
            ) in ("PROPOSAL", "ABSTAIN"):
                found = (n, mine, solver)
                break
        fixed = one_time[arm_id]["value"]
        if found is None or fixed is None:
            out[arm_id] = {"status": "NOT_COMPUTABLE", "break_even_decisions": None}
            continue
        n, mine, solver = found
        model_pd = mine["per_decision_search_cost"]["value"]
        solver_pd = solver["per_decision_search_cost"]["value"]
        if model_pd is None or solver_pd is None:
            out[arm_id] = {"status": "NOT_COMPUTABLE", "break_even_decisions": None}
            continue
        if solver_pd <= model_pd:
            status, count = "NEVER", None
        else:
            status = "COMPUTED"
            count = max(1, math.ceil(fixed / (solver_pd - model_pd) - 1e-12))
        out[arm_id] = {
            "status": status,
            "break_even_decisions": count,
            "one_time_cost": fixed,
            "model_per_decision_cost": model_pd,
            "solver_per_decision_cost": solver_pd,
            "costs_from_decision_count": n,
            "model_correct_decision": mine["scopes"][CONTRACT_SCOPE][
                "correct_decision"
            ],
            "solver_correct_decision": solver["scopes"][CONTRACT_SCOPE][
                "correct_decision"
            ],
        }
    return out


def _comparator_summary(comparators):
    return {
        scope: {
            "status": item["status"],
            "coverage": item["coverage"],
            "best": (
                None
                if item["best_reference_feasible_in_complete_set"] is None
                else {
                    "design_id": item["best_reference_feasible_in_complete_set"][
                        "design_id"
                    ],
                    "worst_objective": item["best_reference_feasible_in_complete_set"][
                        "worst_objective"
                    ],
                }
            ),
        }
        for scope, item in comparators.items()
    }


def decision_value(scope_metrics):
    """A sortable decision-quality key for ``score_value`` (lower is better).

    The order is a declared working policy: a correct-or-defined regret
    (class 0, by regret) beats abstaining (1), which beats an unsafe,
    reference-infeasible selection (2). Unresolved evidence ranks nothing
    (None). The Test Lead may supersede this order.
    """

    regret = scope_metrics["regret"]
    if regret["status"] == "DEFINED_FINITE_SET":
        return (0, float(regret["regret"]))
    if scope_metrics["proposal_outcome"] == "ABSTAIN":
        return (1, 0.0)
    if scope_metrics["proposal_outcome"] == "CONFIRMED_INFEASIBLE":
        return (2, 0.0)
    return None
