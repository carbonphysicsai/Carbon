"""THE PACK-TIME SOLVER-IN-THE-LOOP REFERENCE (D option a1), against a cheap analytic stand-in solver.

Claims: the driver is off unless the pack spec turns it on, and then every owner value is required (no default); the
seeded CMA-ES on the solver plus the line search along the active limit finds the constrained optimum that sits ON the
limit, never worse than a pre-solved pool's best; the solve budget is exact; the run is deterministic; reference
failures, refused derives and infrastructure failures are typed and counted, never added to the pool, and an unresolved
infrastructure failure gives no reference; the extended pool feeds `build_target`; the public summary carries counts only.
The stand-in is a test fixture with made-up numbers: no Challenge's values.
"""

from __future__ import annotations

import math
import random

import pytest

from carbon.scoring import pool_solver_reference as psr
from carbon.scoring.pool_grader import Limit, build_target

HOST = "custody2"
SPEC = {
    "solver_reference": {
        "enabled": True,
        "budget": 60,
        "population": 6,
        "sigma0": 0.3,
        "line_search_points": 8,
        "line_search_span": 0.1,
        "infra_retries": 1,
    }
}
OPTIMUM = 1.0  # max x0 + x1 subject to x0^2 + x1^2 <= 0.5, at (0.5, 0.5)


def _problem(seed=11, bound=0.5, u_g=0.01):
    return psr.Problem(
        target_id="t-analytic",
        fixed={"c": 1.0},
        outputs=("f", "g"),
        objective="f",
        sense="max",
        limits=(Limit("g", "<=", bound),),
        u={"f": 0.0, "g": u_g},
        box=((0.0, 1.0), (0.0, 1.0)),
        start=(0.2, 0.2),
        seed=seed,
    )


class StandIn:
    """An analytic 'solver': f = x0 + x1, g = x0^2 + x1^2. Optional typed failures by region or call."""

    def __init__(self, refuse_above=None, infra_calls=(), infra_always=None):
        self.calls, self.designs = 0, []
        self.refuse_above, self.infra_calls = refuse_above, set(infra_calls)
        self.infra_always = infra_always

    def __call__(self, fixed, designs):
        assert fixed == {"c": 1.0}
        self.calls += 1
        out = []
        for x0, x1 in designs:
            self.designs.append((x0, x1))
            if (
                self.infra_always is not None and self.infra_always(x0, x1)
            ) or self.calls in self.infra_calls:
                out.append({"status": "FAILED_INFRA"})
            elif self.refuse_above is not None and x0 > self.refuse_above:
                out.append({"status": "REFERENCE_SOLVER_FAILED"})
            else:
                out.append(
                    {"status": "OK", "outputs": {"f": x0 + x1, "g": x0 * x0 + x1 * x1}}
                )
        return out


def _policy(**changes):
    block = dict(SPEC["solver_reference"], **changes)
    return psr.policy_from_spec({"solver_reference": block})


@pytest.mark.parametrize(
    "spec",
    [
        {},
        {"solver_reference": {}},
        {"solver_reference": {"enabled": False}},
        {"solver_reference": {"enabled": "true"}},
        None,
    ],
)
def test_off_unless_the_pack_spec_turns_it_on(spec):
    solver = StandIn()
    assert psr.run_pack(spec, [_problem()], solver, host_class=HOST) is None
    assert solver.calls == 0


@pytest.mark.parametrize("field", psr._POLICY_FIELDS)
def test_every_owner_value_is_required(field):
    for missing in (None, "HUMAN_INPUT"):
        block = dict(SPEC["solver_reference"], **{field: missing})
        with pytest.raises(psr.SolverReferenceRefused, match="human_input_required"):
            psr.policy_from_spec({"solver_reference": block})
    block = {k: v for k, v in SPEC["solver_reference"].items() if k != field}
    with pytest.raises(psr.SolverReferenceRefused, match="human_input_required"):
        psr.policy_from_spec({"solver_reference": block})


@pytest.mark.parametrize(
    "changes",
    [
        {"budget": 0},
        {"population": 1},
        {"sigma0": 0},
        {"line_search_span": -1.0},
        {"infra_retries": -1},
        {"budget": 6.0},
        {"surprise": 1},
    ],
)
def test_invalid_owner_values_refuse(changes):
    with pytest.raises(psr.SolverReferenceRefused):
        _policy(**changes)


