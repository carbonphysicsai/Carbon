"""Track B on the motor decision, by no-cost replay of its counted GetDP.

The replay table (``docs/development/evidence/track-b-replay/``) is derived
from the 48 counted records adopted by study V2 (OWNER-MOTOR-COUNTED-ADOPT-01).
The raw records stay outside Git. These tests check the replay against the
committed completion manifest and the counted result, then run both Track B
questions on it. Nothing is solved and nothing is spent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from carbon.design_search import cost, track_b
from carbon.motor import track_b as motor

REPOSITORY = Path(__file__).resolve().parents[2]
COUNTED = REPOSITORY / "docs/development/evidence/motor-decision-counted-v2"


@pytest.fixture(scope="module")
def study():
    config = motor.load_config(REPOSITORY)
    table = json.loads((REPOSITORY / motor.REPLAY).read_text(encoding="utf-8"))
    reference = motor.replay_reference(config, table)
    problem, contract = motor.problem(config)
    predictors = motor.predictors(
        config, repository=REPOSITORY, contract=contract, reference=reference
    )
    return config, table, reference, problem, predictors


def test_replay_is_the_adopted_counted_campaign(study):
    _, table, _, _, _ = study
    completion = json.loads((COUNTED / "completion.json").read_text("utf-8"))
    campaign = completion["campaign"]
    assert table["source_records_sha256"] == campaign["records_sha256"]
    assert len(table["cases"]) == campaign["initial_attempts"] == 48
    assert {row["status"] for row in table["cases"]} == {"OK"}
    assert sum(row["wall_s"] for row in table["cases"]) == pytest.approx(
        campaign["solver_wall_sum_s"]
    )
    assert table["solver_image"] == campaign["solver_image"]


def test_track_b_reproduces_the_counted_decision_result(study, tmp_path):
    _, _, reference, problem, predictors = study
    counted = json.loads((COUNTED / "completion.json").read_text("utf-8"))[
        "decision_result"
    ]
    result = track_b.alignment(
        problem,
        [predictors["analytic-v1"], predictors["learned-krr-v1"]],
        method="fixed_grid",
        parameters={},
        query_allowance=48,
        reference=reference,
        directory=tmp_path,
        unit=motor.UNIT,
    )
    comparator = result["comparators"][track_b.CONTRACT_SCOPE]
    assert comparator["status"] == counted["comparator_status"]
    assert comparator["coverage"]["confirmed_feasible_designs"] == (
        counted["confirmed_feasible_designs"]
    )
    assert comparator["best"]["design_id"] == counted["best_design_id"]
    assert comparator["best"]["worst_objective"] == pytest.approx(
        counted["best_worst_ripple_fraction"]
    )
    # The analytical model predicts zero ripple for every design, so every
    # design ties. Track B's neutral rule takes the lower design (d01), where
    # the registered study breaks ties by higher mean torque (d07). Both
    # selections are reference-infeasible, so the unsafe outcome is the same.
    analytic = result["arms"]["analytic-v1"]
    assert analytic["design_id"] == "d01"
    assert analytic["scopes"][track_b.CONTRACT_SCOPE]["false_feasible"] is True
    assert counted["arms"]["analytic-v1:fixed_grid"]["outcome"] == (
        "CONFIRMED_INFEASIBLE"
    )
    krr = result["arms"]["learned-krr-v1"]
    assert krr["design_id"] == "d06"
    assert krr["scopes"][track_b.CONTRACT_SCOPE]["regret"]["regret"] == pytest.approx(
        counted["arms"]["learned-krr-v1:fixed_grid"]["regret_ripple_fraction"]
    )


def test_motor_bracket_and_full_set_anchor(study, tmp_path):
    _, _, reference, problem, predictors = study
    ladder = motor.proposed_budget_ladder(reference)
    assert ladder["k48"] == pytest.approx(
        48 * motor.median_solve_core_seconds(reference)
    )
    arms = [
        track_b.Arm("solver-grid", predictors["solver"], "fixed_grid"),
        track_b.Arm("krr-grid", predictors["learned-krr-v1"], "fixed_grid"),
    ]

    def run(label, conversions):
        return track_b.economic(
            problem,
            arms,
            budget=ladder["anchor_full_set"],
            unit=motor.UNIT,
            reference=reference,
            directory=tmp_path / label,
            ladder=(1, 1000),
            conversions=conversions,
            assumption=label,
        )

    point = run("point", ())
    bounds = {
        label: run(label, conversions)
        for label, conversions in motor.bracket_conversions().items()
    }
    summary = track_b.bracket(point, bounds)["krr-grid"]
    assert summary["point_status"] == cost.UNPRICED
    low, high = summary["one_time_range"]
    assert 0 < low < high
    solver = bounds["lower"]["views"]["equal_cost_deciding"]["1"]["solver-grid"]
    assert solver["queries_used"] == 48
    assert solver["design_id"] == "d04"
    assert solver["scopes"][track_b.CONTRACT_SCOPE]["correct_decision"] is True
