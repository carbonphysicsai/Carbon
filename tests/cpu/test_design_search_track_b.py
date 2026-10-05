"""Track B harness (TRACK-B-HARNESS-01) on a synthetic toy Challenge.

No solver runs and nothing is spent: the reference is a fixed table, the
clock is injected, and every figure here is synthetic.
"""

from __future__ import annotations

import itertools
import json
import random

import pytest

from carbon.battery.value import decision as battery_decision
from carbon.battery.value import divergence as battery_divergence
from carbon.design_search import cost, score_value, track_b

HOST = "toy-host"
SOLVE_CORE_S = 100.0
UNIT = cost.Unit("core_seconds", HOST)


def _quantities(design, condition):
    a, b, c = design
    load, stress = condition
    objective = 10 - 3 * a - 2 * b - c + load
    # Design (1, 1, 1) is feasible at the representative conditions but not
    # at the boundary one; (0, *, *) designs are infeasible everywhere.
    ok = a == 1 and not (b == 1 and c == 1 and stress == 1)
    return {"objective": float(objective), "ok": ok}


def problem():
    designs = tuple(
        track_b.Design(f"d{i}", values)
        for i, values in enumerate(itertools.product((0, 1), repeat=3))
    )
    conditions = (
        track_b.Condition("r1", "REPRESENTATIVE", (0, 0)),
        track_b.Condition("r2", "REPRESENTATIVE", (1, 0)),
        track_b.Condition("b1", "BOUNDARY_STRESS", (2, 1)),
    )
    return track_b.Problem(
        challenge="toy",
        designs=designs,
        conditions=conditions,
        passes=lambda q: q["ok"],
        objective=lambda q: q["objective"],
        host_route=HOST,
    )


def reference(p=None, *, guard=None):
    p = p or problem()
    cases = {
        p.point(d, c): track_b.Case(_quantities(d.values, c.values), SOLVE_CORE_S, HOST)
        for d in p.designs
        for c in p.conditions
    }
    ref = track_b.Reference(cases, evidence_class="SYNTHETIC_FIXTURE", source="toy")
    if guard is not None:
        original = ref.case

        def guarded(point):
            guard()
            return original(point)

        ref.case = guarded
    return ref


def _split(point):
    return tuple(point[:3]), tuple(point[3:])


def model(name, transform=lambda q: q, one_time=1000.0):
    def infer(points):
        return [transform(_quantities(*_split(p))) for p in points]

    return track_b.Predictor(
        name=name,
        kind=track_b.MODEL,
        planning_core_seconds=0.01,
        planning_route=HOST,
        infer=infer,
        one_time=(
            ("training_data_generation", HOST, one_time, "ALLOCATED_CPU_X_WALL", "toy"),
        ),
    )


def solver(ref=None):
    return track_b.Predictor(
        name="solver",
        kind=track_b.SOLVER,
        planning_core_seconds=SOLVE_CORE_S,
        planning_route=HOST,
        reference=ref or reference(),
    )


def clock():
    return 0.0


# --------------------------------------------------------------------- cost


def test_cost_prices_one_route_and_refuses_unapproved_usd():
    charges = [
        cost.Charge("a", "inference", HOST, 5.0, "MEASURED_CPU"),
        cost.Charge("a", "in_search_solve", HOST, 100.0, "ALLOCATED_CPU_X_WALL"),
    ]
    priced = cost.price(charges, UNIT)
    assert (priced["status"], priced["value"]) == (cost.SINGLE_ROUTE, 105.0)
    usd = cost.price(charges, cost.Unit("usd"))
    assert usd["status"] == cost.NO_APPROVED_RATE and usd["value"] is None
    rate = cost.Rate(HOST, 0.036, "synthetic-approval")
    assert cost.price(charges, cost.Unit("usd"), rates=[rate])[
        "value"
    ] == pytest.approx(105.0 / 3600 * 0.036)


def test_mixed_hardware_is_unpriced_unless_a_cited_conversion_exists():
    charges = [
        cost.Charge("a", "in_search_solve", HOST, 100.0, "ALLOCATED_CPU_X_WALL"),
        cost.Charge("a", "in_search_solve", "toy-pod", 60.0, "ALLOCATED_CPU_X_WALL"),
    ]
    assert cost.price(charges, UNIT)["status"] == cost.UNPRICED
    conversion = cost.Conversion("toy-pod", HOST, 1.6, "toy paired timing")
    priced = cost.price(charges, UNIT, conversions=[conversion])
    assert priced["status"] == cost.CONVERTED
    assert priced["value"] == pytest.approx(196.0)