def test_the_solver_optimum_reaches_the_constrained_optimum_on_the_limit():
    solver = StandIn()
    (result,) = psr.run_pack(SPEC, [_problem()], solver, host_class=HOST)
    assert result.status == psr.TARGET_OK
    best = result.points[result.reference]
    assert best.status == "OK" and best.margins[0] >= 0.0
    assert best.outputs["f"] > OPTIMUM - 0.03
    assert (
        result.active_limit == 0 and best.margins[0] < 0.05
    )  # on (near) the active limit


def _pool(seed=5, size=100):
    rng = random.Random(seed)
    designs = [[rng.random(), rng.random()] for _ in range(size)]
    return designs, [{"f": a + b, "g": a * a + b * b} for a, b in designs]


def test_the_pack_reference_is_never_worse_than_the_pre_solved_pool():
    """Strict: the extended pool's reference (pool + solver points) is at least the pool's own."""
    from dataclasses import replace

    designs, truths = _pool()
    pool_best = max(t["f"] for t in truths if t["g"] <= 0.5)
    beaten = 0
    for seed in range(12):
        problem = _problem(seed=seed)
        problem = replace(problem, start=psr.pool_start(problem, designs, truths))
        (result,) = psr.run_pack(SPEC, [problem], StandIn(), host_class=HOST)
        _, ext, _, _ = psr.extend_pool(designs, truths, result, problem)
        assert max(t["f"] for t in ext if t["g"] <= 0.5) >= pool_best
        beaten += result.points[result.reference].outputs["f"] > pool_best
    # Measured on this stand-in (not a guarantee): the warm-started solver alone beats the pool's best on most seeds.
    assert beaten >= 9, beaten


def test_the_line_search_lands_feasible_points_on_the_active_limit():
    near = 0
    for seed in range(12):
        (result,) = psr.run_pack(
            SPEC, [_problem(seed=seed)], StandIn(), host_class=HOST
        )
        line = [p for p in result.points if p.phase == "line_search"]
        assert result.counts["line_search"] == "run"
        assert 1 <= len(line) <= SPEC["solver_reference"]["line_search_points"]
        assert len({p.design for p in line}) == len(line)
        near += any(0.0 <= p.margins[0] < 0.01 for p in line)
        best = result.points[result.reference]
        cmaes_best = max(
            p.outputs["f"]
            for p in result.points
            if p.phase == "cmaes" and p.margins[0] >= 0.0
        )
        assert best.outputs["f"] >= cmaes_best  # strict: the line search only adds
    assert near >= 10, near  # measured on this stand-in


def test_the_budget_is_exact_and_the_run_is_deterministic():
    solver_a, solver_b = StandIn(), StandIn()
    (a,) = psr.run_pack(SPEC, [_problem()], solver_a, host_class=HOST)
    (b,) = psr.run_pack(SPEC, [_problem()], solver_b, host_class=HOST)
    assert sum(p.phase == "cmaes" for p in a.points) == 60
    line = sum(p.phase == "line_search" for p in a.points)
    assert a.counts["solves"] == 60 + line == len(solver_a.designs) and line <= 8
    assert a.points == b.points and a.reference == b.reference
    (c,) = psr.run_pack(SPEC, [_problem(seed=12)], StandIn(), host_class=HOST)
    assert c.points != a.points
    # A budget that ends mid-generation stops there.
    spec = {
        "solver_reference": dict(
            SPEC["solver_reference"], budget=10, line_search_points=0
        )
    }
    (d,) = psr.run_pack(spec, [_problem()], StandIn(), host_class=HOST)
    assert len(d.points) == 10 and d.counts["line_search"] == "not_run"


