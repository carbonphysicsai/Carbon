"""Static panel conformance only; no reference timing or scientific evidence."""

from __future__ import annotations

import ast
import json
import math
import runpy
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/dev/customer_feasibility_panels.py"
DOCS = ROOT / "docs/development/challenge_pipeline/round1"


@pytest.fixture
def api(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    return runpy.run_path(str(SCRIPT))


@pytest.fixture
def sheet():
    return json.loads((DOCS / "requirements.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("challenge", ["f02", "f08", "f13"])
def test_thirty_unique_recipes_and_no_fabricated_measurements(api, sheet, challenge):
    before = deepcopy(sheet)
    result = api["panel"](challenge, sheet)
    assert sheet == before
    assert result == api["panel"](challenge, sheet)
    assert result["purpose"].endswith("NOT_EXECUTION_AUTHORITY")
    assert result["dispatch_ready"] is False
    assert result["solver_runs_performed"] == 0
    assert result["reference_adequacy"] == "NOT_DEMONSTRATED"
    assert set(result["required_pins"].values()) == {None}
    cases = result["cases"]
    assert len(cases) == len({r["definition_digest"] for r in cases}) == 30
    assert len({r["public_recipe_label"] for r in cases}) == 30
    for row in cases:
        assert row["status"] == "NOT_RUN"
        assert row["retained_artifacts"] is None
        assert set(row["measured_cost"]) == set(api["COST_FIELDS"])
        assert set(row["measured_cost"].values()) == {None}
        assert row["definition_digest"].startswith("sha256:")
    assert result["common_requirements_and_existing_caps"]["grant"] == (
        sheet["challenges"][challenge]["grant"]
    )


def test_recipe_and_panel_identities_bind_the_inputs(api, sheet):
    first = api["panel"]("f02", sheet)
    changed = deepcopy(sheet)
    changed["challenges"]["f02"]["thermal"]["layers"][0]["k_w_m_k"] = 129
    second = api["panel"]("f02", changed)
    assert first["source_sheet_digest"] != second["source_sheet_digest"]
    assert first["panel_definition_digest"] != second["panel_definition_digest"]
    # A per-row digest deliberately identifies variable recipe inputs only;
    # common material/contract identity is supplied by the whole-panel digest.
    assert (
        first["cases"][0]["definition_digest"]
        == second["cases"][0]["definition_digest"]
    )


def test_unknown_scope_and_cap_inflation_are_rejected(api, sheet):
    with pytest.raises(ValueError, match="unsupported"):
        api["panel"]("battery", sheet)
    changed = deepcopy(sheet)
    changed["challenges"]["f08"]["grant"]["attempts"] = 90
    with pytest.raises(ValueError, match="ceiling"):
        api["panel"]("f08", changed)
    changed = deepcopy(sheet)
    changed["dispatch_ready"] = True
    with pytest.raises(ValueError, match="authorize"):
        api["panel"]("f02", changed)


def test_thermal_panel_covers_every_stratum_and_frozen_screen_probes(api, sheet):
    rows = [r["definition"] for r in api["panel"]("f02", sheet)["cases"]]
    nominal = [r for r in rows if r["role"] == "stratum-nominal"]
    assert len(nominal) == 24
    strata = {
        (
            r["cooling"]["coolant_c"],
            r["cooling"]["h_w_m2_k"],
            r["initial_c"],
            r["left_power_fraction"],
            r["waveform_family"],
        )
        for r in nominal
    }
    assert len(strata) == 24
    assert {(r[0], r[1]) for r in strata} == {(30, 2500), (40, 1500)}
    assert all((r["peak_w"], r["on_time_s"]) == (110, 10) for r in nominal)
    selected = {
        r["waveform_family"]: (r["peak_w"], r["on_time_s"])
        for r in rows
        if r["role"] == "rc-selected-probe-NOT_TRUTH"
    }
    assert selected == {
        "rectangular": (80, 10),
        "ramp": (80, 20),
        "two-pulse": (140, 5),
    }


def test_waveforms_have_complete_horizon_event_and_energy_accounting(api, sheet):
    for row in api["panel"]("f02", sheet)["cases"]:
        case = row["definition"]
        segments = case["segments_start_end_s_power_start_end_w"]
        assert segments[0][:2] == [0, 20]
        assert segments[-1][1] == 120
        assert all(end > start for start, end, _, _ in segments)
        assert all(a[1] == b[0] for a, b in zip(segments, segments[1:]))
        energy_above_base = sum(
            (end - start) * ((p0 + p1) / 2 - 20) for start, end, p0, p1 in segments
        )
        expected = (case["peak_w"] - 20) * case["on_time_s"]
        if case["waveform_family"] == "ramp":
            expected /= 2
        assert energy_above_base == pytest.approx(expected)
        if case["waveform_family"] == "two-pulse":
            assert segments[2][1] - segments[2][0] == 10


def test_structures_use_ten_valid_geometries_and_three_complete_damping_tasks(
    api,
    sheet,
):
    rows = [r["definition"] for r in api["panel"]("f08", sheet)["cases"]]
    groups = {}
    bounds = sheet["challenges"]["f08"]["structure"]
    for row in rows:
        geometry = row["geometry"]
        key = tuple(geometry.values())
        groups.setdefault(key, []).append(row["modal_damping"])
        for name, value in geometry.items():
            assert bounds[name][0] <= value <= bounds[name][1]
        width, rib = geometry["width_mm"], geometry["rib_thickness_mm"]
        assert width / 4 - rib / 2 - 10 >= bounds["minimum_ligament_mm"]
        assert (geometry["length_mm"] - geometry["relief_length_mm"]) / 2 >= 6
    assert len(groups) == 10
    assert all(values == [0.005, 0.01, 0.02] for values in groups.values())


def test_silencer_full_band_geometry_panel_respects_packaging_and_clearance(
    api,
    sheet,
):
    result = api["panel"]("f13", sheet)
    assert "complete" in result["complete_task"]
    acoustic = sheet["challenges"]["f13"]["acoustic"]
    for row in result["cases"]:
        g = row["definition"]["geometry"]
        assert 55 <= g["radius_1_mm"] <= 70
        assert 55 <= g["radius_2_mm"] <= 70
        assert 40 <= g["length_1_mm"] <= 110
        assert 40 <= g["length_2_mm"] <= 110
        assert 10 <= g["neck_length_mm"] <= 50
        assert 0 <= g["neck_offset_mm"] <= 25
        assert g["length_1_mm"] + g["length_2_mm"] + g["neck_length_mm"] + 20 <= 300
        assert acoustic["neck_radius_mm"] + g["neck_offset_mm"] + 10 <= min(
            g["radius_1_mm"], g["radius_2_mm"]
        )
    # This cost task is 30 complete initial curves, not 30 single frequencies.
    points = (2500 - 500) // acoustic["grid_hz"] + 1
    assert points == 201
    assert 30 * points == 6030 > sheet["challenges"]["f13"]["grant"]["attempts"]


def test_midpoint_strata_are_permutations_not_outcome_adaptive(api, sheet):
    rows = api["panel"]("f13", sheet)["cases"][:27]
    for key in rows[0]["definition"]["geometry"]:
        assert len({r["definition"]["geometry"][key] for r in rows}) == 27


def test_offline_script_has_no_execution_or_write_surface():
    source = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not imports & {"subprocess", "requests", "os", "socket", "runpod"}
    assert not any(
        isinstance(node, ast.Attribute)
        and node.attr in {"write_text", "write_bytes", "mkdir", "unlink", "system"}
        for node in ast.walk(tree)
    )


def test_buyer_revision_keeps_limits_and_exposes_unsupported_claims():
    body = (DOCS / "customer-feasibility-revisions.md").read_text(encoding="utf-8")
    for text in (
        "6 N·m holding",
        "full-35-mm-stack-equivalent torque",
        "never apply 1/3 twice",
        "≤0.05 N·m",
        "≤85 °C",
        "**(a) Yes, under this packet:**",
        "complete declared 30-cycle programme, including discharge/rest",
        "NO_VERIFIED_FEASIBLE_PROTOCOL",
        "same cooling action throughout charge/rest/discharge",
        "NO_VERIFIED_FEASIBLE_DESIGN",
        "No paid or counted/fresh campaign ran",
    ):
        assert text in body
    assert (1 - (85 - 45) / (89 - 45)) * 100 == pytest.approx(9.0909, abs=0.0001)
    assert 1500 * 0.0005 / (391 * 0.03**2) == pytest.approx(2.13129, abs=0.00001)
    assert math.lcm(10, 12) == 60
    assert 0.7 / 2 * 60 + 2 == 23
