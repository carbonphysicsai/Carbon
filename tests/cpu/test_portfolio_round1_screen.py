"""The planning screen checks its basis; it does not qualify any reference."""

from __future__ import annotations

import copy
import json

import pytest

from scripts.dev.portfolio_round1_screen import (
    SHEET,
    _rc_peak,
    screen,
    validate_allowances,
)


@pytest.fixture
def sheet():
    return json.loads(SHEET.read_text(encoding="utf-8"))


def test_allowances_reconcile_and_no_execution_authority(sheet):
    result = screen(sheet)
    assert result["basis"] == "OFFLINE_ANALYTICAL_SCREEN_NOT_REFERENCE_EVIDENCE"
    assert result["examined"] == {"challenge_count": 5, "grant_count": 5}
    assert result["allowance_totals"] == {
        "usd": 160,
        "allocated_node_hours": 46,
        "allocated_vcpu_hours": 736,
        "maximum_attempts": 202,
    }
    assert all("cannot_establish" in result[f] for f in sheet["challenges"])


@pytest.mark.parametrize(
    "field", ["dispatch_ready", "official_scoring", "protocol_transition"]
)
def test_screen_refuses_to_be_reused_as_authority(sheet, field):
    sheet[field] = True
    with pytest.raises(ValueError, match="cannot authorize"):
        screen(sheet)


@pytest.mark.parametrize("value", [-1, 0, True, float("nan"), float("inf")])
def test_invalid_allowance_fails_closed(sheet, value):
    sheet["challenges"]["f02"]["grant"]["node_hours"] = value
    with pytest.raises(ValueError, match="invalid grant"):
        validate_allowances(sheet)


def test_retry_and_total_changes_cannot_silently_expand_round(sheet):
    retry = copy.deepcopy(sheet)
    retry["challenges"]["f06"]["grant"]["automatic_retries"] = 1
    with pytest.raises(ValueError, match="zero retries"):
        validate_allowances(retry)
    sheet["aggregate"]["usd"] += 1
    with pytest.raises(ValueError, match="aggregate"):
        validate_allowances(sheet)


def test_adequacy_is_not_a_screen_result(sheet):
    sheet["challenges"]["f17"]["reference_adequacy"] = "ADEQUATE"
    with pytest.raises(ValueError, match="adequacy needs evidence"):
        screen(sheet)


@pytest.mark.parametrize(
    "field", ["memory_gib", "node_hours", "usd", "attempts", "timeout_s"]
)
def test_raising_family_caps_and_totals_together_is_refused(sheet, field):
    sheet["challenges"]["f13"]["grant"][field] += 1
    if field == "usd":
        sheet["aggregate"]["usd"] += 1
    if field == "node_hours":
        sheet["aggregate"]["allocated_node_hours"] += 1
        sheet["aggregate"]["allocated_vcpu_hours"] += 16
    with pytest.raises(ValueError, match="approved .* ceiling"):
        validate_allowances(sheet)


def test_rc_selection_is_frozen_before_reference_and_not_a_safe_claim(sheet):
    thermal = sheet["challenges"]["f02"]["thermal"]
    assert thermal["cooling_regimes"] == [
        {"coolant_c": 30, "h_w_m2_k": 2500},
        {"coolant_c": 40, "h_w_m2_k": 1500},
    ]
    result = screen(sheet)["f02"]
    for family, selection in result["near_limit_actions"].items():
        assert selection["peak_w"] in thermal["peak_w"]
        assert selection["on_time_s"] in thermal["on_time_s"]
        assert (selection["peak_w"], selection["on_time_s"]) not in ((110, 10), (80, 5))
        assert selection["boundary_coverage"] in ("SCREEN_NEAR_ONLY", "GAP_UNRESOLVED")
        assert selection["rc_peak_c"] == _rc_peak(
            thermal,
            result["total_1d_resistance_k_w"][1],
            result["lumped_heat_capacity_j_k"],
            family,
            selection["peak_w"],
            selection["on_time_s"],
        )


def test_rc_constant_equilibrium_control_and_missing_boundary_coverage(sheet):
    thermal = sheet["challenges"]["f02"]["thermal"]
    thermal["initial_c"][1] = 60
    # R=1,C=1,Tcool=40,base=20 => exact equilibrium60.
    assert _rc_peak(thermal, 1, 1, "rectangular", 20, 5) == pytest.approx(60)
    thermal["limit_c"] = 1000
    assert all(
        v["boundary_coverage"] == "GAP_UNRESOLVED"
        for v in screen(sheet)["f02"]["near_limit_actions"].values()
    )


def test_thermal_screen_uses_each_layer_area_and_cooling_regime(sheet):
    result = screen(sheet)["f02"]
    assert result["lumped_heat_capacity_j_k"] == pytest.approx(6.73548)
    assert result["total_1d_resistance_k_w"] == pytest.approx(
        [0.5597578347578347, 0.856054131054131]
    )


def test_optical_support_remains_manufacturable_after_offsets(sheet):
    result = screen(sheet)["f06"]
    assert result["minimum_perturbed_line_space_nm"] == pytest.approx(182.4)
    assert (
        result["minimum_perturbed_line_space_nm"]
        >= sheet["challenges"]["f06"]["optical"]["minimum_feature_nm"]
    )
    assert result["minimum_remaining_si_nm"] == 80
    assert result["bare_cells_at_10nm_range"] == pytest.approx([572569600, 1195104000])


def test_structure_screen_reports_unribbed_control_not_dynamic_pass(sheet):
    result = screen(sheet)["f08"]
    assert 0.3 < result["nominal_sharp_relief_mass_kg"] < 0.4
    assert result["plain_beam_compliance_mm_n"] > 0
    assert 80 < result["plain_beam_first_mode_hz"] < 110
    assert "peaks" in result["cannot_establish"]


def test_acoustic_screen_distinguishes_duct_and_chamber_modes(sheet):
    result = screen(sheet)["f13"]
    assert result["duct_first_transverse_cutoff_hz"] > 2500
    assert all(f < 2500 for f in result["chamber_first_transverse_cutoff_hz"])


def test_mixer_screen_converts_microlitres_and_charges_no_flow_oracle(sheet):
    result = screen(sheet)["f17"]
    assert result["hydraulic_diameter_um"] == pytest.approx(150)
    assert result["reynolds_by_flow"][-1] == pytest.approx(0.4158333333333333)
    assert result["peclet_range"] == pytest.approx(
        [833.3333333333333, 16666.666666666668]
    )
    assert result["smooth_mean_residence_s_by_flow"] == pytest.approx([18, 6, 3.6])
    assert result["smooth_channel_pressure_pa_by_flow"][-1] == pytest.approx(
        42.19409282700422
    )


def test_every_packet_uses_the_ten_section_contract(sheet):
    expected = [
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
    for challenge in sheet["challenges"].values():
        packet = (SHEET.parent / challenge["packet"]).read_text(encoding="utf-8")
        headings = [line for line in packet.splitlines() if line.startswith("## ")]
        assert headings == [f"## {i}. {title}" for i, title in enumerate(expected, 1)]