def test_reference_failures_are_typed_counted_and_never_pooled():
    (result,) = psr.run_pack(
        SPEC, [_problem()], StandIn(refuse_above=0.6), host_class=HOST
    )
    refused = [p for p in result.points if p.status == "REFERENCE_SOLVER_FAILED"]
    assert refused and result.counts["by_status"]["REFERENCE_SOLVER_FAILED"] == len(
        refused
    )
    assert result.status == psr.TARGET_OK
    assert result.points[result.reference].design[0] <= 0.6
    designs, _truths, added, _ = psr.extend_pool([], [], result, _problem())
    assert len(added) == sum(p.status == "OK" for p in result.points) == len(designs)
    assert all(d[0] <= 0.6 for d in designs)


def test_an_infrastructure_failure_is_retried_then_typed():
    solver = StandIn(infra_calls={2})
    (result,) = psr.run_pack(SPEC, [_problem()], solver, host_class=HOST)
    assert result.status == psr.TARGET_OK
    assert result.counts["infra_attempts"] == SPEC["solver_reference"]["population"]
    assert result.counts["solves"] == len(result.points) + 6
    assert all(p.status != "FAILED_INFRA" for p in result.points)
    assert any(p.attempts == 2 for p in result.points)
    # Infrastructure that never answers: no reference, never a scientific verdict.
    stuck = StandIn(infra_always=lambda x0, x1: x0 > 0.5)
    (result,) = psr.run_pack(SPEC, [_problem()], stuck, host_class=HOST)
    assert result.status == psr.TARGET_INFRA and result.reference is None
    assert result.counts["by_status"]["FAILED_INFRA"] > 0
    # ...and an incomplete target adds nothing to the pool (review finding 2).
    with pytest.raises(psr.SolverReferenceRefused, match="result_not_ok"):
        psr.extend_pool([], [], result, _problem())


def test_no_feasible_point_is_the_reference_s_failure():
    (result,) = psr.run_pack(SPEC, [_problem(bound=-1.0)], StandIn(), host_class=HOST)
    assert result.status == psr.TARGET_NO_FEASIBLE and result.reference is None
    assert result.counts["line_search"] == "not_run"


def test_the_adapter_solver_types_a_refused_derive():
    class Adapter:
        def model_row(self, fixed, design):
            return [fixed["c"], *design]

        def derive_row(self, row, raw):
            if raw is None or raw[0] > 0.9:
                return None  # the Challenge's own validity gate refuses this raw row
            return {"f": raw[0] + raw[1], "g": raw[0] ** 2 + raw[1] ** 2}

    def run_rows(rows):
        return [{"status": "OK", "raw": [row[1], row[2]]} for row in rows]

    solve = psr.adapter_solver(Adapter(), run_rows)
    out = solve({"c": 1.0}, [[0.95, 0.1], [0.2, 0.3]])
    assert out[0] == {"status": psr.DERIVE_REFUSED}
    assert out[1]["status"] == "OK" and math.isclose(out[1]["outputs"]["f"], 0.5)
    (result,) = psr.run_pack(SPEC, [_problem()], solve, host_class=HOST)
    assert result.status == psr.TARGET_OK


def test_the_extended_pool_feeds_build_target():
    rng = random.Random(3)
    designs = [[rng.random(), rng.random()] for _ in range(40)]
    truths = [{"f": a + b, "g": a * a + b * b} for a, b in designs]
    tight = _problem(u_g=1e-6)
    (result,) = psr.run_pack(SPEC, [tight], StandIn(), host_class=HOST)
    extended, ext_truths, added, _ = psr.extend_pool(designs, truths, result, tight)

    def build(ds, ts):
        return build_target(
            target_id="t-analytic",
            conditions={"fixed": {"c": 1.0}},
            outputs=("f", "g"),
            objective="f",
            sense="max",
            limits=[Limit("g", "<=", 0.5)],
            u={"f": 0.0, "g": 1e-6},
            box=((0.0, 1.0), (0.0, 1.0)),
            designs=ds,
            truths=ts,
            agen=(),
            start=(0.5, 0.5),
            seed=1,
        )

    before, after = build(designs, truths), build(extended, ext_truths)
    assert after.s_ref > before.s_ref
    assert after.origin[after.reference] in added