def test_verification_is_charged_to_no_arm():
    with pytest.raises(cost.CostError, match="verification_is_charged_to_no_arm"):
        cost.Charge("arm", "verification", HOST, 1.0, "MEASURED_CPU")
    with pytest.raises(cost.CostError, match="verification_is_charged_to_no_arm"):
        cost.Charge(cost.VERIFICATION, "inference", HOST, 1.0, "MEASURED_CPU")
    with pytest.raises(cost.CostError, match="unknown_cost_category"):
        cost.Charge("arm", "tea", HOST, 1.0, "MEASURED_CPU")


# ----------------------------------------------------------------- harness


def test_only_the_solver_reaches_the_reference():
    with pytest.raises(track_b.TrackBError, match="only_the_solver"):
        track_b.Predictor(
            name="sneaky",
            kind=track_b.MODEL,
            planning_core_seconds=0.0,
            planning_route=HOST,
            infer=lambda points: [],
            reference=reference(),
        )


def test_equal_cost_budget_stops_the_solver_and_amortises_one_time(tmp_path):
    p = problem()
    arms = [
        track_b.Arm("solver-grid", solver(), "fixed_grid"),
        track_b.Arm("exact-grid", model("exact"), "fixed_grid"),
    ]
    result = track_b.economic(
        p,
        arms,
        budget=6 * SOLVE_CORE_S,
        unit=UNIT,
        reference=reference(p),
        directory=tmp_path,
        ladder=(1, 10),
        clock=clock,
    )
    deciding = result["views"]["equal_cost_deciding"]
    solver_row = deciding["1"]["solver-grid"]
    # B buys six solves: two designs at three conditions, both infeasible.
    assert solver_row["queries_used"] == 6
    assert solver_row["per_decision_search_cost"]["value"] == 600.0
    assert solver_row["status"] == "ABSTAIN"
    assert solver_row["actual_cost_exceeds_budget"] is False
    # The model's one-time cost (1000) exceeds B at N=1 but not at N=10.
    assert deciding["1"]["exact-grid"]["status"] == track_b.OVER_BUDGET
    searched = deciding["10"]["exact-grid"]
    assert searched["amortised_one_time_cost"] == 100.0
    assert searched["queries_used"] == 24
    assert searched["scopes"][track_b.CONTRACT_SCOPE]["correct_decision"] is True
    assert searched["cost_to_correct_decision"] == 100.0
    even = result["views"]["amortised_break_even"]["exact-grid"]
    # Model per decision 0 vs solver 600: 1000 / 600 rounds up to 2.
    assert (even["status"], even["break_even_decisions"]) == ("COMPUTED", 2)
    assert even["model_correct_decision"] is True
    assert even["solver_correct_decision"] is False


def test_verification_starts_only_after_every_commitment(tmp_path):
    p = problem()
    expected = 2

    def guard():
        files = list(tmp_path.glob("*.commitment.json"))
        assert len(files) == expected, "reference reached before all commitments"

    result = track_b.alignment(
        p,
        [model("exact"), model("pessimist", lambda q: {**q, "ok": False})],
        method="fixed_grid",
        parameters={},
        query_allowance=24,
        reference=reference(p, guard=guard),
        directory=tmp_path,
        unit=UNIT,
        clock=clock,
    )
    assert result["arms"]["pessimist"]["status"] == "ABSTAIN"
    assert result["arms"]["pessimist"]["scopes"][track_b.CONTRACT_SCOPE][
        "abstained_while_feasible_exists"
    ]


def test_an_altered_commitment_stops_verification(tmp_path):
    p = problem()
    arm = track_b.Arm("exact", model("exact"), "fixed_grid")
    selection, oracle, _ = track_b._search(
        p, arm, cost.Ledger(), ("points", 24), UNIT, (), (), clock
    )
    document = track_b._commit(p, arm, selection, oracle, tmp_path, "t")
    path = tmp_path / "t--exact.commitment.json"
    altered = json.loads(path.read_text())
    altered["design_id"] = "d0"
    path.write_text(json.dumps(altered))
    with pytest.raises(track_b.TrackBError, match="commitment_altered"):
        track_b._load_commitments(tmp_path, {"exact": document})
    with pytest.raises(FileExistsError):
        track_b._commit(p, arm, selection, oracle, tmp_path, "t")


