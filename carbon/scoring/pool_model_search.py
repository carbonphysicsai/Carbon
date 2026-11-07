"""Model-driven search for the fixed-optimizer design-value proof (Exam Quality spec DV_FIXED_OPTIMIZER_PROOF, 5 Nov).

The proof asks, per version, whether a model that knows the out-of-range physics (P) steers OUR fixed optimizer to a
design the reference solver scores better than a TRAIN-only fit (F) does. This module is that optimizer: the D (a1)
driver's CMA-ES loop (`pool_solver_reference._cmaes_phase`, unchanged), with the solver call replaced by a MODEL call.

- `model_evaluator(predict, ...)` turns a fitted model into the driver's `solve(fixed, designs)` shape. `predict(rows)`
  takes model input rows (lists in `input_names` order) and returns one prediction per row: either the derived outputs
  (``{output: value}``) or, with `derive` given (a `pool_adapters.PoolAdapter`'s `derive`), a raw output row that
  `derive(inputs, raw)` turns into them. A prediction that is missing, non-finite or refused by `derive` is typed
  ``REFERENCE_DERIVE_REFUSED`` and ranks last; it is the MODEL's invalid prediction here, never a solver outcome.
  An exception from `predict` propagates (a setup error, not a search result).
- `model_search(problem, evaluator, ...)`: seeded CMA-ES, `population` x `generations` model calls (proof setting
  10 x 20 = 200), no line search, no surrogate, no infra retries. Feasibility is the MODEL's predictions against the
  target's limits (every margin >= 0); the optimizer sees only the model. Returns the incumbent after generations
  5 / 10 / 20 (`checkpoints`) and the final pick (the incumbent after the last generation).
- `solve_job(result, problem, input_names, design_names, model_label)`: the final pick as ONE solve job, a version-
  neutral record carrying the full model input row by name. Each version's runner maps it to its own shard format
  (DC: BT, mc-exam/TL: Motor + Cooling, TE2: RB); `job_writer` lets the caller do that in the same call.

Fixed optimizer: seed 0, start at the box centre, sigma0 0.3 of the unit box, population 10, 20 generations
(`proof_problem` builds a Problem with these). F and P run on the SAME Problem, so the only difference is the model.

Custody only (`host_class` must be a custody class): the box is the version's signed extended region, the predictions
and the pick's inputs are hidden-region values. Nothing here writes a file; the caller writes the job into custody.
Off by default: nothing calls this module unless a proof runner does. It changes no registered score.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from carbon.scoring.pool_solver_reference import (
    DERIVE_REFUSED,
    OK,
    DriverPolicy,
    Problem,
    SolvedPoint,
    _check_problem,
    _cmaes_phase,
    _key,
    _margins,
    _raw,
    _require,
    _require_custody,
    _unit,
)

PROOF_POPULATION = 10
PROOF_GENERATIONS = 20
PROOF_SEED = 0
PROOF_SIGMA0 = 0.3
PROOF_CHECKPOINTS = (5, 10, 20)
JOB_SCHEMA = "carbon.model_search_pick.v1"


def model_evaluator(predict, *, input_names, design_names, derive=None):
    """The driver's `solve(fixed, designs)` over a fitted model (see the module docstring)."""
    input_names, design_names = tuple(input_names), tuple(design_names)
    _require(
        len(set(input_names)) == len(input_names)
        and set(design_names) <= set(input_names),
        "design_names_must_be_model_inputs",
    )

    def solve(fixed, designs):
        rows = []
        for design in designs:
            values = {**fixed, **dict(zip(design_names, design, strict=True))}
            _require(
                set(values) == set(input_names),
                "fixed_and_design_must_complete_the_row",
            )
            rows.append([float(values[name]) for name in input_names])
        predictions = predict(rows)
        _require(
            predictions is not None and len(predictions) == len(rows),
            "model_returned_wrong_count",
        )
        out = []
        for row, prediction in zip(rows, predictions):
            outputs = prediction
            if derive is not None:
                outputs = derive(dict(zip(input_names, row)), prediction)
            if type(outputs) is not dict or not all(
                isinstance(v, (int, float)) and math.isfinite(v)
                for v in outputs.values()
            ):
                out.append({"status": DERIVE_REFUSED})
            else:
                out.append({"status": OK, "outputs": dict(outputs)})
        return out

    return solve


def proof_problem(*, target_id, fixed, outputs, objective, sense, limits, u, box):
    """A Problem with the proof's fixed optimizer settings: seed 0, start at the centre of `box`."""
    return Problem(
        target_id=target_id,
        fixed=dict(fixed),
        outputs=tuple(outputs),
        objective=objective,
        sense=sense,
        limits=tuple(limits),
        u=dict(u),
        box=tuple(tuple(b) for b in box),
        start=(0.5,) * len(box),
        seed=PROOF_SEED,
    )


