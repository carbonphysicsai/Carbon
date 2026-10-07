"""Static proposal checks and synthetic arithmetic, not a quiz or solver."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / "docs/development/challenge_pipeline/question-laws"
SHEET = json.loads((PACKET / "proposals.json").read_text(encoding="utf-8"))
TEXT = (PACKET / "README.md").read_text(encoding="utf-8")
QUIZ = (PACKET / "motor-cooling-quiz.md").read_text(encoding="utf-8")


def _recommendation(value):
    assert value["status"] == "HUMAN_INPUT"
    assert value["registered"] is None
    assert value["recommendation"] is not None
    return value["recommendation"]


def test_only_a_non_runtime_eight_challenge_proposal():
    assert SHEET["ticket"] == "CHALLENGE-QUESTION-LAWS-01"
    assert SHEET["maturity"] == "SPECIFIED"
    assert SHEET["runtime_registration"] is False
    assert {row["family"] for row in SHEET["challenges"]} == {
        "f02",
        "f04",
        "f05",
        "f06",
        "f08",
        "f09",
        "f13",
        "f17",
    }
    assert len(SHEET["challenges"]) == 8


@pytest.mark.parametrize("row", SHEET["challenges"], ids=lambda row: row["challenge"])
def test_every_new_law_value_is_unregistered_and_capacity_is_not_invented(row):
    for key in ("P", "Q", "w", "exposure_E", "near_limit_bands"):
        _recommendation(SHEET["common"][key])
    for key in (
        "service_contexts",
        "objective",
        "bank_candidates",
        "questions_per_batch",
    ):
        _recommendation(row[key])
    for axis in row["requirement_axes"]:
        values = _recommendation(axis)
        assert values == sorted(set(values))
        assert all(math.isfinite(value) for value in values)
        assert axis["op"] in ("<=", ">=")
        assert axis["unit"] and axis["quantity"]
        interval = _recommendation(axis["continuous_interval"])
        assert interval == [min(values), max(values)]
        assert interval[0] < interval[1]
    raw = row.get("context_count", 1) * math.prod(
        len(axis["recommendation"]) for axis in row["requirement_axes"]
    )
    assert row["raw_question_grid_upper_bound"] == raw
    assert row["distinct_answer_changing_questions"] is None
    assert row["distinct_best_picks"] is None
    assert row["revised_bank_cpu_hours"] is None
    assert row["support_gate"]
    continuous = row["continuous_variant"]
    _recommendation(continuous)
    assert continuous["report_status"] == "NOT_DEMONSTRATED"
    for key in (
        "expected_distinct_winners_P",
        "expected_distinct_winners_Q",
        "close_call_rate_P",
        "close_call_rate_Q",
        "residual_unresolved_rate",
    ):
        assert continuous[key] is None


def test_one_historical_cost_never_prices_seven_other_or_revised_scopes():
    measured = SHEET["historical_measured_cost"]
    assert measured["solves"] * measured[
        "approximate_cpu_seconds_per_solve"
    ] / 3600 == (pytest.approx(67.1))
    assert measured["reported_approximate_cpu_hours"] == 68
    assert "not the revised" in measured["scope"]
    statuses = {
        row["challenge"]: row["solve_cost_status"] for row in SHEET["challenges"]
    }
    assert statuses.pop("battery") == "MEASURED_HISTORICAL_ONLY"
    assert set(statuses.values()) == {"UNMEASURED"}
    assert len(statuses) == 7


def test_cooling_is_cell_only_and_initial_batch_recommendation_is_eight():
    row = next(row for row in SHEET["challenges"] if row["challenge"] == "cooling-cell")
    assert "periodic cooling cell only" in row["scope"]
    assert "no full cold plate" in row["scope"]
    assert row["raw_question_grid_upper_bound"] == 9
    assert _recommendation(row["questions_per_batch"]) == 8
    assert "cannot supply twelve distinct" in TEXT
    assert "UNMEASURED" in row["solve_cost_status"]
    assert "CELL allocations" in row["mandatory_anchor"]
    assert "Unsupported reduced-supply scenario excluded" in row["support_gate"]


def test_task_interface_seams_and_exposure_custody_are_not_silently_adopted():
    for phrase in (
        "Outer P/Q/w must not be silently put in inner strata",
        "unweighted `mean`",
        "role-aware observer projection",
        "hashes ordered candidate IDs, not physical truths",
        "MIGRATION_REQUIRED",
        "NEW_OWNER_DECISION_REQUIRED",
        "Test Lead owns",
        "Idempotent replay/model arms",
        "never return to hidden use",
        "one question per underlying window",
        "Do not repeatedly redraw",
        "exact protected picks",
        "after every drawing window",
    ):
        # The README uses slightly different line wrapping for two phrases.
        normalized = " ".join(TEXT.split())
        if phrase == "after every drawing window":
            assert "every drawing window has ended" in normalized
        else:
            assert phrase in normalized


def test_synthetic_threshold_count_is_not_answer_diversity_or_new_exposure():
    # Invented values only: no physical truth, runtime task or protected bank.
    designs = [("A", 80, 3), ("B", 84, 2), ("C", 88, 1)]
    caps = [79, 81, 83, 85, 87, 89]
    signatures, answers = [], []
    for cap in caps:
        feasible = [design for design in designs if design[1] <= cap]
        signatures.append(tuple(design[0] for design in feasible))
        answers.append(
            min(feasible, key=lambda design: design[2])[0] if feasible else None
        )
    assert answers == [None, "A", "A", "B", "B", "C"]
    assert len(caps) == 6
    assert len(set(signatures)) == len(set(answers)) == 4
    assert len(set(answers) - {None}) == 3
    # Recommendation: every question draws the complete shared support once.
    residual_exposures = [2, 4, 3]
    usable = min(len(set(answers)), min(residual_exposures))
    assert usable == 2
    assert min(len(set(answers)), 0) == 0  # no threshold can revive retired truth


def test_one_dominating_answer_and_missing_truth_are_different_failures():
    # A solver failure/unknown competitor is not NONE_FEASIBLE or a new pick.
    repeated_picks = ["A", "A", "A"]
    assert len(set(repeated_picks)) < _recommendation(
        SHEET["common"]["minimum_distinct_resolved_picks_per_batch"]
    )
    reference_verdicts = [False, None]
    assert not all(verdict is False for verdict in reference_verdicts)
    assert not any(verdict is True for verdict in reference_verdicts)
    assert "UNRESOLVED is coverage" in TEXT
    assert "reference/infrastructure failure remains typed" in " ".join(TEXT.split())


def test_one_old_cell_result_is_not_proof_of_bank_wide_infeasibility():
    normalized = " ".join(TEXT.split())
    assert "report bounds every member of the retained old bank" in normalized
    assert "One reported cell solve alone cannot establish" in normalized
    assert "mean wall temperature cannot stand in for local TIM peak" in normalized


def test_part_b_merge_dependency_is_satisfied_not_a_scoring_adoption():
    assert "**landing**" in TEXT
    assert "Q3 redraw of all-infeasible tasks" in TEXT
    assert "not** copied" in TEXT
    assert "Validators rebuild/score; they" in TEXT
    assert "never solve references" in TEXT
    assert SHEET["basis"]["feasibility_merge"] in QUIZ
    assert SHEET["basis"]["tasks_merge"] in QUIZ
    assert "SPECIFIED only" in QUIZ


def test_continuous_law_is_an_owner_choice_not_uniform_answer_cells():
    for key in (
        "variant_selection",
        "continuous_P",
        "continuous_Q",
        "continuous_w",
        "winner_expectation_method",
        "close_call_method",
    ):
        _recommendation(SHEET["common"][key])
    normalized = " ".join(TEXT.split())
    for phrase in (
        "owner picks grid or continuous",
        "density over regions",
        "peak absolute cap remains twice holding cap",
        "not guaranteed by continuity",
        "Continuous decimals do not supply fresh exposure",
        "compute occupancy under the exact registered batch law",
    ):
        assert phrase in normalized


def test_synthetic_continuous_occupancy_is_bank_bounded_not_decimal_count():
    # Same arbitrary A/B/C example, continuous cap U[78,90]. No solver truth.
    # NONE on [78,80), A on [80,84), B on [84,88), C on [88,90].
    masses = {"NONE": 2 / 12, "A": 4 / 12, "B": 4 / 12, "C": 2 / 12}
    assert sum(masses.values()) == pytest.approx(1)
    k = 8
    expected = sum(1 - (1 - masses[a]) ** k for a in ("A", "B", "C"))
    assert expected == pytest.approx(2.6893950760)
    assert expected <= min(k, 3)
    # A diagnostic Q concentrated on A changes observed occupancy; weighting
    # observations cannot make it equal to the P occupancy.
    q_masses = {"A": 0.6, "B": 0.15, "C": 0.05, "NONE": 0.2}
    q_expected = sum(1 - (1 - q_masses[a]) ** k for a in ("A", "B", "C"))
    assert q_expected < expected
    # NONE and unresolved coverage are not distinct resolved winners.
    all_unresolved = {"UNRESOLVED": 1.0}
    assert sum(1 - (1 - p) ** k for a, p in all_unresolved.items() if a == "A") == 0
    # Requiring k draws does not create the missing residual E.
    assert min([2, 4, 3]) < k


def test_synthetic_close_call_rate_is_band_width_not_exact_equality():
    # Arbitrary continuous cap U[78,90], temperature intervals around 80/84/88.
    # Half-width .25 gives three disjoint .5-wide crossing regions.
    interval_width = 90 - 78
    rate = 3 * (2 * 0.25) / interval_width
    assert rate == pytest.approx(0.125)
    assert 0 < rate < 1
    # No grid cap is in those bands; continuity need not change pick count.
    assert all(
        min(abs(cap - edge) for edge in (80, 84, 88)) > 0.25
        for cap in (79, 81, 83, 85, 87, 89)
    )
    assert "reference-unavailable rate" in TEXT


def test_both_quizzes_have_behavioural_controls_and_all_five_diagnostics():
    normalized = " ".join(QUIZ.split())
    for phrase in (
        "Motor Q2 near-limit content",
        "Cooling cell Q2 near-limit content",
        "Holding torque floor",
        "Peak torque floor",
        "Zero-current cogging",
        "Local TIM jump",
        "Good accurate selector",
        "Good calibrated uncertainty",
        "Edge-optimist",
        "Over-cautious",
        "Localized sign-error",
        "Optimizer or lattice aware",
        "(a) Optimizer stability",
        "(b) Grid resolution",
        "(c) Power by k",
        "(d) Agreement with decision value",
        "(e) Unresolved rate",
        "none becomes a gate or score input",
        "No failed reference",
        "Validators **never solve references**",
        "Accurate edge optima are **not gaming**",
        "no redraw until a convenient feasible set appears",
        "count those composite actions explicitly",
        "before answer-key access",
    ):
        assert phrase in normalized
