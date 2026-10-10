"""Static proposed-panel arithmetic only: no runner, reference or hidden data."""

from __future__ import annotations

import json
from collections import Counter
from decimal import Decimal
from itertools import product
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "docs/development/challenge_pipeline/question-laws"
PANEL = json.loads(
    (DIRECTORY / "battery-v3-middle-bands-panel.json").read_text(encoding="utf-8")
)
TEXT = (DIRECTORY / "battery-v3-middle-bands-panel.md").read_text(encoding="utf-8")
STEP = Decimal(PANEL["slice"]["c_rate_step"])


def _axis(group, coordinate):
    if f"{coordinate}_list" in group:
        return [Decimal(value) for value in group[f"{coordinate}_list"]]
    low, high = map(Decimal, group[f"{coordinate}_range"])
    steps = (high - low) / STEP
    assert steps == steps.to_integral_value()
    return [low + i * STEP for i in range(int(steps) + 1)]


def test_panel_has_no_execution_or_authority_capability():
    assert PANEL["maturity"] == "SPECIFIED"
    assert PANEL["accepted_manifest_digest"] is PANEL["dispatch_grant"] is None
    assert all(value is False for value in PANEL["permissions"].values())
    assert not PANEL["global_P_Q_w_E_k_changed"]
    assert not PANEL["other_challenge_laws_changed"]
    assert not PANEL["EV5_journal14_live_contract_changed"]
    assert PANEL["near"]["current_T2a"] == "NOT_DEMONSTRATED"


def test_all_proposed_actions_are_unique_lattice_tuples_with_allowed_cooling():
    rows = []
    counts = Counter()
    for group in PANEL["groups"]:
        c1, c2 = _axis(group, "c1"), _axis(group, "c2")
        assert len(c1) * len(c2) == group["rows"]
        assert group["cooling"] in (1, 2, 4)
        for first, second in product(c1, c2):
            assert first % STEP == second % STEP == 0
            assert 0 < second <= first <= Decimal("2.00")
            rows.append((group["ambient_c"], group["cooling"], first, second))
            counts[str(group["ambient_c"])] += 1
    assert len(rows) == len(set(rows)) == PANEL["stage_A"]["rows"] == 300
    assert dict(counts) == PANEL["stage_A"]["rows_by_band"]
    for band in (15, 25, 35):
        assert {h for t, h, _, _ in rows if t == band} == {1, 2, 4}


def test_newly_proposed_actions_do_not_adopt_global_bounds_or_slack():
    assert PANEL["slice"]["status"] == "HUMAN_INPUT_PANEL_RECOMMENDATION"
    assert PANEL["slice"]["global_action_bounds_adopted"] is False
    assert PANEL["hard_limits"] == {
        "charging_temperature_max_c": 45,
        "every_charge_plating_min_v": 0,
        "programme_voltage_max_v": 4.2,
        "q30_over_q1_min": 0.99,
        "time_hard_cap": None,
        "discharge_temperature_role": "DIAGNOSTIC",
        "producer_voltage_slack_adopted": False,
    }


def test_both_sides_use_two_bands_without_manufacturing_coverage():
    near = PANEL["near"]
    assert near["bands_both_sides"] == 2
    assert near["accepted_widths"] is None
    assert near["min_resolved_feasible"] == near["min_resolved_infeasible"] == 5
    assert near["missing_intervals_are_unresolved"]
    assert near["count_distinct_union_and_per_limit"]
    assert not near["widen_band_for_count"]
    assert not PANEL["stage_A"]["guaranteed_5_plus_5"]
    assert "T15 plating-only coverage" in TEXT
    # Toy signed margins, not battery outcomes: both endpoints must fit.
    band = Decimal("0.002")
    assert Decimal("0.003") <= 2 * band < Decimal("0.006")
    assert -2 * band <= Decimal("-0.003") < 0
    assert not (0 <= Decimal("-0.0001") <= Decimal("0.0039") <= 2 * band)


def test_reuse_includes_scheduled_identity_not_a_blind_subtraction():
    source = PANEL["source"]
    assert source["acquisition_head"] == "66ea509888e4ef0f5ac08750554db744b56b92bf"
    refinements = source["prior_registered_refinements"]
    assert sum(refinements[str(t)] for t in (15, 25, 35)) == 93
    assert refinements["all_bands"] == 115
    assert source["prior_completion"] == "NOT_VERIFIED"
    assert source["full_overlay_lock"] is None
    assert not source["operator_export_accessed"]
    assert PANEL["stage_A"]["reuse_by_complete_physical_and_rung_identity"]
    assert PANEL["stage_A"]["check_scheduled_before_start"]
    assert "Never subtract all93" in TEXT


def test_extension_cannot_extrapolate_change_cooling_or_create_truth():
    extension = PANEL["stage_B"]
    assert extension["max_extra_tuples"] == 3 * extension["max_extra_per_band"] == 60
    assert extension["within_group_axis_bounds"]
    assert extension["identical_fixed_coordinates"]
    assert extension["interpolation_is_truth"] is False
    assert extension["unbracketed_extrapolation"] is False
    assert extension["automatic_retries"] is False
    near = PANEL["near"]
    t_band = Decimal(near["recommendation_temperature_band_k"])
    p_band = Decimal(near["recommendation_plating_band_v"])
    assert all(
        abs(Decimal(t) - 45) == Decimal("1.5") * t_band
        for t in extension["temperature_targets_c"]
    )
    assert all(
        abs(Decimal(p)) == Decimal("1.5") * p_band
        for p in extension["plating_targets_v"]
    )


@pytest.mark.parametrize("scenario", PANEL["cost"]["scenarios"])
def test_cost_arithmetic_counts_full_programmes_and_does_not_claim_measurement(
    scenario,
):
    cost = PANEL["cost"]
    seconds = (
        scenario["standard"] * Decimal(cost["standard_cpu_s"])
        + scenario["rung2"] * Decimal(cost["refined_cpu_s_proxy"])
        + scenario["rung3"] * Decimal(cost["third_rung_cpu_s_allowance"])
    )
    assert float(seconds / 3600) == pytest.approx(float(scenario["cpu_h"]))
    assert (
        cost["refined_cpu_status"] == "SINGLE_THREAD_PROXY_ASSUMPTION_NOT_MEASURED_CPU"
    )
    assert cost["third_rung_status"] == "NOT_MEASURED_STOP_RECOMMENDATION"
    assert cost["effective_throughput_measured"] is None
    assert cost["setup_helpers_failures_included"] is False
    assert cost["all_in_under_100_eur_demonstrated"] is False


def test_maximum_attempt_and_rental_arithmetic_are_not_vcpu_speed_claims():
    cost = PANEL["cost"]
    maximum = next(s for s in cost["scenarios"] if s["name"] == "A_B_max")
    assert maximum["standard"] == maximum["rung2"] == 360
    assert maximum["rung3"] == (
        PANEL["stage_A"]["max_new_rung3"] + PANEL["stage_B"]["max_new_rung3"]
    )
    rental = Decimal(maximum["cpu_h"]) * Decimal(cost["ccx63_eur_per_billed_node_h"])
    assert rental == Decimal("88.913")
    assert rental / 8 == Decimal("11.114125")
    assert "48 vCPUs is not S=48" in TEXT
    assert "All five bands remain" in TEXT