@dataclass(frozen=True)
class Incumbent:
    generation: int
    index: int  # into ModelSearchResult.points
    design: tuple  # raw design
    predicted: dict | None  # the model's derived outputs
    model_feasible: bool  # every predicted margin >= 0


@dataclass(frozen=True)
class ModelSearchResult:
    target_id: str
    pick: Incumbent  # the incumbent after the last generation
    checkpoints: tuple  # Incumbent per requested generation
    points: tuple  # pool_solver_reference.SolvedPoint, in call order (phase "cmaes")
    counts: dict  # model calls by status
    settings: dict  # population, generations, sigma0, seed, start, host_class


def _feasible(point):
    return point.status == OK and all(m >= 0.0 for m in point.margins.values())


def _incumbent(problem, points, generation):
    """The best point so far: model-feasible by the objective (or the grader's value under a near-limit rule) first,
    else the least predicted violation, as the driver ranks."""
    index = min(range(len(points)), key=lambda i: (_key(problem, points[i]), i))
    point = points[index]
    return Incumbent(
        generation=generation,
        index=index,
        design=point.design,
        predicted=point.outputs,
        model_feasible=_feasible(point),
    )


def model_search(
    problem,
    evaluator,
    *,
    host_class,
    population=PROOF_POPULATION,
    generations=PROOF_GENERATIONS,
    sigma0=PROOF_SIGMA0,
    checkpoints=PROOF_CHECKPOINTS,
):
    """CMA-ES over the model (see the module docstring). `evaluator` is `model_evaluator(...)`."""
    _require_custody(host_class)
    _check_problem(problem)
    _require(
        type(population) is int
        and population >= 2
        and type(generations) is int
        and generations >= 1,
        "population_and_generations_invalid",
    )
    _require(isinstance(sigma0, (int, float)) and 0.0 < sigma0 <= 1.0, "sigma0_invalid")
    _require(
        all(type(g) is int and 1 <= g <= generations for g in checkpoints),
        "checkpoints_must_be_generations_run",
    )
    policy = DriverPolicy(
        budget=population * generations,
        population=population,
        sigma0=float(sigma0),
        line_search_points=0,
        line_search_span=0.0,
        infra_retries=0,
    )
    counts = {"solves": 0, "infra_attempts": 0, "by_status": {}}
    points = _cmaes_phase(problem, evaluator, policy, counts)
    _require(len(points) == population * generations, "search_did_not_run_its_budget")
    _require(counts["infra_attempts"] == 0, "model_evaluator_returned_failed_infra")
    marks = sorted(set(checkpoints) | {generations})
    found = {g: _incumbent(problem, points[: g * population], g) for g in marks}
    return ModelSearchResult(
        target_id=problem.target_id,
        pick=found[generations],
        checkpoints=tuple(found[g] for g in sorted(set(checkpoints))),
        points=tuple(points),
        counts={"model_calls": counts["solves"], "by_status": counts["by_status"]},
        settings={
            "population": population,
            "generations": generations,
            "sigma0": float(sigma0),
            "seed": problem.seed,
            "start": tuple(problem.start),
            "host_class": host_class,
        },
    )


def solve_job(
    result, problem, *, input_names, design_names, model_label, job_writer=None
):
    """The final pick as one solve job (custody material: it carries hidden-region inputs).

    The record is version-neutral: ``inputs`` is the full model input row by name (the target's fixed conditions plus
    the pick's design). With `job_writer`, returns ``job_writer(record)``: the version's own shard format.
    """
    _require(type(model_label) is str and model_label, "model_label_required")
    _require(result.target_id == problem.target_id, "result_is_for_another_target")
    design = dict(zip(design_names, result.pick.design, strict=True))
    values = {**problem.fixed, **design}
    _require(set(values) == set(input_names), "fixed_and_design_must_complete_the_row")
    _require(
        all(0.0 <= x <= 1.0 for x in _unit(problem, result.pick.design)),
        "pick_outside_the_box",
    )
    record = {
        "schema": JOB_SCHEMA,
        "target_id": problem.target_id,
        "model": model_label,
        "inputs": {name: float(values[name]) for name in input_names},
        "design": {name: float(v) for name, v in design.items()},
        "model_feasible": result.pick.model_feasible,
        "settings": {**result.settings, "start": list(result.settings["start"])},
    }
    return record if job_writer is None else job_writer(record)


