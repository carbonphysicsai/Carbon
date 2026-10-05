"""Track B on the AI cooling decision, by no-cost replay of its counted CFD.

The replay table (``docs/development/evidence/track-b-replay/``) is derived
from the counted CHALLENGE-AI-COOLING records kept outside Git; these tests
check it against the committed completion manifest and run both Track B
questions on it. Nothing is solved and nothing is spent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from carbon.cold_plate import track_b as cooling
from carbon.design_search import cost, track_b

REPOSITORY = Path(__file__).resolve().parents[2]
COMPLETION = (
    REPOSITORY / "docs/development/evidence/ai-cooling-counted-v1/completion.json"
)


@pytest.fixture(scope="module")
def study():
    config = cooling.load_config(REPOSITORY)
    table = json.loads((REPOSITORY / cooling.REPLAY).read_text(encoding="utf-8"))
    reference = cooling.replay_reference(config, table)
    problem, contract = cooling.problem(config)
    predictors = cooling.predictors(
        config, repository=REPOSITORY, contract=contract, reference=reference
    )
    return config, table, reference, problem, predictors


def test_replay_is_the_counted_campaign(study):
    config, table, _, _, _ = study
    completion = json.loads(COMPLETION.read_text(encoding="utf-8"))
    assert table["study_id"] == completion["study_id"] == config["study_id"]
    assert len(table["cases"]) == completion["execution"]["initial_attempts"] == 48
    assert {row["status"] for row in table["cases"]} == {"OK"}
    assert sum(row["wall_s"] for row in table["cases"]) == pytest.approx(
        completion["execution"]["solver_wall_sum_s"]
    )
    assert {row["cpus"] for row in table["cases"]} == {
        completion["execution"]["cpus_per_execution"]
    }
    assert table["solver_image"] == completion["execution"]["solver_image"]
    assert table["source_records_sha256"].startswith("sha256:")


def test_replay_comparator_matches_the_counted_result(study, tmp_path):
    _, _, reference, problem, predictors = study
    completion = json.loads(COMPLETION.read_text(encoding="utf-8"))["decision_result"]
    result = track_b.alignment(
        problem,
        [predictors["analytic-v1"], predictors["learned-krr-v1"]],
        method="fixed_grid",
        parameters={},
        query_allowance=48,
        reference=reference,
        directory=tmp_path,
        unit=cooling.UNIT,
    )
    contract = result["comparators"][track_b.CONTRACT_SCOPE]
    assert contract["status"] == completion["finite_set_comparator_status"]
    coverage = contract["coverage"]
    assert (
        coverage["confirmed_feasible_designs"]
        == completion["confirmed_feasible_designs"]
    )
    assert (
        coverage["confirmed_infeasible_designs"]
        == completion["confirmed_infeasible_designs"]
    )
    assert contract["best"]["design_id"] == completion["selected_design_id"]
    assert contract["best"]["worst_objective"] == pytest.approx(
        completion["representative_reference_cases"]["maximum_hydraulic_power_w"]
    )
    for arm in ("analytic-v1", "learned-krr-v1"):
        scopes = result["arms"][arm]["scopes"]
        assert result["arms"][arm]["design_id"] == "d03"
        assert scopes[track_b.CONTRACT_SCOPE]["correct_decision"] is True


def test_groups_expose_an_unsafe_interpolation_choice(study, tmp_path):
    _, _, reference, problem, predictors = study
    result = track_b.alignment(
        problem,
        [predictors["nearest-neighbour-v1"]],
        method="fixed_grid",
        parameters={},
        query_allowance=48,
        reference=reference,
        directory=tmp_path,
        unit=cooling.UNIT,
    )
    scopes = result["arms"]["nearest-neighbour-v1"]["scopes"]
    assert scopes["REPRESENTATIVE"]["proposal_outcome"] == "CONFIRMED_FEASIBLE"
    assert scopes["BOUNDARY_STRESS"]["proposal_outcome"] == "CONFIRMED_INFEASIBLE"
    assert scopes[track_b.CONTRACT_SCOPE]["false_feasible"] is True


def test_one_time_cost_is_recorded_by_route_and_not_mixed(study, tmp_path):
    _, _, reference, problem, predictors = study
    routes = {route for _, route, *_ in predictors["learned-krr-v1"].one_time}
    assert routes == {cooling.HOST_ROUTE, cooling.POOL_POD_ROUTE}
    ladder = cooling.proposed_budget_ladder(reference)
    assert ladder["k48"] == pytest.approx(
        48 * cooling.median_solve_core_seconds(reference)
    )
    result = track_b.economic(
        problem,
        [
            track_b.Arm("solver-grid", predictors["solver"], "fixed_grid"),
            track_b.Arm("analytic-grid", predictors["analytic-v1"], "fixed_grid"),
            track_b.Arm("krr-grid", predictors["learned-krr-v1"], "fixed_grid"),
        ],
        budget=ladder["k48"],
        unit=cooling.UNIT,
        reference=reference,
        directory=tmp_path,
        ladder=(1, 1000),
    )
    assert result["one_time_cost"]["krr-grid"]["status"] == cost.UNPRICED
    deciding = result["views"]["equal_cost_deciding"]
    assert deciding["1"]["krr-grid"] == {"status": cost.UNPRICED}
    assert deciding["1"]["analytic-grid"]["design_id"] == "d03"
    even = result["views"]["amortised_break_even"]
    assert even["krr-grid"]["status"] == "NOT_COMPUTABLE"
    assert even["analytic-grid"]["status"] == "COMPUTED"
    assert even["analytic-grid"]["model_correct_decision"] is True