def test_the_public_summary_carries_counts_only():
    results = psr.run_pack(
        SPEC, [_problem(), _problem(bound=-1.0)], StandIn(), host_class=HOST
    )
    summary = psr.public_summary(results)
    assert summary["targets"] == 2
    assert summary["by_target_status"] == {psr.TARGET_NO_FEASIBLE: 1, psr.TARGET_OK: 1}

    def leaves(value):
        if isinstance(value, dict):
            for v in value.values():
                yield from leaves(v)
        else:
            yield value

    assert all(type(v) is int for v in leaves(summary))


def test_a1_needs_a2_today_s_grader_drops_the_on_limit_optimum():
    """At a realistic U the solver's on-limit points fall within U and today's build_target drops them: extend_pool
    says how many, so a pack never assumes the solver optimum became the reference (review finding 1).
    """
    problem = _problem(u_g=0.01)
    (result,) = psr.run_pack(SPEC, [problem], StandIn(), host_class=HOST)
    designs, truths = _pool()
    extended, ext_truths, _added, within = psr.extend_pool(
        designs, truths, result, problem
    )
    assert within >= 1
    target = build_target(
        target_id="t-analytic",
        conditions={"fixed": {"c": 1.0}},
        outputs=("f", "g"),
        objective="f",
        sense="max",
        limits=[Limit("g", "<=", 0.5)],
        u={"f": 0.0, "g": 0.01},
        box=((0.0, 1.0), (0.0, 1.0)),
        designs=extended,
        truths=ext_truths,
        agen=(),
        start=(0.5, 0.5),
        seed=1,
    )
    solver_best = result.points[result.reference]
    assert abs(solver_best.margins[0]) <= 0.01  # on the limit, within U
    assert (
        target.s_ref < solver_best.outputs["f"]
    )  # ...so the current grader cannot use it


@pytest.mark.parametrize(
    "status", ["solver crashed at x=0.41", "CANDIDATE_FAILED", "ok", "REFERENCE_"]
)
def test_only_closed_statuses_are_accepted(status):
    def solve(fixed, designs):
        return [{"status": status} for _ in designs]

    with pytest.raises(psr.SolverReferenceRefused, match="solve_status_not_closed"):
        psr.run_pack(SPEC, [_problem()], solve, host_class=HOST)


def test_numpy_outputs_are_numbers_and_a_wrong_output_set_is_carbon_s_error():
    np = pytest.importorskip("numpy")

    def numpy_solve(fixed, designs):
        return [
            {
                "status": "OK",
                "outputs": {"f": np.float64(a + b), "g": np.float64(a * a + b * b)},
            }
            for a, b in designs
        ]

    (result,) = psr.run_pack(SPEC, [_problem()], numpy_solve, host_class=HOST)
    assert result.status == psr.TARGET_OK
    assert "REFERENCE_DERIVE_REFUSED" not in result.counts["by_status"]

    def extra_key(fixed, designs):
        return [
            {"status": "OK", "outputs": {"f": 1.0, "g": 0.1, "h": 0.0}} for _ in designs
        ]

    with pytest.raises(psr.SolverReferenceRefused, match="derive_outputs_do_not_match"):
        psr.run_pack(SPEC, [_problem()], extra_key, host_class=HOST)


def test_an_exact_limit_still_guides_the_search_back_to_feasibility():
    """U = 0 ranks the raw excess (as the grader does), not an all-equal infinity (review finding 5)."""
    from dataclasses import replace

    corner = replace(_problem(u_g=0.0), start=(0.95, 0.95))
    (exact,) = psr.run_pack(SPEC, [corner], StandIn(), host_class=HOST)
    assert exact.status == psr.TARGET_OK
    assert exact.points[exact.reference].outputs["f"] > OPTIMUM - 0.03


def test_one_dimension_walks_only_to_the_limit_point():
    problem = psr.Problem(
        target_id="t-1d",
        fixed={"c": 1.0},
        outputs=("f", "g"),
        objective="f",
        sense="max",
        limits=(Limit("g", "<=", 0.25),),
        u={"f": 0.0, "g": 0.001},
        box=((0.0, 1.0),),
        start=(0.2,),
        seed=3,
    )

    def solve(fixed, designs):
        return [{"status": "OK", "outputs": {"f": x, "g": x * x}} for (x,) in designs]

    (result,) = psr.run_pack(SPEC, [problem], solve, host_class=HOST)
    line = [p for p in result.points if p.phase == "line_search"]
    assert len({round(p.design[0], 9) for p in line}) == len(line)
    assert result.points[result.reference].outputs["f"] > 0.49