# --- de_polish_v1: DE + limit-following polish (owner decision 7 Nov 13:15Z; spec GRADING_OPTIMIZER_SPEC_DE_POLISH.md) ---
#
# The grading optimizer for the new launch versions (a version's crown_d block names it; older versions keep
# `model_search`, nothing rescored). The logic is the design-optimum reference `de_polish_search.py` (sha 39c05c53),
# statement for statement; its constants are part of the optimizer's name (changing any = a new name). Budget B model
# calls (an owner value): (1) DE for floor(0.85 B) calls, population 8d on Halton points, rand/1/bin F 0.7 CR 0.9, one
# forced gene, out-of-box genes bounced toward the parent, greedy replacement when key <= parent's; (2) POLISH from the
# incumbent (model-feasible, limits present): up to 15 central-difference (h 1e-4) moves along the objective gradient
# projected on the most active limit's tangent, steps 0.05 / 0.02 / 0.008 / 0.003 / 0.001, each followed by one
# pull-back onto that limit, first strict improvement accepted; (3) COMPASS with the calls left, +-step per axis,
# halve on failure, 0.05 -> 1e-4. Pick = best by the driver's `_key` over every call, ties by call order. Host-
# deterministic: random.Random(seed), Halton, + - * / % abs and math.sqrt only; no numpy in any comparison path.

DE_NAME = "de_polish_v1"
DE_SHARE = 0.85
DE_F_WEIGHT, DE_CR = 0.7, 0.9
DE_POLISH_STEPS = (0.05, 0.02, 0.008, 0.003, 0.001)
DE_POLISH_ITERS, DE_FD_H = 15, 1e-4
DE_COMPASS_START, DE_COMPASS_MIN = 0.05, 1e-4
DE_PRIMES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
DE_CHECKPOINTS = (0.25, 0.5, 1.0)


class _DeDone(Exception):
    pass


def _halton(n, d, skip):
    out = []
    for i in range(skip + 1, skip + n + 1):
        row = []
        for p in DE_PRIMES[:d]:
            f, r, k = 1.0, 0.0, i
            while k > 0:
                f /= p
                r += f * (k % p)
                k //= p
            row.append(r)
        out.append(row)
    return out


class _DeCalls:
    """Batched model calls with a hard budget; every point kept in call order."""

    def __init__(self, problem, evaluator, budget):
        self.problem, self.evaluator, self.budget = problem, evaluator, budget
        self.points = []
        self.best = None  # (key, index)

    def left(self):
        return self.budget - len(self.points)

    def __call__(self, units):
        room = self.left()
        if room <= 0:
            raise _DeDone
        units = [[min(1.0, max(0.0, float(v))) for v in u] for u in units][:room]
        records = self.evaluator(
            self.problem.fixed, [list(_raw(self.problem, u)) for u in units]
        )
        _require(
            isinstance(records, list) and len(records) == len(units),
            "model_returned_wrong_count",
        )
        out = []
        for u, rec in zip(units, records):
            ok = rec.get("status") == OK
            p = SolvedPoint(
                design=tuple(_raw(self.problem, u)),
                phase="model",
                status=rec.get("status"),
                outputs=rec.get("outputs") if ok else None,
                margins=_margins(self.problem, rec["outputs"]) if ok else None,
                attempts=1,
            )
            self.points.append(p)
            k = _key(self.problem, p)
            if self.best is None or (k, len(self.points) - 1) < (
                self.best[0],
                self.best[1],
            ):
                self.best = (k, len(self.points) - 1)
            out.append((u, k, p))
        return out


def _de_phase(problem, calls, seed, cap):
    d = len(problem.box)
    rng = random.Random(seed)
    npop = 8 * d
    pop = _halton(npop, d, skip=3 + 389 * seed)
    res = calls(pop)
    pop, keys = [r[0] for r in res], [r[1] for r in res]
    while len(calls.points) + npop <= cap:
        trials = []
        for i in range(npop):
            a, b, c = rng.sample([j for j in range(npop) if j != i], 3)
            jr = rng.randrange(d)
            t = []
            for j in range(d):
                v = (
                    pop[a][j] + DE_F_WEIGHT * (pop[b][j] - pop[c][j])
                    if (rng.random() < DE_CR or j == jr)
                    else pop[i][j]
                )
                if v < 0.0:
                    v = pop[i][j] * rng.random()
                if v > 1.0:
                    v = pop[i][j] + (1.0 - pop[i][j]) * rng.random()
                t.append(v)
            trials.append(t)
        for i, (x, k, _p) in enumerate(calls(trials)):
            if k <= keys[i]:
                pop[i], keys[i] = x, k


def _unit_of(problem, point):
    return [(x - lo) / (hi - lo) for x, (lo, hi) in zip(point.design, problem.box)]


