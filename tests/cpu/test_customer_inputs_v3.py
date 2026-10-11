"""Prospective customer specifications; public/static and synthetic checks only."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from carbon.battery.reference import SPEC
from carbon.design_search import tasks

ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "docs/development/challenge_pipeline"
LAW = json.loads(
    (PIPELINE / "question-laws/battery-continuous-v3.json").read_text(encoding="utf-8")
)
PANEL = json.loads(
    (PIPELINE / "round1/cooling-spreader-panel-v2.json").read_text(encoding="utf-8")
)
REC = PANEL["recommendation"]


@pytest.mark.parametrize("sheet", [LAW, PANEL])
def test_proposals_cannot_register_or_dispatch(sheet):
    assert sheet["ticket"] == "CHALLENGE-CUSTOMER-INPUTS-03"
    assert sheet["maturity"] == "SPECIFIED"
    assert sheet["runtime_registration"] is False
    assert sheet["protected_material"] is False
    assert sheet["spend_grant"] is None
    if sheet is PANEL:
        assert sheet["status"] == "HUMAN_INPUT"
        assert sheet["dispatch_ready"] is False
        for pin in (
            "accepted_stack",
            "accepted_package_pins",
            "accepted_case_manifest",
        ):
            assert sheet[pin] is None
    else:
        assert sheet["historical_rescore"] is False
        assert sheet["primary_variant"]["status"] == "OWNER_SELECTED_DEVELOPMENT"
        assert sheet["primary_variant"]["runtime_registered"] is False
        for law in ("registered_P", "registered_Q", "registered_w"):
            assert sheet[law] is None


@pytest.mark.parametrize(
    ("relative", "expected"),
    [
        (
            "question-laws/proposals-v2.json",
            "8466a835c23df62aa09112904545a3cc247f3f15fc0692d65c265fdfe6d7c2ee",
        ),
        (
            "question-laws/foundation-quiz-proposals.json",
            "6f9bb6047307ca0d68fa8bc692fd44b030f17b9a9aba43d629eeb5739f675360",
        ),
        (
            "optimizers/battery-ev-fast-charge.md",
            "46f6012bf3719211d8354bdf78f2bc72a70fdab512cb084b2b2a12b0216c6c5b",
        ),
        (
            "round1/cooling-cell-v2.md",
            "885c88ab5985b320972b51ba41ff4fc10dd8f5de331743b252b1acdb85f2fb84",
        ),
    ],
)
def test_history_and_other_laws_preserved(relative, expected):
    content = (PIPELINE / relative).read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(content).hexdigest() == expected


def test_spreader_joint_units_and_bulk_lower_bounds():
    assert REC["lid"]["thickness_mm"] == 1.5
    assert REC["lid"]["footprint_mm"] == [30, 30]
    assert REC["tim1"]["effective_r_m2k_w"] == pytest.approx(0.0514 * 1e-4)
    assert REC["tim2"]["effective_r_range_m2k_w"] == pytest.approx(
        [0.04 * 1e-4, 0.08 * 1e-4]
    )
    for name, thickness in (
        ("tim1", "thickness_um"),
        ("tim2", "conditioned_thickness_um"),
    ):
        joint = REC[name]
        bulk = joint[thickness] * 1e-6 / joint["bulk_k_w_mk"]
        assert bulk <= joint["effective_r_m2k_w"]
    # A sensitivity range is not permission to use every Cartesian pairing.
    thick_pcm_bulk = 50e-6 / REC["tim2"]["bulk_k_w_mk"]
    assert thick_pcm_bulk > min(REC["tim2"]["effective_r_range_m2k_w"])
    assert "no double counting" in REC["joint_rule"]


def test_panel_counts_include_controls_refinement_and_witnesses():
    geometry = REC["geometry_product"]
    actions = len(geometry["channel_width_mm"]) * len(geometry["channel_depth_mm"])
    assert actions == 6
    assert actions * len(REC["contexts"]) == REC["base_cases"] == 30
    subset = REC["difficult_subset"]
    assert (
        len(subset["channel_width_mm"]) * len(subset["contexts"])
        == subset["cases"]
        == 6
    )
    assert (
        subset["cases"] * REC["extra_refinement_rungs"] == REC["extra_refinement_jobs"]
    )
    total = (
        REC["base_cases"]
        + len(REC["verification_controls"])
        + REC["extra_refinement_jobs"]
        + REC["repeating_cell_3d_coupled_witness_jobs"]
    )
    assert total == REC["total_logical_jobs"] == 53
    assert REC["charged_solver_invocations"] is REC["cpu_hours"] is None
    assert REC["geometry_product"]["channel_cover_mm"] != REC["lid"]["thickness_mm"]
    assert "NO_FULL_PLATE" in PANEL["scope"]


def test_panel_contexts_cannot_smuggle_a_solved_interface_ratio():
    for context in REC["contexts"]:
        assert "raw_hotspot_ratio" in context
        assert "post_spreader_ratio" not in context
        flow = context["heat_load_w"] / 1000 * REC["flow_lpm_per_kw"]
        assert flow <= 3
        assert 30 <= context["inlet_c"] <= 45
    assert REC["coupling"]["universal_fixed_map_accepted"] is False
    assert "TABULATED_FLUX_NOT_GAUSSIAN_FIT" in REC["map_support"]
    assert REC["verification"]["decision_agreement_threshold"] is None
    assert "NOT_CANDIDATE_FAILURE" in REC["missing_support_outcome"]
    assert REC["alternatives"] == "REPORT_ONLY_NOT_SELECTED"
    assert len(set(PANEL["source_links"])) == 4


def test_battery_service_inputs_match_declared_reference_not_aged_claims():
    population = LAW["P_recommendation"]
    ambient = population["ambient_mix"]
    alpha_total = sum(ambient["alpha"])
    assert [a / alpha_total for a in ambient["alpha"]] == ambient["expected_mix"]
    assert sum(ambient["expected_mix"]) == pytest.approx(1)
    assert ambient["all_five_hard_limits_required"] is True
    assert ambient["unsolved_temperature_interpolation"] is False
    assert all(
        SPEC["input_bounds"]["t_amb_c"][0] <= t <= 40 for t in ambient["support_c"]
    )
    soc = population["start_soc"]
    assert soc["reference_declared_bounds"] == SPEC["input_bounds"]["soc0"]
    assert all(0.05 <= value <= 0.5 for value in soc["values"])
    assert sum(soc["mass"]) == pytest.approx(1)
    assert population["ageing_state"]["law"] == "POINT_MASS"
    assert population["ageing_state"]["mass"] == 1
    assert LAW["aged_extension"]["initial_state_manifest"] is None
    assert "BLOCKED_REFERENCE_SUPPORT" in LAW["aged_extension"]["status"]


def test_continuous_margins_strengthen_anchors_without_time_cap():
    axes = {a["quantity"]: a for a in LAW["P_recommendation"]["requirements"]}
    assert set(axes) == {"charging_thermal_margin", "charging_plating_margin"}
    thermal = axes["charging_thermal_margin"]
    plating = axes["charging_plating_margin"]
    assert thermal["interval"] == [0, 2.5] and thermal["anchor_limit"] == 45
    assert plating["interval"] == [0, 0.002] and plating["anchor_limit"] == 0
    assert 45 - max(thermal["interval"]) == 42.5
    assert min(plating["interval"]) >= 0
    assert LAW["objective"]["sense"] == "min"
    assert LAW["objective"]["hard_time_max"] is None
    assert LAW["time_observer"]["anchor_soc"] == 0.1
    assert LAW["time_observer"]["initial_rest_s_included"] == 120
    assert (
        "PROSPECTIVE_OBSERVER_REQUIRED" in LAW["time_observer"]["variable_soc_status"]
    )


def test_four_grid_vectors_are_a_separate_audit_not_eight_questions():
    grid = LAW["audit_grid"]
    assert grid["status"] == "AUDIT_ONLY_NOT_PRIMARY"
    assert math.prod(len(v) for v in grid["requirements"].values()) == 4
    assert grid["raw_combinations"] == grid["distinct_grid_vectors_upper_bound"] == 4
    assert grid["same_population_as_primary"] is False
    assert grid["plating_floor_v"] == 0
    assert LAW["diversity"]["questions_per_batch"]["recommendation"] == 8


def test_p_q_w_and_expected_occupancy_remain_separate():
    diagnostic = LAW["Q_recommendation"]
    assert sum(
        diagnostic[k]
        for k in (
            "interior_mass",
            "thermal_or_plating_edge_mass",
            "objective_pick_flip_mass",
        )
    ) == pytest.approx(1)
    assert diagnostic["redraw_none_feasible"] is False
    assert LAW["w_recommendation"]["buyer_ambient_mix_is_evidence_weight"] is False
    diversity = LAW["diversity"]
    for field in (
        "expected_distinct_winners_P",
        "expected_distinct_winners_Q",
        "feasible_mix_P",
        "none_feasible_mix_P",
        "unresolved_mix_P",
        "close_call_rate_P",
        "close_call_rate_Q",
        "residual_unresolved_rate",
    ):
        assert diversity[field] is None
    assert diversity["distinct_winners_bounds_k8"] == [0, 8]
    assert "NO_REDRAW" in diversity["none_feasible"]
    # Toy occupancy, not a claim about any physical solved bank.
    expected = sum(1 - (1 - p) ** 8 for p in (0.5, 0.5))
    assert expected == 1.9921875
    assert sum(1 - (1 - p) ** 8 for p in (0,)) == 0


def test_cost_arithmetic_does_not_transfer_historical_solver_price():
    cost = LAW["bank_cost"]
    assert (
        math.prod(
            cost[k]
            for k in (
                "candidates_recommendation",
                "ambient_contexts",
                "soc_contexts",
                "initial_age_states",
            )
        )
        == cost["base_programmes"]
        == 1500
    )
    assert cost["cpu_hours"] is cost["refinement_programmes"] is None
    assert cost["threshold_only_incremental_solves"] == 0
    assert cost["historical_quiz"]["applies_to_revised_bank"] is False
    assert set(LAW["unchanged_laws"]) == {
        "cooling-cell",
        "motor",
        "burst-thermal",
        "grating-coupler",
        "resonance-structure",
        "compressor-silencer",
        "passive-micromixer",
    }


def test_synthetic_task_projection_rejects_unsafe_speed_and_has_no_deadline():
    identity = {
        "challenge": "synthetic-only",
        "contract_version": "toy.v1",
        "action_grammar": "toy.v1",
        "optimizer": "exhaustive.v1",
        "query_budget": 4,
        "seed": 0,
        "observer_version": "toy.v1",
        "reference_bank": "toy.v1",
    }
    task = tasks.task(
        "toy-time-objective",
        identity=identity,
        conditions=[{"id": "warm", "stratum": "service"}],
        strata={"service": {"p": 1, "q": 1, "w": 1}},
        candidates=["unsafe-fast", "safe-slower", "safe-faster"],
        objective={
            "quantity": "session_min",
            "unit": "min",
            "sense": "min",
            "aggregate": "worst",
        },
        limits=[{"quantity": "charge_c", "unit": "degC", "op": "<=", "value": 45}],
    )
    # Discharge is not used as the charge temperature; all timings exceed30min.
    rows = {
        ("unsafe-fast", "warm"): {"session_min": 31, "charge_c": 46, "discharge_c": 40},
        ("safe-slower", "warm"): {"session_min": 42, "charge_c": 44, "discharge_c": 54},
        ("safe-faster", "warm"): {"session_min": 36, "charge_c": 43, "discharge_c": 52},
    }
    committed = tasks.commit(task, rows, model_id="synthetic-model")
    result = tasks.judge(task, committed, rows)
    assert result["kind"] == "SELECTED_FEASIBLE"
    assert committed["selected"] == "safe-faster"


def test_spec_handoff_names_support_and_uncertainty_seams():
    cooling = (PIPELINE / "round1/cooling-spreader-v2.md").read_text(encoding="utf-8")
    battery = (PIPELINE / "question-laws/battery-continuous-v3.md").read_text(
        encoding="utf-8"
    )
    optimizer = (PIPELINE / "optimizers/battery-ev-fast-charge-v2.md").read_text(
        encoding="utf-8"
    )
    for phrase in (
        "owner approval pending",
        "candidate's",
        "3D lid",
        "UNRESOLVED",
        "not die junction",
        "HUMAN_INPUT",
        "No runs or spend",
    ):
        assert phrase in cooling
    for phrase in (
        "point mass",
        "No redraws",
        "four-vector audit",
        "NOT_DEMONSTRATED",
        "UNMEASURED",
        "(a)",
        "(e)",
    ):
        assert phrase in battery
    for phrase in (
        "No30-minute cap",
        "validators rebuild/score",
        "NONE_FEASIBLE",
        "UNRESOLVED",
        "#815",
        "#808",
    ):
        assert phrase in optimizer
    assert "battery-continuous-v3.md" in (
        PIPELINE / "question-laws/README.md"
    ).read_text(encoding="utf-8")
    assert "battery-ev-fast-charge-v2.md" in (
        PIPELINE / "optimizers/README.md"
    ).read_text(encoding="utf-8")


def test_synthetic_buyer_mix_can_change_pick_without_new_physical_truth():
    # Toy settled times only; no claim these are physical Battery protocols.
    times = {"a": (20, 40), "b": (25, 30)}

    def pick(mix):
        return min(
            times,
            key=lambda action: sum(
                weight * value for weight, value in zip(mix, times[action])
            ),
        )

    assert pick((0.8, 0.2)) == "a"
    assert pick((0.2, 0.8)) == "b"
    # Even a small buyer frequency must not average away a hard safety breach.
    temperatures = {"a": (40, 46), "b": (43, 44)}
    admissible = [
        action for action, values in temperatures.items() if max(values) <= 45
    ]
    assert admissible == ["b"]


def test_synthetic_tim_peak_uses_colocated_map_not_unrelated_maxima():
    # Invented two-point fields exercise units/coordinates, not physical truth.
    face_c = [80, 60]
    flux_w_m2 = [1e6, 3e6]
    resistance = 5e-6
    composed_peak = max(t + resistance * q for t, q in zip(face_c, flux_w_m2))
    assert composed_peak == 85
    assert max(face_c) + resistance * max(flux_w_m2) == 95
