"""Planning consistency, not reference evidence, customer acceptance or a grader."""

from __future__ import annotations

import ast
import json
import math
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKETS = ROOT / "docs/development/challenge_pipeline/round1"
SHEET = PACKETS / "first-three-requirements.json"
SECTIONS = [
    "Engineering job",
    "Physical system",
    "Population P, Q and w",
    "Case contract",
    "Reference policy",
    "Output and measurement contract",
    "Construction contract",
    "Research kit",
    "Evidence plan",
    "Readiness and claim record",
]


@pytest.fixture
def sheet():
    return json.loads(SHEET.read_text(encoding="utf-8"))


def literal_assignment(relative_path, name, *, fields=None):
    """Read only public source constants, never run a solver or access evidence."""
    tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            if fields is not None:
                assert isinstance(node.value, ast.Dict)
                return {
                    ast.literal_eval(key): ast.literal_eval(value)
                    for key, value in zip(
                        node.value.keys, node.value.values, strict=True
                    )
                    if ast.literal_eval(key) in fields
                }
            return ast.literal_eval(node.value)
    raise AssertionError(f"missing public source constant {name}")


def test_planning_has_no_execution_score_qualification_or_spend_authority(sheet):
    assert sheet["purpose"] == "MOCK_CUSTOMER_REQUIREMENTS_NOT_EXECUTION_AUTHORITY"
    assert sheet["authority"] == "OWNER-FIRST-THREE-CUSTOMER-ROUND-01"
    assert sheet["development_order"] == ["motor", "cooling", "battery"]
    assert list(sheet["packets"]) == sheet["development_order"]
    for field in (
        "dispatch_ready",
        "official_scoring",
        "scientific_qualification",
        "protocol_transition",
    ):
        assert sheet[field] is False
    assert sheet["spend_grant"] is None
    assert sheet["deployment_population"] == "HUMAN_INPUT"
    assert sheet["economic_basis"] == "HYPOTHETICAL_ASSUMPTIONS_NOT_OBSERVED_VALUE"
    for packet in sheet["packets"].values():
        assert packet["reference_adequacy"] == "NOT_DEMONSTRATED_FOR_NEW_BUYER_DECISION"


@pytest.mark.parametrize("name", ["motor", "cooling", "battery"])
def test_packets_keep_ten_sections_and_local_links(sheet, name):
    path = PACKETS / sheet["packets"][name]["file"]
    body = path.read_text(encoding="utf-8")
    headings = re.findall(r"^## (\d+)\. (.+)$", body, re.MULTILINE)
    assert headings == [(str(i), title) for i, title in enumerate(SECTIONS, 1)]
    for token in ("Role-play", "DEVELOPMENT", "HUMAN_INPUT", "UNRESOLVED"):
        assert token in body
    for target in re.findall(r"\]\(([^)]+)\)", body):
        if not target.startswith("https://"):
            assert (path.parent / target.split("#", 1)[0]).is_file(), target


def test_all_selected_numeric_fields_are_finite_not_booleans(sheet):
    def check(value):
        if isinstance(value, dict):
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)
        elif type(value) in (int, float):
            assert math.isfinite(value)
        else:
            assert isinstance(value, str)

    for packet in sheet["packets"].values():
        # Metadata flags are separate; no Boolean may stand in for a limit or rate.
        for field in ("limits", "cost_assumptions", "reference_checks"):
            check(packet[field])


def test_motor_load_ripple_and_cogging_are_buyer_allocations(sheet):
    motor = sheet["packets"]["motor"]
    load, limits = motor["load_assumptions"], motor["limits"]
    required = (
        load["payload_kg"] * load["gravity_m_s2"] * load["lever_m"]
        + load["tool_link_torque_nm"]
    ) * load["load_multiplier"]
    assert required == pytest.approx(5.9316)
    assert limits["holding_mean_nm_min"] == math.ceil(required) == 6
    assert limits["peak_mean_nm_min"] == 12
    assert limits["energized_ripple_pp_fraction_max"] == 0.05
    assert limits["holding_ripple_pp_nm_max"] == pytest.approx(6 * 0.05)
    assert limits["peak_ripple_pp_nm_max"] == pytest.approx(12 * 0.05)
    tip_um = (
        limits["holding_ripple_pp_nm_max"]
        / load["joint_torsional_stiffness_nm_rad"]
        * load["lever_m"]
        * 1e6
    )
    assert tip_um == pytest.approx(6)
    assert tip_um < limits["tip_motion_pp_um_context_only_max"]
    assert limits["unpowered_cogging_pp_nm_max"] == 0.05
    assert motor["synthetic_panel"]["unpowered_metric"].endswith("NO_MEAN_DIVISION")