def test_alignment_excludes_one_time_cost_and_separates_groups(tmp_path):
    p = problem()

    def optimistic(q):
        return {**q, "ok": True}

    result = track_b.alignment(
        p,
        [model("exact"), model("optimistic", optimistic)],
        method="fixed_grid",
        parameters={},
        query_allowance=24,
        reference=reference(p),
        directory=tmp_path,
        unit=UNIT,
        clock=clock,
    )
    assert not [c for c in result["ledger"] if c["category"] in cost.ONE_TIME]
    exact = result["arms"]["exact"]["scopes"]
    # The exact model picks the best design feasible everywhere: d6 = (1,1,0).
    assert result["arms"]["exact"]["design_id"] == "d6"
    assert exact[track_b.CONTRACT_SCOPE]["correct_decision"] is True
    optimistic_scopes = result["arms"]["optimistic"]["scopes"]
    # The optimist picks d7 (1,1,1): feasible at the representative
    # conditions, infeasible at the boundary one, reported apart.
    assert result["arms"]["optimistic"]["design_id"] == "d7"
    assert (
        optimistic_scopes["REPRESENTATIVE"]["proposal_outcome"] == "CONFIRMED_FEASIBLE"
    )
    assert (
        optimistic_scopes["BOUNDARY_STRESS"]["proposal_outcome"]
        == "CONFIRMED_INFEASIBLE"
    )
    assert optimistic_scopes[track_b.CONTRACT_SCOPE]["false_feasible"] is True
    assert optimistic_scopes[track_b.CONTRACT_SCOPE]["point_false_accepts"] == 13
    assert result["comparators"][track_b.CONTRACT_SCOPE]["best"]["design_id"] == "d6"
    assert result["comparators"]["REPRESENTATIVE"]["best"]["design_id"] == "d7"


def test_missed_feasible_designs_are_named(tmp_path):
    p = problem()

    def infer(points):
        out = []
        for point in points:
            design, condition = _split(point)
            q = _quantities(design, condition)
            out.append({**q, "ok": False} if design == (1, 1, 0) else q)
        return out

    picky = track_b.Predictor(
        name="picky",
        kind=track_b.MODEL,
        planning_core_seconds=0.01,
        planning_route=HOST,
        infer=infer,
    )
    result = track_b.alignment(
        p,
        [picky],
        method="fixed_grid",
        parameters={},
        query_allowance=24,
        reference=reference(p),
        directory=tmp_path,
        unit=UNIT,
        clock=clock,
    )
    scopes = result["arms"]["picky"]["scopes"]
    assert scopes[track_b.CONTRACT_SCOPE]["missed_feasible_designs"] == ["d6"]
    assert scopes[track_b.CONTRACT_SCOPE]["regret"]["status"] == "DEFINED_FINITE_SET"
    assert scopes[track_b.CONTRACT_SCOPE]["correct_decision"] is False


def test_solver_repeat_is_a_cache_hit_and_still_an_evaluation():
    p = problem()
    arm = track_b.Arm("solver", solver(), "fixed_grid")
    ledger = cost.Ledger()
    oracle = track_b._Oracle(p, arm, ledger, ("points", 10), SOLVE_CORE_S, clock)
    point = p.point(p.designs[0], p.conditions[0])
    first = oracle.query([point])
    second = oracle.query([point])
    assert first == second and oracle.used == 2
    assert [c.category for c in ledger.charges()] == ["in_search_solve", "cache_lookup"]
    model_arm = track_b.Arm("m", model("exact"), "fixed_grid")
    model_oracle = track_b._Oracle(
        p, model_arm, cost.Ledger(), ("points", 10), 0.01, clock
    )
    model_oracle.query([point])
    with pytest.raises(track_b.TrackBError, match="duplicate_query"):
        model_oracle.query([point])


def test_registered_methods_and_seeded_random_subset_run_unchanged(tmp_path):
    p = problem()
    expected = {
        "screen_then_confirm": ({"screen_condition": 2}, "d6"),
        "random_subset": ({"seed": 7}, "d6"),
        # On a two-level grid the smallest registered stride (2) samples only
        # design (0, 0, 0), which is infeasible, so there is nothing to refine
        # and the method abstains. That is the method, reported honestly.
        "coarse_to_fine": ({"stride": 2, "radius": 1, "top_k": 2}, None),
    }
    for method, (parameters, design_id) in expected.items():
        result = track_b.alignment(
            p,
            [model("exact")],
            method=method,
            parameters=parameters,
            query_allowance=24,
            reference=reference(p),
            directory=tmp_path / method,
            unit=UNIT,
            clock=clock,
        )
        assert result["arms"]["exact"]["design_id"] == design_id, method
    with pytest.raises(track_b.TrackBError, match="seed_must_be_an_integer"):
        track_b.run_method("random_subset", {"seed": "7"}, None, None)


