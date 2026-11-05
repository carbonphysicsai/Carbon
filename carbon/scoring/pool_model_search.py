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
from dataclasses import dataclass

from carbon.scoring.pool_solver_reference import (
    DERIVE_REFUSED,
    OK,
    DriverPolicy,
    Problem,
    _check_problem,
    _cmaes_phase,
    _key,
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