def test_motor_commands_and_refinement_bind_existing_public_geometry_scope(sheet):
    motor = sheet["packets"]["motor"]
    panel = motor["synthetic_panel"]
    bounds = literal_assignment("carbon/motor/domain.py", "INPUT_BOUNDS")
    commands = panel["precision_j_a_mm2"] + panel["peak_j_a_mm2"]
    assert all(bounds["current_density_a_mm2"][0] <= j <= 15 for j in commands)
    assert all(0 <= angle <= 60 for angle in panel["energized_angle_deg"])
    queries = len(commands) * len(panel["energized_angle_deg"]) + 1
    assert motor["deployment_targets_unmeasured"]["queries_per_design"] == queries == 9
    checks = motor["reference_checks"]
    assert checks["angle_refinement_counts"] == [60, 120, 240]
    for angles, nodes in zip(
        checks["angle_refinement_counts"],
        checks["compatible_min_gap_nodes"],
        strict=True,
    ):
        period_nodes = nodes * 15 // 360
        assert period_nodes % angles == 0


def test_cooling_power_and_tim_units_are_full_assembly_not_cell_relabel(sheet):
    cooling = sheet["packets"]["cooling"]
    limits, allocation = cooling["limits"], cooling["allocation_assumptions"]
    q_m3_s = limits["assembly_flow_lpm_max"] / 1000 / 60
    assert q_m3_s == pytest.approx(0.00005)
    assert limits["assembly_pressure_drop_pa_max"] * q_m3_s == pytest.approx(2.5)
    assert limits["assembly_hydraulic_w_max"] == 2.5
    assert limits["die_peak_c_max"] == 85
    assert allocation["channel_pressure_pa"] + allocation["header_pressure_pa"] == 50000
    assert limits["pressure_scope"] == "FULL_PLATE_AND_INLET_OUTLET_MANIFOLDS"
    assert "TOTAL_PRESSURE" in limits["pressure_observer"]
    assert "LOCAL_FLUX_TIM" in limits["thermal_observer"]
    area_m2 = (allocation["heated_side_mm"] / 1000) ** 2
    tim_k_w = allocation["tim_areal_m2_k_w"] / area_m2
    assert tim_k_w * 1500 == pytest.approx(8.3333333333)
    assert (limits["die_peak_c_max"] - 45) / 1500 == pytest.approx(0.02666666667)


def test_cooling_service_panel_does_not_clamp_low_supply_into_old_support(sheet):
    cooling = sheet["packets"]["cooling"]
    panel = cooling["synthetic_panel"]
    assert len(panel) == len({case["name"] for case in panel}) == 6
    assert panel[-1]["flow_factor"] == 0.625
    coefficients = [
        a * panel[-1]["flow_factor"] for a in cooling["flow_actions_lpm_per_kw"]
    ]
    assert coefficients == [0.78125, 0.9375, 1.25]
    assert cooling["reference_checks"]["flow_loss_outside_existing_support"] == (
        "UNRESOLVED_NOT_CLAMPED"
    )
    assert (
        max(
            a * case["flow_factor"] * case["heat_w"] / 1000
            for case in panel
            for a in cooling["flow_actions_lpm_per_kw"]
        )
        == 3
    )