def test_economic_view_needs_one_solver_and_a_valid_ladder(tmp_path):
    p = problem()
    with pytest.raises(track_b.TrackBError, match="exactly_one_solver"):
        track_b.economic(
            p,
            [track_b.Arm("m", model("exact"), "fixed_grid")],
            budget=100.0,
            unit=UNIT,
            reference=reference(p),
            directory=tmp_path,
        )
    with pytest.raises(track_b.TrackBError, match="decision_count_ladder"):
        track_b.economic(
            p,
            [track_b.Arm("s", solver(), "fixed_grid")],
            budget=100.0,
            unit=UNIT,
            reference=reference(p),
            directory=tmp_path,
            ladder=(0,),
        )


def test_diagnostic_equal_query_view_is_labelled_apart(tmp_path):
    p = problem()
    result = track_b.economic(
        p,
        [
            track_b.Arm("solver-grid", solver(), "fixed_grid"),
            track_b.Arm("exact-grid", model("exact"), "fixed_grid"),
        ],
        budget=24 * SOLVE_CORE_S,
        unit=UNIT,
        reference=reference(p),
        directory=tmp_path,
        ladder=(1,),
        diagnostic_query_allowance=24,
        clock=clock,
    )
    diagnostic = result["views"]["equal_query_diagnostic"]
    assert diagnostic["query_allowance"] == 24
    assert {a["queries_used"] for a in diagnostic["arms"].values()} == {24}
    # At the full-set anchor the solver arm reaches the correct decision.
    anchor = result["views"]["equal_cost_deciding"]["1"]["solver-grid"]
    assert anchor["scopes"][track_b.CONTRACT_SCOPE]["correct_decision"] is True
    assert anchor["cost_to_correct_decision"] == 2400.0


# -------------------------------------------------------------- score-value


