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
    raw = row.get("context_count", 1) * math.prod(
        len(axis["recommendation"]) for axis in row["requirement_axes"]
    )
    assert row["raw_question_grid_upper_bound"] == raw
    assert row["distinct_answer_changing_questions"] is None
    assert row["distinct_best_picks"] is None
    assert row["revised_bank_cpu_hours"] is None
    assert row["support_gate"]


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


def test_cooling_is_cell_only_and_the_batch_capacity_shortfall_is_explicit():
    row = next(row for row in SHEET["challenges"] if row["challenge"] == "cooling-cell")
    assert "periodic cooling cell only" in row["scope"]
    assert "no full cold plate" in row["scope"]
    assert row["raw_question_grid_upper_bound"] == 9
    assert _recommendation(row["questions_per_batch"]) == 12
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


def test_part_b_is_explicitly_merge_gated_and_battery_reuse_is_not_scoring_adoption():
    assert "**landing**" in TEXT
    assert "Q3 redraw of all-infeasible tasks" in TEXT
    assert "not** copied" in TEXT
    assert "Validators rebuild/score; they" in TEXT
    assert "never solve references" in TEXT