def test_battery_retains_scope_and_makes_18_min_goal_unavailable_not_falsely_passed(
    sheet,
):
    battery = sheet["packets"]["battery"]
    scope, limits = battery["current_scope"], battery["limits"]
    public_spec = literal_assignment(
        "carbon/battery/reference.py",
        "SPEC",
        fields={"input_bounds", "initial_rest_s", "v_max"},
    )
    assert scope["c1_c_bounds"] == public_spec["input_bounds"]["c1"]
    assert scope["c2_c_bounds"] == public_spec["input_bounds"]["c2"]
    assert scope["initial_rest_s"] == public_spec["initial_rest_s"] == 120
    assert scope["cycles"] == 30
    assert scope["capacity_checkpoints"] == [1, 10, 20, 30]
    lower_bound_s = (scope["target_soc"] - scope["initial_soc"]) * scope[
        "screen_soc_capacity_over_rate_capacity_assumption"
    ] / max(scope["c1_c_bounds"]) * 3600 + scope["initial_rest_s"]
    assert lower_bound_s == pytest.approx(1380)
    assert scope["market_context_session_s_not_supported"] < lower_bound_s
    assert lower_bound_s < limits["warm_10_80_session_s_max"] == 1800
    assert limits["temperature_c_max"] == 45
    assert limits["plating_reaction_overpotential_v_min"] == 0
    assert limits["terminal_voltage_v_max"] == public_spec["v_max"]
    assert limits["q30_over_q1_min"] == 0.99
    assert scope["timing_observer"].startswith("NEEDED_PROSPECTIVE")
    assert scope[
        "all_cycle_temperature_voltage_and_charge_plating_observer"
    ].startswith("NEEDED_NOT_CURRENT")
    assert [p["ambient_c"] for p in battery["synthetic_panel"]] == [5, 15, 25, 35, 40]
    assert [
        p["ambient_c"]
        for p in battery["synthetic_panel"]
        if p["warm_time_target_applies"]
    ] == [25, 35]


def test_hypothetical_value_and_wrong_decision_units_reconcile(sheet):
    motor = sheet["packets"]["motor"]["cost_assumptions"]
    assert motor["stop_h"] * motor["line_usd_h"] + motor["scrap_usd"] == 640
    assert (
        motor["redo_engineer_h"] * motor["engineer_usd_h"] + motor["prototype_usd"]
        == 3600
    )
    assert motor["saved_engineer_h_per_revision"] * motor["engineer_usd_h"] == 900
    cooling = sheet["packets"]["cooling"]["cost_assumptions"]
    assert (
        cooling["redo_engineer_h"] * cooling["engineer_usd_h"]
        + cooling["prototype_usd"]
        == 7600
    )
    assert (
        cooling["stop_h"] * cooling["accelerators"] * cooling["accelerator_usd_h"] == 48
    )
    assert cooling["saved_engineer_h_per_revision"] * cooling["engineer_usd_h"] == 1200
    saving = (
        cooling["illustrative_electric_saving_w"]
        / 1000
        * cooling["operation_h_year"]
        * cooling["electricity_usd_kwh"]
    )
    assert saving == pytest.approx(2.628)
    battery = sheet["packets"]["battery"]["cost_assumptions"]
    assert battery["abort_min"] / 60 * battery["driver_usd_h"] == 7.5
    session_value = (
        (
            battery["previous_session_min_if_measured"]
            - battery["improved_session_min_if_verified"]
        )
        / 60
        * battery["driver_usd_h"]
    )
    assert session_value == 2.5
    assert (
        session_value
        * battery["vehicles"]
        * battery["sessions_day"]
        * battery["operation_days_year"]
        == 25000
    )


@pytest.mark.parametrize(
    "name,p95,designs,queries",
    [
        ("motor", "warm_p95_curve_s_max", "proposed_designs", "queries_per_design"),
        ("cooling", "warm_p95_case_s_max", "proposed_designs", "queries_per_design"),
        (
            "battery",
            "warm_p95_trajectory_s_max",
            "proposed_protocols",
            "queries_per_protocol",
        ),
    ],
)
def test_unmeasured_inference_throughput_targets_reconcile(
    sheet, name, p95, designs, queries
):
    target = sheet["packets"][name]["deployment_targets_unmeasured"]
    assert (
        target[p95] * target[designs] * target[queries]
        == target["inference_batch_s_max"]
    )
    assert target["inference_batch_s_max"] < target["shortlist_elapsed_s_max"]