@pytest.mark.parametrize("host", ["lium", "targon", "runpod", "Custody2", "", None, 0])
def test_a_rented_or_unknown_host_refuses_before_the_first_solve(host):
    """Validator must-fix: the trajectory traces the hidden optimum, so only custody hosts run it."""
    calls = []

    def solve(fixed, designs):
        calls.append(designs)
        return StandIn()(fixed, designs)

    with pytest.raises(psr.SolverReferenceRefused, match="host_not_custody"):
        psr.run_pack(SPEC, [_problem()], solve, host_class=host)
    policy = psr.policy_from_spec(SPEC)
    with pytest.raises(psr.SolverReferenceRefused, match="host_not_custody"):
        psr.run_target(_problem(), solve, policy, host_class=host)
    assert calls == []


@pytest.mark.parametrize("host", sorted(psr.CUSTODY_HOST_CLASSES))
def test_every_custody_host_runs(host):
    (result,) = psr.run_pack(SPEC, [_problem()], StandIn(), host_class=host)
    assert result.status == psr.TARGET_OK


def test_the_host_class_has_no_default():
    with pytest.raises(TypeError):
        psr.run_pack(SPEC, [_problem()], StandIn())


RAMP = {"kind": "credit_ramp", "shape": "linear"}


def test_under_the_near_limit_rule_the_driver_searches_the_grader_s_value():
    """a2 in main: the on-limit optimum earns credit 0, so the driver ranks by credit x gain (pool_grader.credit). With
    the pool's own zero, the solver points raise the GRADER's reference value (v_ref) over the pre-solved pool's.
    """
    from dataclasses import replace

    from carbon.scoring.pool_grader import credit as grader_credit

    def u_of(name):
        return 0.05 if name == "g" else 0.0

    def target_of(designs, truths):
        return build_target(
            target_id="t-analytic",
            conditions={"fixed": {"c": 1.0}},
            outputs=("f", "g"),
            objective="f",
            sense="max",
            limits=[Limit("g", "<=", 0.5)],
            u={"f": 0.0, "g": 0.05},
            box=((0.0, 1.0), (0.0, 1.0)),
            designs=designs,
            truths=truths,
            agen=(),
            start=(0.5, 0.5),
            seed=1,
            near_limit=RAMP,
        )

    designs, truths = _pool()
    before = target_of(designs, truths)
    base = _problem(u_g=0.05)
    (plain,) = psr.run_pack(SPEC, [base], StandIn(), host_class=HOST)
    on_limit = plain.points[plain.reference].outputs
    assert (
        grader_credit(base.limits, on_limit, u_of) < 0.5
    )  # the raw optimum is worth little under the rule

    problem = replace(base, near_limit=RAMP, s_low=before.s_low)
    (result,) = psr.run_pack(SPEC, [problem], StandIn(), host_class=HOST)
    assert result.status == psr.TARGET_OK

    def value(out):
        return grader_credit(problem.limits, out, u_of) * max(
            0.0, out["f"] - before.s_low
        )

    best = result.points[result.reference].outputs
    assert value(best) == max(
        value(p.outputs) for p in result.points if p.status == "OK"
    )
    assert value(best) > value(on_limit)
    extended, ext_truths, _, _ = psr.extend_pool(designs, truths, result, problem)
    after = target_of(extended, ext_truths)
    assert len(after.designs) == len(extended)  # nothing dropped under the rule
    assert after.v_ref > before.v_ref


@pytest.mark.parametrize(
    "near_limit, s_low",
    [
        (RAMP, None),
        (None, 0.5),
        ({"kind": "credit_ramp", "shape": "cubic"}, 0.5),
        (RAMP, float("nan")),
    ],
)
def test_near_limit_and_its_zero_go_together(near_limit, s_low):
    from dataclasses import replace

    with pytest.raises(psr.SolverReferenceRefused, match="near_limit_and_s_low"):
        psr.run_pack(
            SPEC,
            [replace(_problem(), near_limit=near_limit, s_low=s_low)],
            StandIn(),
            host_class=HOST,
        )