def test_tau_b_matches_battery_and_rho_is_rank_pearson():
    rng = random.Random(3)
    for _ in range(50):
        n = rng.randint(2, 9)
        xs = [rng.choice([0, 1, 2, 3]) for _ in range(n)]
        ys = [rng.choice([0, 1, 2]) for _ in range(n)]
        assert score_value.kendall_tau_b(xs, ys) == battery_decision.kendall_tau_b(
            xs, ys
        )
    assert score_value.spearman_rho([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    assert score_value.spearman_rho([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0
    # Ranks (1, 2, 3) against (2, 1, 3): rho = 1 - 6*2/(3*8) = 0.5.
    assert score_value.spearman_rho([1, 2, 3], [2, 1, 3]) == pytest.approx(0.5)
    assert score_value.spearman_rho([1, 1, 1], [1, 2, 3]) is None


def _battery_results(scores, losses, spread):
    """A battery-shaped result: two seeds per recipe, losses spread apart."""

    members, rule_scores, variation = {}, {}, {}
    for recipe, (score, loss) in enumerate(zip(scores, losses)):
        for seed, delta in ((0, 0.0), (1, spread)):
            name = f"r{recipe}-s{seed}"
            members[name] = {
                "eligible": True,
                "kind": "RECONSTRUCTED",
                "loss_development": loss + delta,
                "loss_verification": loss + delta,
            }
            rule_scores[name] = {battery_divergence.DECIDING_RULE: score}
        variation[f"r{recipe}"] = {
            split: {"seeds": 2, "max": loss + spread, "min": loss}
            for split in battery_divergence.SPLITS
        }
    return {
        "schema": "carbon.engineering-value-results.v1",
        "summary": {"members": members},
        "rule_scores": rule_scores,
        "seed_variation": variation,
    }


@pytest.mark.parametrize(
    "scores, losses, spread",
    [
        ([3.0, 2.0, 1.0], [1.0, 2.0, 3.0], 0.1),  # aligned: nothing fires
        ([3.0, 2.0, 1.0], [3.0, 2.0, 1.0], 0.1),  # inverted: fires
        ([3.0, 2.0, 1.0], [1.05, 1.0, 3.0], 0.2),  # gap inside the band
    ],
)
def test_divergence_matches_battery_on_its_own_shape(scores, losses, spread):
    results = _battery_results(scores, losses, spread)
    battery = {
        (c["condition"], c["member"])
        for c in battery_divergence.conditions(results)
        if c.get("split") in (None, "verification")
    }
    members = {
        name: {
            "score": results["rule_scores"][name][battery_divergence.DECIDING_RULE],
            "value": row["loss_verification"],
            "eligible": row["eligible"],
            "recipe": name.rsplit("-s", 1)[0],
            "kind": row["kind"],
        }
        for name, row in results["summary"]["members"].items()
    }
    neutral = score_value.alignment(members)
    assert {(c["condition"], c["member"]) for c in neutral["conditions"]} == battery
    assert neutral["value_noise_band"] == pytest.approx(spread)
    band = battery_divergence.tau_noise_band(results)
    assert neutral["tau_noise_band"]["band"] == pytest.approx(band["band"])


def test_decision_value_orders_correct_abstain_and_unsafe(tmp_path):
    p = problem()
    result = track_b.alignment(
        p,
        [
            model("exact"),
            model("pessimist", lambda q: {**q, "ok": False}),
            model("optimistic", lambda q: {**q, "ok": True}),
        ],
        method="fixed_grid",
        parameters={},
        query_allowance=24,
        reference=reference(p),
        directory=tmp_path,
        unit=UNIT,
        clock=clock,
    )
    values = {
        arm: track_b.decision_value(row["scopes"][track_b.CONTRACT_SCOPE])
        for arm, row in result["arms"].items()
    }
    assert values == {"exact": (0, 0.0), "pessimist": (1, 0.0), "optimistic": (2, 0.0)}
    # A score that ranks the unsafe optimist first diverges from value.
    members = {
        arm: {
            "score": score,
            "value": values[arm],
            "eligible": True,
            "recipe": arm,
            "kind": "RECONSTRUCTED",
        }
        for arm, score in (("exact", 1.0), ("pessimist", 2.0), ("optimistic", 3.0))
    }
    aligned = score_value.alignment(members)
    assert aligned["kendall_tau_b"] == -1.0
    assert aligned["spearman_rho"] == -1.0
    fired = {c["member"] for c in aligned["conditions"]}
    assert fired == {"pessimist", "optimistic"}
    assert aligned["top_k"] == {
        "k": 1,
        "by_score": ["optimistic"],
        "by_value": ["exact"],
        "overlap": 0,
    }


def test_mixed_hardware_one_time_cost_is_bracketed_beside_the_point(tmp_path):
    p = problem()
    mixed = track_b.Predictor(
        name="mixed",
        kind=track_b.MODEL,
        planning_core_seconds=0.0,
        planning_route=HOST,
        infer=model("exact").infer,
        one_time=(
            ("training_data_generation", HOST, 400.0, "ALLOCATED_CPU_X_WALL", "h"),
            ("training_data_generation", "toy-pod", 600.0, "ALLOCATED_CPU_X_WALL", "p"),
        ),
    )
    arms = [
        track_b.Arm("solver-grid", solver(), "fixed_grid"),
        track_b.Arm("mixed-grid", mixed, "fixed_grid"),
    ]

    def run(label, factor):
        conversions = (
            ()
            if factor is None
            else (cost.Conversion("toy-pod", HOST, factor, f"toy {label}"),)
        )
        return track_b.economic(
            p,
            arms,
            budget=6 * SOLVE_CORE_S,
            unit=UNIT,
            reference=reference(p),
            directory=tmp_path / label,
            ladder=(10,),
            conversions=conversions,
            assumption=label,
            clock=clock,
        )

    point = run("point", None)
    summary = track_b.bracket(
        point, {"lower": run("lower", 1.0), "upper": run("upper", 1.6)}
    )
    mixed_row = summary["mixed-grid"]
    assert mixed_row["point_status"] == cost.UNPRICED
    assert mixed_row["one_time_range"] == [1000.0, pytest.approx(1360.0)]
    # Solver per decision 600, model 0: 1000/600 -> 2 and 1360/600 -> 3.
    assert mixed_row["break_even_range"] == [2, 3]
    assert mixed_row["assumptions"]["upper"]["conversions"][0]["factor"] == 1.6


def test_an_overrun_is_also_reported_at_the_rung_that_covers_it(tmp_path):
    p = problem()
    cases = {
        point: track_b.Case(case.quantities, 150.0, HOST)
        for point, case in reference(p)._cases.items()
    }
    pricey = track_b.Reference(cases, evidence_class="SYNTHETIC_FIXTURE", source="toy")
    arms = [track_b.Arm("solver-grid", solver(pricey), "fixed_grid")]
    rungs = {
        f"k{k}": track_b.economic(
            p,
            arms,
            budget=k * SOLVE_CORE_S,
            unit=UNIT,
            reference=pricey,
            directory=tmp_path / f"k{k}",
            ladder=(1,),
            clock=clock,
        )
        for k in (6, 12)
    }
    overruns = track_b.ladder_overruns(rungs)
    # Planned at 100 per solve, six solves cost 900 > 600: covered by k12.
    assert overruns[0]["rung"] == "k6"
    assert overruns[0]["actual_total_cost"] == 900.0
    assert overruns[0]["also_reported_at_rung"] == "k12"