def _polish_phase(problem, calls):
    """Projected finite-difference move along the most active limit (see the block comment above)."""
    d = len(problem.box)
    sign = 1.0 if problem.sense == "max" else -1.0
    for _ in range(DE_POLISH_ITERS):
        k0, i0 = calls.best
        p0 = calls.points[i0]
        if k0[0] != 0 or not problem.limits:
            return
        x = _unit_of(problem, p0)
        pts = []
        for i in range(d):
            y1, y2 = list(x), list(x)
            y1[i], y2[i] = min(1.0, x[i] + DE_FD_H), max(0.0, x[i] - DE_FD_H)
            pts += [y1, y2]
        res = calls(pts)
        if len(res) < len(pts) or any(r[2].status != OK for r in res):
            return
        names = [problem.objective] + [lim.output for lim in problem.limits]
        g = {}
        for n in names:
            g[n] = [
                (res[2 * i][2].outputs[n] - res[2 * i + 1][2].outputs[n])
                / ((pts[2 * i][i] - pts[2 * i + 1][i]) or 1e-12)
                for i in range(d)
            ]
        gf = [sign * v for v in g[problem.objective]]
        ai = min(range(len(problem.limits)), key=lambda j: (p0.margins[j], j))
        act = problem.limits[ai]
        gc = g[act.output] if act.kind == "<=" else [-v for v in g[act.output]]
        cc = sum(v * v for v in gc) or 1e-30
        dot = sum(a * b for a, b in zip(gf, gc))
        proj = [a - (dot / cc) * b for a, b in zip(gf, gc)]
        nrm = math.sqrt(sum(v * v for v in proj)) or 1e-30
        moved = False
        for step in DE_POLISH_STEPS:
            y = [min(1.0, max(0.0, a + step * v / nrm)) for a, v in zip(x, proj)]
            ry = calls([y])[0][2]
            if ry.status != OK:
                continue
            m = ry.margins[ai]
            y = [min(1.0, max(0.0, a + m * v / cc)) for a, v in zip(y, gc)]
            before = calls.best
            calls([y])
            if calls.best != before:
                moved = True
                break
        if not moved:
            return


def _compass_phase(problem, calls):
    d = len(problem.box)
    step = DE_COMPASS_START
    while step >= DE_COMPASS_MIN:
        x = _unit_of(problem, calls.points[calls.best[1]])
        trial = []
        for i in range(d):
            for s in (step, -step):
                y = list(x)
                y[i] = min(1.0, max(0.0, y[i] + s))
                if y != x:
                    trial.append(y)
        before = calls.best
        calls(trial)
        if calls.best == before:
            step /= 2.0


def model_search_de(
    problem, evaluator, *, host_class, budget, checkpoints=DE_CHECKPOINTS
):
    """The de_polish_v1 search on a model (see the block comment above). `budget` = model calls (an owner value, at
    least one DE generation, 16d); `checkpoints` are budget FRACTIONS. Same result shape as `model_search`.
    """
    _require_custody(host_class)
    _check_problem(problem)
    _require(
        type(budget) is int and budget >= 16 * len(problem.box),
        "budget_too_small_for_one_de_generation",
    )
    _require(
        all(isinstance(c, float) and 0.0 < c <= 1.0 for c in checkpoints),
        "checkpoints_must_be_budget_fractions",
    )
    calls = _DeCalls(problem, evaluator, budget)
    marks = {}
    try:
        _de_phase(problem, calls, problem.seed, int(DE_SHARE * budget))
        _polish_phase(problem, calls)
        _compass_phase(problem, calls)
    except _DeDone:
        pass

    def inc_at(n):
        best = min(range(n), key=lambda i: (_key(problem, calls.points[i]), i))
        p = calls.points[best]
        return Incumbent(
            generation=n,
            index=best,
            design=p.design,
            predicted=p.outputs,
            model_feasible=_feasible(p),
        )

    for c in checkpoints:
        n = max(1, min(len(calls.points), int(c * budget)))
        marks[c] = inc_at(n)
    pick = inc_at(len(calls.points))
    by = {}
    for p in calls.points:
        by[p.status] = by.get(p.status, 0) + 1
    return ModelSearchResult(
        target_id=problem.target_id,
        pick=pick,
        checkpoints=tuple(marks[c] for c in checkpoints),
        points=tuple(calls.points),
        counts={"model_calls": len(calls.points), "by_status": by},
        settings={
            "optimizer": DE_NAME,
            "budget": budget,
            "seed": problem.seed,
            "host_class": host_class,
            "de_share": DE_SHARE,
            "F": DE_F_WEIGHT,
            "CR": DE_CR,
        },
    )
