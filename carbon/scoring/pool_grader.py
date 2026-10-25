"""Pool grader: the design half as optimisation over a pre-solved pool, with no solver at grade time.

Basis: OWNER-INVERSE-DESIGN-PROOF-01 and OWNER-HEADROOM-REGIONS-01; spec
`codex-queue/reports/POOL_GRADER_AND_PROOF_SUITE_SPEC_20261024.md` (Validator). One module for every
Challenge: a Challenge plugs in only data (its design box, outputs, limits, objective, U, pool and the
true outputs of each pool design) and a `predict` callable. Nothing here names a Challenge.

How one target is graded (spec section 2):
1. Carbon's seeded CMA-ES (`pool_cmaes`) searches the target's normalised design box. Each proposal
   snaps to the nearest unqueried queryable pool point. The model predicts that point's outputs (one
   batched call per generation). Ranking is feasibility-first on the PREDICTED outputs, then by the
   predicted objective: the exact, constant-free form of "predicted objective with a penalty for
   predicted limit violations".
2. The final pick is the best predicted-feasible point among those queried. Its truth is looked up.
3. D(target) = 0 if the pick is truly infeasible (or there is no predicted-feasible pick), else
   q * h, with q the closeness to the reference optimum (clipped to [0, 1], the median feasible
   objective scoring 0) and h = exp(-e / s_h) the honesty of the model's own prediction at its pick.
4. D(set) is the mean over the set's targets. No simulator runs.

Every constant the spec marks OWNER (the query budget B, the honesty scale s_h, the A and A_gen
scales, how A_gen enters A, the C rule) is a required argument with no default. The CMA-ES initial
step size and the honesty error reduction (max or rms over outputs) are also explicit: the spec does
not fix them.

Disclosure: only `SetGrade.public()` (the set's D and closed reason codes) may leave custody; picks,
per-target values, pool points and queries stay in custody.

Reference failure is not candidate failure: a pool that cannot give a non-degenerate reference is
refused at build time (`PoolRefused`), never scored as a candidate's loss. A malformed prediction is
the candidate's (closed code, D = 0); an exception from `predict` (a crashed sandbox) propagates, so
the caller can mark the grade FAILED_INFRA.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import dataclass, replace

from carbon.scoring.design_fidelity import benefit
from carbon.scoring.pool_cmaes import CmaEs

REASONS = (
    "graded",
    "no_predicted_feasible_pick",
    "pick_infeasible",
    "prediction_invalid",
)


def _is_relative(value):
    return (
        type(value) is dict
        and set(value) == {"relative"}
        and _finite(value["relative"])
        and value["relative"] > 0
    )


def _valid_u(value):
    return _is_relative(value) or (_finite(value) and value >= 0)


def u_value(u, true_value):
    """A U at one row: a number as it is, or {"relative": r} as r x |true_value|."""
    return u["relative"] * abs(true_value) if type(u) is dict else u


class PoolRefused(ValueError):
    """The pool or its policy cannot give a sound grade: the Challenge's material, not a candidate's failure."""


def _require(condition, reason):
    if not condition:
        raise PoolRefused(reason)


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


@dataclass(frozen=True)
class Limit:
    output: str
    kind: (
        str  # "<=" (the output must not exceed bound) or ">=" (must not fall below it)
    )
    bound: float

    def margin(self, value):
        """Positive when the limit is met, by how much."""
        return self.bound - value if self.kind == "<=" else value - self.bound


@dataclass(frozen=True)
class OptimizerPolicy:
    """The query budget B per target (OWNER), the CMA-ES initial step in the unit box, and the population
    (None = the tutorial's 4 + floor(3 ln n))."""

    budget: int
    sigma0: float
    population: int | None


@dataclass(frozen=True)
class HonestyPolicy:
    """s_h (OWNER) and how the per-output U-normalised errors reduce to one number: "max" or "rms"."""

    scale: float
    reduction: str


def _check_policies(optimizer, honesty):
    _require(
        type(optimizer.budget) is int and optimizer.budget >= 1,
        "budget_must_be_a_positive_int",
    )
    _require(
        _finite(optimizer.sigma0) and optimizer.sigma0 > 0, "sigma0_must_be_positive"
    )
    _require(
        optimizer.population is None
        or (type(optimizer.population) is int and optimizer.population >= 2),
        "population_must_be_none_or_at_least_2",
    )
    _require(
        _finite(honesty.scale) and honesty.scale > 0, "honesty_scale_must_be_positive"
    )
    _require(
        honesty.reduction in ("max", "rms"), "honesty_reduction_must_be_max_or_rms"
    )


@dataclass(frozen=True)
class TargetSpec:
    """One sealed optimisation problem with its pre-solved pool. Build it with `build_target`."""

    def u_at(self, index, name):
        """The U of output `name` at pool row `index`: the number, or r x |that row's true value|."""
        return u_value(self.u[name], self.truths[index][name])

    target_id: str
    conditions: dict
    outputs: tuple
    objective: str
    sign: (
        float  # +1 maximise, -1 minimise: sign * objective is always "bigger is better"
    )
    limits: tuple
    u: dict
    box: tuple
    designs: tuple  # raw design vectors, one per kept pool point
    norm: tuple  # the same designs in the unit box
    truths: tuple  # true outputs per point
    feasible: tuple  # truly feasible (every margin >= 0; kept points are clear of U)
    queryable: tuple  # indices the optimiser may query (the A_gen slice excluded)
    agen: tuple  # indices reserved for accuracy only
    reference: int  # best feasible queryable point
    s_ref: float
    s_low: float  # median feasible queryable objective, in sign * objective
    start: tuple
    seed: int
    excluded: int  # pool points dropped at build time for a margin within U of a limit
    digest: str
    public: bool  # a PUBLIC practice pool: its per-target values may be shown; a sealed pool's never are


def _digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def build_target(
    *,
    target_id,
    conditions,
    outputs,
    objective,
    sense,
    limits,
    u,
    box,
    designs,
    truths,
    agen,
    start,
    seed,
    public=False,
):
    """Validate a target's sealed material and derive its reference.

    `agen` is the set of ORIGINAL pool indices reserved for accuracy only (never queried).
    `start` is the optimiser's private starting point in the unit box; `seed` its private seed.
    Pool points whose true margin is within U of any limit are excluded (spec section 1), so every
    kept point is clearly feasible or clearly infeasible."""
    _require(type(target_id) is str and target_id, "target_id_required")
    _require(type(conditions) is dict, "conditions_must_be_a_dict")
    outputs = tuple(outputs)
    _require(
        len(outputs) == len(set(outputs)) and outputs,
        "outputs_must_be_unique_and_non_empty",
    )
    _require(objective in outputs, "objective_must_be_an_output")
    _require(sense in ("max", "min"), "sense_must_be_max_or_min")
    limits = tuple(limits)
    _require(
        all(
            isinstance(l, Limit)
            and l.kind in ("<=", ">=")
            and l.output in outputs
            and _finite(l.bound)
            for l in limits
        ),
        "limits_must_name_outputs_with_a_kind_and_a_finite_bound",
    )
    _require(set(u) == set(outputs), "u_must_cover_exactly_the_outputs")
    # A U is a number >= 0, or {"relative": r} (r > 0): r times the ABSOLUTE true value of that output in that
    # pool row, as the exam applies it (e.g. a hydraulic power, r = 0.03). A relative U is never a scalar.
    # U = 0 marks an output Carbon computes exactly (an analytic quantity such as an energy or a mass formula),
    # never predicted by the model: it is held to equality, not to a tolerance, and does not enter the honesty
    # scale. At least one output must carry a real U or there is nothing for honesty to measure.
    _require(
        all(_valid_u(v) for v in u.values()),
        "u_must_be_non_negative_and_finite_or_relative",
    )
    _require(
        any(_is_relative(v) or v > 0 for v in u.values()),
        "u_needs_one_predicted_output",
    )
    box = tuple((float(lo), float(hi)) for lo, hi in box)
    _require(
        box
        and all(math.isfinite(lo) and math.isfinite(hi) and hi > lo for lo, hi in box),
        "box_must_be_finite_with_hi_above_lo",
    )
    _require(
        len(designs) == len(truths) and len(designs) >= 2,
        "pool_needs_matching_designs_and_truths",
    )
    for design, truth in zip(designs, truths):
        _require(
            len(design) == len(box) and all(_finite(x) for x in design),
            "design_must_match_the_box_and_be_finite",
        )
        _require(
            type(truth) is dict
            and set(truth) == set(outputs)
            and all(_finite(v) for v in truth.values()),
            "truth_must_give_every_output_finite",
        )
    _require(type(seed) is int, "seed_must_be_an_int")
    _require(
        len(start) == len(box) and all(_finite(x) and 0.0 <= x <= 1.0 for x in start),
        "start_must_be_in_the_unit_box",
    )
    agen = set(agen)
    _require(
        all(type(i) is int and 0 <= i < len(designs) for i in agen),
        "agen_index_out_of_range",
    )
    keep, excluded = [], 0
    for index, truth in enumerate(truths):
        if any(
            abs(limit.margin(truth[limit.output]))
            <= u_value(u[limit.output], truth[limit.output])
            for limit in limits
        ):
            excluded += 1
            continue
        keep.append(index)
    kept_designs = tuple(tuple(float(x) for x in designs[i]) for i in keep)
    kept_truths = tuple({k: float(v) for k, v in truths[i].items()} for i in keep)
    kept_agen = tuple(n for n, i in enumerate(keep) if i in agen)
    queryable = tuple(n for n, i in enumerate(keep) if i not in agen)
    norm = tuple(
        tuple((x - lo) / (hi - lo) for x, (lo, hi) in zip(design, box))
        for design in kept_designs
    )
    feasible = tuple(
        all(limit.margin(truth[limit.output]) >= 0.0 for limit in limits)
        for truth in kept_truths
    )
    sign = 1.0 if sense == "max" else -1.0
    scores = {n: sign * kept_truths[n][objective] for n in queryable if feasible[n]}
    _require(
        len(scores) >= 2, "degenerate_reference_needs_two_feasible_queryable_points"
    )
    reference = min(scores, key=lambda n: (-scores[n], n))
    s_ref, s_low = scores[reference], statistics.median(scores.values())
    _require(s_ref > s_low, "degenerate_reference_best_feasible_must_beat_the_median")
    body = {
        "target_id": target_id,
        "conditions": conditions,
        "outputs": list(outputs),
        "objective": objective,
        "sense": sense,
        "limits": [[l.output, l.kind, l.bound] for l in limits],
        "u": u,
        "box": [list(b) for b in box],
        "designs": [list(d) for d in kept_designs],
        "truths": list(kept_truths),
        "agen": list(kept_agen),
        "start": list(start),
        "seed": seed,
        "public": public,  # visibility is part of the identity: a sealed pool cannot be relabelled public
    }
    _require(type(public) is bool, "public_must_be_a_bool")
    return TargetSpec(
        target_id=target_id,
        conditions=conditions,
        outputs=outputs,
        objective=objective,
        sign=sign,
        limits=limits,
        u=dict(u),
        box=box,
        designs=kept_designs,
        norm=norm,
        truths=kept_truths,
        feasible=feasible,
        queryable=queryable,
        agen=kept_agen,
        reference=reference,
        s_ref=s_ref,
        s_low=s_low,
        start=tuple(float(x) for x in start),
        seed=seed,
        excluded=excluded,
        digest=_digest(body),
        public=public,
    )


@dataclass(frozen=True)
class TargetGrade:
    """Custody-only: never disclosed outside `SetGrade.public()`."""

    target_id: str
    digest: str
    d: float
    q: float
    h: float
    e: float
    feasible: bool
    pick: int | None
    queries: int
    reason: str
    reached_reference: bool


def _valid_prediction(prediction, outputs):
    return (
        type(prediction) is dict
        and set(prediction) == set(outputs)
        and all(_finite(v) for v in prediction.values())
    )


def _nearest(point, norm, candidates, taken):
    best, best_distance = None, None
    for index in candidates:
        if index in taken:
            continue
        distance = sum((a - b) ** 2 for a, b in zip(point, norm[index]))
        if best is None or distance < best_distance:
            best, best_distance = index, distance
    return best


def grade_target(spec, predict, optimizer, honesty):
    """Grade one target. `predict(conditions, designs)` returns one dict of outputs per design, in order."""
    _check_policies(optimizer, honesty)
    taken = set()
    predictions = {}
    es = CmaEs(spec.start, optimizer.sigma0, spec.seed, optimizer.population)

    def refused(code):
        return TargetGrade(
            spec.target_id,
            spec.digest,
            0.0,
            0.0,
            0.0,
            math.inf,
            False,
            None,
            len(predictions),
            code,
            False,
        )

    def key(index):
        prediction = predictions[index]
        violation = exact = 0.0
        for limit in spec.limits:
            margin = limit.margin(prediction[limit.output])
            if margin < 0.0:
                scale = spec.u_at(index, limit.output)
                if scale > 0.0:
                    violation += -margin / scale
                else:
                    exact += (
                        -margin
                    )  # an exactly computed quantity: its raw excess ranks first
        loss = -spec.sign * prediction[spec.objective]
        if violation == 0.0 and exact == 0.0:
            return (0, loss)
        return (1, exact, violation, loss)

    while len(predictions) < optimizer.budget and len(taken) < len(spec.queryable):
        samples = es.ask()
        chosen = []
        for sample in samples:
            if len(predictions) + len(chosen) >= optimizer.budget:
                break
            point = [min(1.0, max(0.0, x)) for x in sample]
            index = _nearest(point, spec.norm, spec.queryable, taken)
            if index is None:
                break
            taken.add(index)
            chosen.append(index)
        if not chosen:
            break
        batch = predict(spec.conditions, [list(spec.designs[i]) for i in chosen])
        if type(batch) is not list or len(batch) != len(chosen):
            return refused("prediction_invalid")
        for index, prediction in zip(chosen, batch):
            if not _valid_prediction(prediction, spec.outputs):
                return refused("prediction_invalid")
            predictions[index] = {k: float(v) for k, v in prediction.items()}
        if len(chosen) < len(samples):
            break  # the budget or the pool ended mid-generation: nothing left to adapt to
        es.tell([key(i) for i in chosen])
    feasible_predicted = [i for i in predictions if key(i)[0] == 0]
    if not feasible_predicted:
        return refused("no_predicted_feasible_pick")
    pick = min(feasible_predicted, key=lambda i: (key(i), i))
    queries = len(predictions)
    if not spec.feasible[pick]:
        return TargetGrade(
            spec.target_id,
            spec.digest,
            0.0,
            0.0,
            0.0,
            _error(spec, pick, predictions[pick], honesty),
            False,
            pick,
            queries,
            "pick_infeasible",
            False,
        )
    s_pick = spec.sign * spec.truths[pick][spec.objective]
    q = min(1.0, max(0.0, (s_pick - spec.s_low) / (spec.s_ref - spec.s_low)))
    e = _error(spec, pick, predictions[pick], honesty)
    h = math.exp(-e / honesty.scale)
    return TargetGrade(
        spec.target_id,
        spec.digest,
        q * h,
        q,
        h,
        e,
        True,
        pick,
        queries,
        "graded",
        s_pick >= spec.s_ref,
    )


def _error(spec, index, prediction, honesty):
    ratios = []
    for k in spec.outputs:
        difference = abs(prediction[k] - spec.truths[index][k])
        scale = spec.u_at(index, k)
        if scale > 0.0:
            ratios.append(difference / scale)
        elif not math.isclose(
            prediction[k], spec.truths[index][k], rel_tol=1e-9, abs_tol=1e-12
        ):
            return (
                math.inf
            )  # an exact output that does not match is a wiring fault: honesty 0
    if honesty.reduction == "max":
        return max(ratios)
    return math.sqrt(sum(r * r for r in ratios) / len(ratios))


@dataclass(frozen=True)
class SetGrade:
    d: float
    targets: tuple  # custody only

    def public(self):
        """All that may leave custody: the set's D and the closed reason codes seen. Never a pick, a
        per-target value, a pool point or a query."""
        return {
            "d": self.d,
            "reasons": sorted({t.reason for t in self.targets} - {"graded"}),
        }


def grade_set(specs, predict, optimizer, honesty):
    _require(len(specs) >= 1, "set_needs_targets")
    _require(
        len({s.target_id for s in specs}) == len(specs), "target_ids_must_be_unique"
    )
    grades = tuple(grade_target(spec, predict, optimizer, honesty) for spec in specs)
    return SetGrade(statistics.fmean(g.d for g in grades), grades)


def agen_accuracy(specs, predict, scales):
    """A_gen: accuracy on the reserved slice, atom form benefit(|error| / scale) = 1 / (1 + loss), the common
    benefit of `design_fidelity`, averaged over outputs, points and targets. `scales` is {output: scale} and
    required (OWNER). None when no target has a slice. The slice is never queried by the optimiser.
    """
    values = []
    for spec in specs:
        if not spec.agen:
            continue
        _require(
            set(scales) >= set(spec.outputs)
            and all(_finite(scales[k]) and scales[k] > 0 for k in spec.outputs),
            "agen_scales_must_cover_the_outputs",
        )
        batch = predict(spec.conditions, [list(spec.designs[i]) for i in spec.agen])
        _require(
            type(batch) is list and len(batch) == len(spec.agen),
            "agen_prediction_invalid",
        )
        atoms = []
        for index, prediction in zip(spec.agen, batch):
            _require(
                _valid_prediction(prediction, spec.outputs), "agen_prediction_invalid"
            )
            atoms += [
                benefit(abs(prediction[k] - spec.truths[index][k]) / scales[k])
                for k in spec.outputs
            ]
        values.append(statistics.fmean(atoms))
    return statistics.fmean(values) if values else None


def combine_a(a, a_gen, rule):
    """How A_gen enters A (OWNER): {"kind": "min"}, {"kind": "mean"} or {"kind": "weighted", "weight": w}."""
    if a_gen is None:
        return a
    kind = rule.get("kind")
    if kind == "min":
        return min(a, a_gen)
    if kind == "mean":
        return 0.5 * (a + a_gen)
    if kind == "weighted":
        w = rule.get("weight")
        _require(_finite(w) and 0.0 <= w <= 1.0, "weight_must_be_in_0_1")
        return (1.0 - w) * a + w * a_gen
    raise PoolRefused("a_gen_rule_must_be_min_mean_or_weighted")


def total(a, d, c, c_rule):
    """TOP = 0.5 A + 0.5 D with C as the safety floor (OWNER picks how): {"kind": "min"} takes D = min(D, C);
    {"kind": "gate", "floor": f} gives 0 when C < f. Mandatory gates are applied by the caller before this.
    """
    kind = c_rule.get("kind")
    if kind == "min":
        d = min(d, c)
    elif kind == "gate":
        _require(_finite(c_rule.get("floor")), "floor_must_be_finite")
        if c < c_rule["floor"]:
            return 0.0
    else:
        raise PoolRefused("c_rule_must_be_min_or_gate")
    return 0.5 * a + 0.5 * d


POOL_SCHEMA = "carbon.pool.v1"
PRACTICE_SCHEMA = "carbon.pool-grade.practice.v1"


def dump_pool(spec):
    """A target's pool as a JSON-ready document (layout `carbon.pool.v1`). `digest` is the identity to pin: the
    sha256 of the canonical body, so a pool's exact content is its identity."""
    return {
        "schema": POOL_SCHEMA,
        "public": spec.public,
        "digest": spec.digest,
        "target_id": spec.target_id,
        "conditions": spec.conditions,
        "outputs": list(spec.outputs),
        "objective": spec.objective,
        "sense": "max" if spec.sign > 0 else "min",
        "limits": [[l.output, l.kind, l.bound] for l in spec.limits],
        "u": spec.u,
        "box": [list(b) for b in spec.box],
        "designs": [list(d) for d in spec.designs],
        "truths": list(spec.truths),
        "agen": list(spec.agen),
        "start": list(spec.start),
        "seed": spec.seed,
        "excluded": spec.excluded,
    }


def load_pool(document):
    """Rebuild a target from `dump_pool`'s document, refusing one whose digest does not match its content."""
    _require(
        type(document) is dict and document.get("schema") == POOL_SCHEMA,
        "pool_schema_unknown",
    )
    spec = build_target(
        target_id=document["target_id"],
        conditions=document["conditions"],
        outputs=document["outputs"],
        objective=document["objective"],
        sense=document["sense"],
        limits=[Limit(*row) for row in document["limits"]],
        u=document["u"],
        box=document["box"],
        designs=document["designs"],
        truths=document["truths"],
        agen=document["agen"],
        start=document["start"],
        seed=document["seed"],
        public=document["public"],
    )
    _require(
        spec.digest == document["digest"] and spec.excluded == 0,
        "pool_digest_does_not_match_its_content",
    )
    return replace(spec, excluded=document["excluded"])


def practice_report(
    specs,
    predict,
    optimizer,
    honesty,
    *,
    a,
    c,
    a_rule,
    agen_scales,
    c_rule,
    gates=(),
    minimums=None,
):
    """The practice result for a PUBLIC pool: the legs, the total, the gates and every target's values.

    `a` and `c` are the plugin's legs on the practice cases; A_gen and D_opt come from this module. Refuses any
    pool not marked public, so a sealed target's per-target values cannot be produced here. `gates` is the list
    of {"code", "passed"} the caller's mandatory gates give; any failed gate gives a total of 0. `minimums` is
    passed through as given (OWNER-PRACTICE-SHOWS-MINIMUMS-01 names what a miner sees).
    """
    _require(all(s.public for s in specs), "pool_not_public")
    grade = grade_set(specs, predict, optimizer, honesty)
    a_gen = agen_accuracy(specs, predict, agen_scales)
    a_total = combine_a(a, a_gen, a_rule)
    gated_out = any(not g["passed"] for g in gates)
    top = 0.0 if gated_out else total(a_total, grade.d, c, c_rule)
    return {
        "schema": PRACTICE_SCHEMA,
        "pool_digests": [s.digest for s in specs],
        "legs": {
            "A": a,
            "A_gen": a_gen,
            "A_combined": a_total,
            "D_opt": grade.d,
            "C": c,
        },
        "total": top,
        "gates": [dict(g) for g in gates],
        "minimums": minimums,
        "targets": [
            {
                "target_id": t.target_id,
                "d": t.d,
                "closeness": t.q,
                "honesty": t.h,
                "error_in_u": None if math.isinf(t.e) else t.e,
                "feasible": t.feasible,
                "queries": t.queries,
                "reached_reference": t.reached_reference,
                "reason": t.reason,
            }
            for t in grade.targets
        ],
    }
