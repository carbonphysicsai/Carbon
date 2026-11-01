"""The F08 2.0 U-panel and edge-check payload: the cells, the ladder, the shards, the Roache rule and the judgements.
Pure planning and arithmetic on synthetic series; nothing is solved."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

CALCULIX = (
    Path(__file__).resolve().parents[2] / "scripts/dev/reference_packages/calculix"
)
sys.path.insert(0, str(CALCULIX))

import f08_deck_v2 as v2
import f08_v2_payload as payload


def test_the_u_panel_is_twelve_registered_interior_cases_with_the_alloy_cycled_four_each():
    cells = payload.u_panel(7)
    assert len(cells) == 12 and len({c["cell"] for c in cells}) == 12
    counts = {}
    for cell in cells:
        case = cell["case"]
        counts[case["alloy"]] = counts.get(case["alloy"], 0) + 1
        for name in v2.NEW_INPUTS:
            low, high = v2.RANGES[name]
            assert low <= case[name] <= high
        assert 180.0 <= case["length_mm"] <= 260.0 and 60.0 <= case["width_mm"] <= 100.0
    assert counts == {"6061-T6": 4, "4130-normalized": 4, "Ti-6Al-4V-annealed": 4}
    assert (
        payload.u_panel(7) == cells and payload.u_panel(8) != cells
    )  # deterministic in the seed


def test_the_edge_cells_are_eight_edges_three_alloy_corners_and_the_pad_corner():
    cells = payload.edge_cells()
    kinds = [c["kind"] for c in cells]
    assert (
        kinds.count("edge") == 8
        and kinds.count("corner") == 3
        and kinds.count("pad") == 1
    )
    edges = [c for c in cells if c["kind"] == "edge"]
    assert {c["case"]["alloy"] for c in edges} == {
        "6061-T6"
    }  # the lowest E: most in-band modes
    for name in v2.NEW_INPUTS:
        values = {c["case"][name] for c in edges}
        assert set(v2.RANGES[name]) <= values  # both ends of every new dimension
    for c in edges:
        assert all(c["case"][k] == payload.CENTRE[k] for k in v2.GEOMETRY)
    corners = [c for c in cells if c["kind"] == "corner"]
    assert {c["case"]["alloy"] for c in corners} == set(v2.ALLOYS)
    for c in corners:
        case = c["case"]
        assert case["fillet_radius_mm"] == 0.5 and case["load_angle_deg"] == 45.0
        assert case["load_offset_frac"] == 0.4 and case["damping_ratio"] == 0.005
    pad = next(c for c in cells if c["kind"] == "pad")["case"]
    assert pad["width_mm"] == 60.0 and pad["load_offset_frac"] == 0.4


def test_every_cell_has_the_five_solves_of_the_ladder_sharing_the_base_rung():
    cell = payload.edge_cells()[0]
    jobs = payload.ladder_jobs(cell)
    assert len(jobs) == 5
    keys = {(j["h_mm"], j["fillet_h_mm"]) for j in jobs}
    assert keys == {(3.4, 0.5), (1.7, 0.5), (0.85, 0.5), (1.7, 1.0), (1.7, 0.25)}
    assert payload.RATIO == 2.0 and payload.MESH_RUNGS[0] / payload.MESH_RUNGS[1] == 2.0


def test_the_plan_puts_the_one_job_smoke_first_and_the_shards_hold_inputs_only():
    document = payload.plan(7, shard_size=20)
    assert document["jobs"] == (12 + 12) * 5
    assert len(document["shards"][0]) == 1  # the heaviest job alone
    first = document["shards"][0][0]
    assert first["h_mm"] == 0.85 and first["fillet_h_mm"] in (0.5, 0.25, 1.0)
    ids = [j["job_id"] for shard in document["shards"] for j in shard]
    assert len(ids) == len(set(ids)) == document["jobs"]
    assert document["shards"][1][0]["kind"] == "u_panel"  # the panel before the edges
    text = json.dumps(document)
    for forbidden in ("peak_von_mises", "stress_ratio", "yield_mpa", "E_mpa"):
        assert (
            forbidden not in text
        )  # inputs only: no outputs, no alloy property values
    assert "HUMAN_INPUT until" in document["alloy_properties"]


def series(f_coarse, order, base=1.0):
    """Three values converging at ``order`` towards ``base`` with refinement ratio 2."""
    return tuple(base + 8.0 * (f_coarse) * (0.5 ** (order * k)) for k in range(3))


def test_the_roache_rule_recovers_the_order_and_the_estimate_of_a_clean_series():
    coarse, mid, fine = series(0.01, 2.0)
    r = payload.roache(coarse, mid, fine)
    assert r["monotone"] and r["order"] == pytest.approx(2.0)
    expected = 1.25 * abs(mid - fine) / (2**2.0 - 1)
    assert r["estimate"] == pytest.approx(expected)
    assert r["range"] == pytest.approx(coarse - fine)


@pytest.mark.parametrize(
    "values",
    [(1.0, 1.2, 1.1), (1.0, 1.1, 1.3), (1.0, 1.0, 1.0001)],
)
def test_a_non_monotone_or_slow_series_has_no_estimate_only_its_range(values):
    r = payload.roache(*values)
    if values[0] == values[1]:
        assert r["monotone"] is False
    assert r["estimate"] is None and not r["monotone"]
    assert r["range"] == pytest.approx(max(values) - min(values))
    assert payload.figure(r) == r["range"]


def test_an_exactly_constant_series_has_zero_error():
    r = payload.roache(5.0, 5.0, 5.0)
    assert r["monotone"] and r["estimate"] == 0.0 and payload.figure(r) == 0.0


def _results(cells, make):
    out = {}
    for cell in cells:
        rows = {}
        for axis, rungs in (
            ("mesh", payload.MESH_RUNGS),
            ("fillet", payload.FILLET_RUNGS),
        ):
            for index, rung in enumerate(rungs):
                key = (rung, 0.5) if axis == "mesh" else (1.7, rung)
                row = rows.setdefault(key, {})
                for output in payload.OUTPUTS:
                    row[output] = make(cell, axis, output, index)
        out[cell] = rows
    return out


def _clean(cell, axis, output, index):
    return 10.0 + (0.0 if output == "cad_mass_kg" else 0.4 * 0.5 ** (2 * index))


def test_u_is_the_largest_figure_over_the_panel_and_the_stop_rule_counts_bad_cells():
    cells = [f"U{i:02d}" for i in range(12)]
    good = payload.u_per_output(_results(cells, _clean), cells)
    assert not good["stop"] and good["failed_cells"] == []
    assert set(good["u"]) == set(payload.OUTPUTS) - payload.EXACT
    assert all(v > 0 for v in good["u"].values())

    def two_bad(cell, axis, output, index):
        if cell in ("U03", "U07") and output == "static_tip_mm_per_n":
            return (10.0, 10.6, 10.3)[index]  # non-monotone
        return _clean(cell, axis, output, index)

    bad = payload.u_per_output(_results(cells, two_bad), cells)
    assert bad["failed_cells"] == ["U03", "U07"] and bad["stop"] is True

    def one_bad(cell, axis, output, index):
        if cell == "U03" and output == "static_tip_mm_per_n":
            return (10.0, 10.6, 10.3)[index]
        return _clean(cell, axis, output, index)

    assert payload.u_per_output(_results(cells, one_bad), cells)["stop"] is False


def test_a_missing_rung_is_a_failed_cell_and_a_changing_cad_mass_is_too():
    cells = [f"U{i:02d}" for i in range(12)]
    results = _results(cells, _clean)
    del results["U00"][(0.85, 0.5)]
    out = payload.u_per_output(results, cells)
    assert out["failed_cells"] == ["U00"]

    def mass_moves(cell, axis, output, index):
        if cell == "U05" and output == "cad_mass_kg":
            return 1.0 + index
        return _clean(cell, axis, output, index)

    assert (
        "U05"
        in payload.u_per_output(_results(cells, mass_moves), cells)["failed_cells"]
    )


def test_an_edge_cell_passes_against_u_when_its_figures_are_within_and_fails_with_the_overshoot():
    cells = [f"U{i:02d}" for i in range(12)]
    u = payload.u_per_output(_results(cells, _clean), cells)["u"]
    edge = ["E-fillet_radius_mm-low"]
    assert payload.judge_cell(_results(edge, _clean), edge[0], u)["passes"]

    def rough(cell, axis, output, index):
        if output == "dynamic_fillet_stress_mpa_per_n":
            return 10.0 + 3.0 * 0.5**index  # converges first order from far away
        return _clean(cell, axis, output, index)

    verdict = payload.judge_cell(_results(edge, rough), edge[0], u)
    assert not verdict["passes"]
    assert {o["output"] for o in verdict["over"]} == {"dynamic_fillet_stress_mpa_per_n"}


def test_a_failed_side_is_cut_inward_once_by_12_point_5_percent():
    assert payload.cut_side((0.5, 3.0), "low") == pytest.approx((0.5 + 0.3125, 3.0))
    assert payload.cut_side((0.5, 3.0), "high") == pytest.approx((0.5, 3.0 - 0.3125))
    assert math.isclose(payload.CUT, 0.125)
