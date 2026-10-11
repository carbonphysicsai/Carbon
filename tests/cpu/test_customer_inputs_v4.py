"""Public specification arithmetic and synthetic map semantics, never solvers."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from carbon.battery.reference import SPEC
from carbon.cold_plate.domain import pg25

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs/development/challenge_pipeline"
LAW = json.loads(
    (DOCS / "question-laws/battery-ambient-indexed-v3.json").read_text(encoding="utf-8")
)
BUDGET = json.loads(
    (DOCS / "round1/cooling-thermal-budget-v2.json").read_text(encoding="utf-8")
)
INPUT = BUDGET["inputs"]
ARITH = BUDGET["arithmetic"]


@pytest.mark.parametrize("sheet", [LAW, BUDGET])
def test_specification_cannot_activate_or_spend(sheet):
    assert sheet["ticket"] == "CHALLENGE-CUSTOMER-INPUTS-04"
    assert sheet["maturity"] == "SPECIFIED"
    assert sheet["runtime_registration"] is False
    assert sheet["protected_material"] is False
    assert sheet["spend_grant"] is None


@pytest.mark.parametrize(
    ("path", "digest"),
    [
        (
            "question-laws/battery-continuous-v3.json",
            "45e67ea9bd4bcdba7c71d72f51f16ae03817361d3db8d79c2fad76efa2d5b630",
        ),
        (
            "question-laws/proposals-v2.json",
            "8466a835c23df62aa09112904545a3cc247f3f15fc0692d65c265fdfe6d7c2ee",
        ),
        (
            "question-laws/foundation-quiz-proposals.json",
            "6f9bb6047307ca0d68fa8bc692fd44b030f17b9a9aba43d629eeb5739f675360",
        ),
        (
            "optimizers/battery-ev-fast-charge-v2.md",
            "278c96246a50950a9c3325ca77f9d9ec9f4cc8817125442876560965029f0ffd",
        ),
    ],
)
def test_old_law_optimizer_and_other_family_bytes_preserved(path, digest):
    content = (DOCS / path).read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(content).hexdigest() == digest


def test_cooling_panel_is_held_without_a_release_or_package():
    panel = json.loads(
        (DOCS / "round1/cooling-spreader-panel-v2.json").read_text(encoding="utf-8")
    )
    assert panel["dispatch_ready"] is False
    assert panel["panel_hold"] == BUDGET["panel_status"]
    assert panel["budget_release"] is BUDGET["panel_release"] is None
    assert panel["budget"] == "cooling-thermal-budget-v2.json"
    assert panel["accepted_package_pins"] is None
    assert panel["recommendation"]["total_logical_jobs"] == 53


def test_thermal_flux_and_coolant_are_dimensionally_consistent():
    area = math.prod(INPUT["footprint_mm"]) * 1e-6
    q = INPUT["power_w"] / area
    assert ARITH["average_flux_w_m2"] == pytest.approx(q)
    assert ARITH["raw_peak_flux_w_m2"] == pytest.approx(3 * q)
    rho = pg25("rho", INPUT["inlet_c"] + 273.15)
    cp = pg25("cp", INPUT["inlet_c"] + 273.15)
    rise = INPUT["power_w"] / (rho * cp * INPUT["flow_lpm"] / 60000)
    assert ARITH["coolant_rise_k_full_absorption"] == pytest.approx(rise)
    assert rise + ARITH["remaining_cell_rise_k"] == pytest.approx(28)


def test_interface_is_not_the_die_proxy_or_a_double_counted_plate():
    q = ARITH["average_flux_w_m2"]
    plate = INPUT["inlet_c"] + INPUT["bare_cell_rise_k_approx"]
    interface = plate + q * INPUT["r2_m2k_w"]
    lid = q * INPUT["lid_thickness_m"] / INPUT["lid_k_w_mk"]
    die = interface + lid + q * INPUT["r1_m2k_w"]
    assert ARITH["uniform_interface_c"] == pytest.approx(interface)
    assert ARITH["uniform_die_proxy_c"] == pytest.approx(die)
    assert interface < 85 < die
    assert BUDGET["current_limit_plane"] == "LID_SIDE_TIM2_INTERFACE"
    assert BUDGET["prospective_die_limit_selected"] is False
    # TIM1 is upstream; adding it to the interface silently changes the job.
    assert interface + q * INPUT["r1_m2k_w"] > 85


def test_hotspot_tim1_uses_raw_flux_even_when_downstream_is_flat():
    jump = ARITH["raw_peak_flux_w_m2"] * INPUT["r1_m2k_w"]
    assert jump == pytest.approx(25.7)
    assert ARITH["tim1_raw_hotspot_k"] == pytest.approx(jump)
    assert ARITH["ideal_redistributed_hot_die_proxy_c"] == pytest.approx(
        ARITH["uniform_interface_c"] + ARITH["lid_uniform_k"] + jump
    )
    assert ARITH["no_spread_hot_die_proxy_c"] == pytest.approx(
        INPUT["inlet_c"]
        + 28
        + 3 * ARITH["tim2_uniform_k"]
        + 3 * ARITH["lid_uniform_k"]
        + jump
    )


def test_old_postprocessed_tim_is_removed_before_new_budget():
    basis = BUDGET["basis"]
    bare = (
        basis["old_tim_interface_c"]
        - INPUT["inlet_c"]
        - ARITH["average_flux_w_m2"] * basis["old_tim_r_m2k_w"]
    )
    assert basis["bare_cell_rise_k_inferred"] == pytest.approx(bare)
    assert basis["is_panel_run"] is False
    assert basis["fin_mm"] != basis["panel_fin_mm"]


@pytest.mark.parametrize(
    "ratio,scenario", [(1, "uniform"), (3, "ideal_redistributed_hotspot")]
)
def test_buyer_levers_are_conditional_algebra_not_execution(ratio, scenario):
    r = ratio * INPUT["r1_m2k_w"] + INPUT["r2_m2k_w"]
    r += INPUT["lid_thickness_m"] / INPUT["lid_k_w_mk"]
    rise = 28 + ARITH["average_flux_w_m2"] * r
    lever = BUDGET["nominal_die_levers"][scenario]
    assert lever["inlet_max_c"] == pytest.approx(85 - rise)
    assert lever["limit_min_c"] == pytest.approx(45 + rise)
    assert lever["power_max_w_fixed_flow_linearized"] == pytest.approx(1500 * 40 / rise)
    assert lever["common_die_lid_area_min_mm2_fixed_plate_rise"] == pytest.approx(
        1500 * r / (40 - 28) * 1e6
    )
    assert BUDGET["panel_release"] is None


def test_sensitivity_does_not_convert_interface_possibility_to_die_pass():
    sensitivity = BUDGET["sensitivity"]
    q = ARITH["average_flux_w_m2"]
    copper_r = 0.0015 / 400
    assert sensitivity["favorable_uniform_die_proxy_c"] == pytest.approx(
        45 + 28 + q * (8e-6 + copper_r)
    )
    assert sensitivity["favorable_redistributed_hot_die_proxy_c"] == pytest.approx(
        45 + 28 + q * (16e-6 + copper_r)
    )
    assert sensitivity["favorable_uniform_interface_c"] < 85
    assert sensitivity["favorable_uniform_die_proxy_c"] > 85
    assert sensitivity["nominal_required_post_peak_mean_max"] == pytest.approx(
        (85 - 45 - 28) / ARITH["tim2_uniform_k"]
    )


def test_selected_map_and_weights_are_separate_from_numeric_population():
    decision = LAW["selected_decision"]
    assert decision["status"] == "OWNER_APPROVED_DEVELOPMENT"
    assert decision["ambient_anchors_c"] == [5, 15, 25, 35, 40]
    assert decision["shared_protocol_required"] is False
    assert decision["all_bands_mandatory"] is True
    assert decision["action_fields_per_band"] == [
        "c1",
        "c2",
        "switch_voltage_v",
        "cooling_level",
    ]
    assert LAW["P_recommendation"]["status"] == "HUMAN_INPUT"
    assert LAW["Q_recommendation"]["status"] == "HUMAN_INPUT"
    assert (
        LAW["registered_P"] is LAW["registered_Q"] is LAW["registered_outer_w"] is None
    )
    assert LAW["weights"]["band_value_weight"] == "OWNER_SELECTED_BUYER_AMBIENT_MIX"
    assert LAW["weights"]["band_weights_are_outer_population_weights"] is False
    assert LAW["Q_recommendation"]["redraw_none_feasible"] is False


def test_no_unsupported_action_socs_or_ageing_are_declared_registered():
    support = LAW["action_support"]
    assert support["accepted_bank"] is None
    assert support["current_runtime_has_switch_cooling_inputs"] is False
    assert support["current_runtime_c2_max"] == SPEC["input_bounds"]["c2"][1]
    assert support["public_study_c2_example"] > support["current_runtime_c2_max"]
    assert LAW["permit"] is None
    assert LAW["P_recommendation"]["ageing_state"]["independent_soh_input"] is False
    assert LAW["time_observer"]["initial_rest_s"] == 120
    assert (
        LAW["P_recommendation"]["start_soc"]["support_status"]
        == "OWNER_SELECTED_DEVELOPMENT"
    )
    assert (
        LAW["time_observer"]["variable_soc_status"]
        == "OWNER_SELECTED_DEVELOPMENT_COVERAGE_REQUIRED"
    )
    assert LAW["value_resolution"]["registered_delta_min"] is None


def test_feasible_map_existence_is_not_a_settled_optimum():
    evidence = LAW["public_evidence"]
    assert evidence["complete_feasible_map_with_cooling"] is True
    assert evidence["complete_feasible_map_protocol_only"] is False
    assert evidence["historical_pick_resolved"] == [False, False, False, False, True]
    assert evidence["all_band_optima_settled"] is False
    assert evidence["chosen_cooling_multipliers"] == [1, 1, 1, 4, 4]
    assert (
        evidence["cold_best_plating_v"]
        < LAW["P_recommendation"]["plating_margin_v"]["interval"][1]
    )


def test_cost_is_sum_of_band_inventories_not_cartesian_map_product():
    cost = LAW["cost"]
    assert sum(cost["per_band_inventory_contexts"]) == 414
    assert cost["three_soc_base_inventory_if_fully_rebuilt"] == 3 * 414
    assert cost["cpu_hours"] is None
    assert cost["historical_2684_at_90_cpu_s_is_v3_quote"] is False
    assert LAW["audit_grid"]["vectors"] == 4
    assert LAW["diversity"]["expected_distinct_winners_by_band"] == dict.fromkeys(
        ("T5", "T15", "T25", "T35", "T40")
    )
    assert LAW["diversity"]["mix_only_pick_changes"] == 0


def test_synthetic_separable_band_picks_do_not_change_with_positive_mix():
    times = ((20, 22), (34, 29), (40, 42), (31, 35), (49, 48))
    mixes = ((0.1, 0.15, 0.4, 0.25, 0.1), (0.4, 0.1, 0.1, 0.1, 0.3))
    winners = []
    for mix in mixes:
        winners.append(
            tuple(
                min(range(2), key=lambda j: weight * band[j])
                for weight, band in zip(mix, times)
            )
        )
    assert winners[0] == winners[1]
    assert sum(w * min(t) for w, t in zip(mixes[0], times)) != sum(
        w * min(t) for w, t in zip(mixes[1], times)
    )


def test_synthetic_low_weight_band_cannot_hide_hard_failure():
    limits = LAW["hard_anchor_limits"]
    temperatures = [44, 44, 44, 44, 46]
    weights = [0.24975, 0.24975, 0.24975, 0.24975, 0.001]
    assert sum(w * t for w, t in zip(weights, temperatures)) < 45
    assert not all(t <= limits["charging_temperature_max_c"] for t in temperatures)
    # Even zero weight does not remove a mandatory band's hard gate.
    assert LAW["selected_decision"]["all_bands_mandatory"]


def test_synthetic_equivalence_is_best_anchored_not_transitive_or_safety_slack():
    delta = LAW["value_resolution"]["recommendation_min"]
    times = [30.0, 30.4, 30.8]
    equivalent = [t for t in times if t - min(times) <= delta]
    assert equivalent == [30.0, 30.4]  # 30.4->30.8 does not chain the set.
    excess = max(0, times[-1] - min(times) - delta)
    assert excess == pytest.approx(0.3)
    regrets = [0 if t - min(times) <= delta else t - min(times) for t in times]
    assert regrets == pytest.approx([0, 0, 0.8])
    assert (
        LAW["task_projection"]["regret_rule_recommendation"]
        == "ZERO_WITHIN_DELTA_FULL_DIFFERENCE_OUTSIDE"
    )
    assert LAW["task_projection"]["indexed_task_owner_pr"] == 820
    assert LAW["value_resolution"]["unsafe_pick_can_be_equivalent"] is False


def test_indexes_point_to_current_versions_and_release_seam():
    assert "battery-ambient-map-v3.md" in (DOCS / "round1/README.md").read_text(
        encoding="utf-8"
    )
    assert "battery-ambient-indexed-v3.md" in (
        DOCS / "question-laws/README.md"
    ).read_text(encoding="utf-8")
    assert "battery-ambient-map-v3.md" in (DOCS / "optimizers/README.md").read_text(
        encoding="utf-8"
    )
    spreader = (DOCS / "round1/cooling-spreader-v2.md").read_text(encoding="utf-8")
    assert "Panel hold" in spreader
    assert "cooling-thermal-budget-v2.md" in spreader
