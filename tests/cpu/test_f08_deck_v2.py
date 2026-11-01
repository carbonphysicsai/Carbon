"""F08 2.0 deck (STRESS working choice): owner values refuse, the Gmsh program compiles, the stress reduction and the
closed-form controls are right on synthetic data. No solve, no Gmsh, no CalculiX is run.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import pytest

CALCULIX = (
    Path(__file__).resolve().parents[2] / "scripts/dev/reference_packages/calculix"
)
sys.path.insert(0, str(CALCULIX))

import f08_deck as v1
import f08_deck_v2 as v2

CASE = {
    "length_mm": 220.0,
    "width_mm": 60.0,
    "thickness_mm": 6.0,
    "rib_height_mm": 14.0,
    "rib_thickness_mm": 5.0,
    "relief_length_mm": 40.0,
    "fillet_radius_mm": 2.0,
    "load_angle_deg": 0.0,
    "load_offset_frac": 0.0,
    "damping_ratio": 0.01,
    "alloy": "TEST_ALLOY",
}
#: Clearly synthetic: never a registered range or alloy.
TEST_RANGES = {
    "fillet_radius_mm": (0.5, 4.0),
    "load_angle_deg": (-30.0, 30.0),
    "load_offset_frac": (-0.45, 0.45),
    "damping_ratio": (0.005, 0.02),
}
TEST_TABLE = {
    "TEST_ALLOY": {
        "E_mpa": 70000.0,
        "nu": 0.33,
        "rho_t_per_mm3": 2.7e-9,
        "yield_mpa": 100.0,
    }
}


def test_the_pinned_1_7_deck_is_untouched():
    digest = hashlib.sha256(
        (CALCULIX / "f08_deck.py").read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()
    assert digest == V1_SHA256


#: f08_deck.py on origin/main ae260371c2.
V1_SHA256 = "85b0388b49f8466b21f22f0a2705ec70125c902932dd280085df4b23338653a3"


def test_the_new_input_ranges_are_the_owner_registered_ones():
    assert v2.DECISION == "OWNER-F08-V2-VALUES-01"
    assert v2.RANGES == {
        "fillet_radius_mm": (0.5, 3.0),
        "load_angle_deg": (0.0, 45.0),
        "load_offset_frac": (-0.4, 0.4),
        "damping_ratio": (0.005, 0.02),
    }
    assert (
        v2.validate_case(CASE)["fillet_radius_mm"] == 2.0
    )  # in the registered ranges: no test mode needed
    for change in (
        {"fillet_radius_mm": 3.5},
        {"load_angle_deg": 60.0},
        {"load_angle_deg": -1.0},
        {"load_offset_frac": 0.5},
        {"damping_ratio": 0.03},
    ):
        with pytest.raises(v2.Refused, match="out_of_range"):
            v2.validate_case({**CASE, **change})


def test_a_range_that_is_human_input_refuses_unless_test_mode_supplies_it():
    open_ranges = {**v2.RANGES, "fillet_radius_mm": v2.HUMAN_INPUT}
    with pytest.raises(v2.Refused, match="range_not_registered_fillet_radius_mm"):
        v2.validate_case(CASE, ranges=open_ranges)
    assert (
        v2.validate_case(CASE, ranges=open_ranges, test_mode=True)["alloy"]
        == "TEST_ALLOY"
    )


@pytest.mark.parametrize(
    "change, code",
    [
        ({"fillet_radius_mm": 9.0}, "out_of_range"),
        ({"fillet_radius_mm": 0.1}, "out_of_range"),
        ({"rib_height_mm": 0.0}, "fillet_needs_a_rib"),
        ({"load_offset_frac": 0.4, "width_mm": 20.0}, "load_pad_leaves_the_plate"),
        ({"damping_ratio": 0.0}, "out_of_range"),
    ],
)
def test_an_out_of_range_case_is_refused(change, code):
    with pytest.raises(v2.Refused, match=code):
        v2.validate_case({**CASE, **change}, ranges=TEST_RANGES)


def test_a_fillet_larger_than_the_junction_is_refused():
    wide = {**TEST_RANGES, "fillet_radius_mm": (0.5, 20.0)}
    with pytest.raises(v2.Refused, match="fillet_radius_exceeds_the_junction"):
        v2.validate_case({**CASE, "fillet_radius_mm": 5.5}, ranges=wide)


ALLOY_SHA256 = "d5b8cc5638c3fa8d1bfd517b98d61c4735d59e3e6dd832c843e347dfd7b7fc10"
ALLOY_FILE = CALCULIX / "f08_v2_alloy_table.json"


def test_the_vendored_alloy_file_is_the_signed_one_and_the_deck_loads_its_values():
    raw = ALLOY_FILE.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(raw).hexdigest() == ALLOY_SHA256
    assert v2.ALLOY_SHA256 == "sha256:" + ALLOY_SHA256 and v2.ALLOY_STATUS == "SIGNED"
    assert v2.ALLOY_DECISION == "OWNER-F08-V2-ALLOYS-SIGNED-01"
    assert list(v2.ALLOYS) == ["6061-T6", "4130-normalized", "Ti-6Al-4V-annealed"]
    assert v2.SAFETY_FACTOR == 1.5
    assert v2.alloy_ids() == {
        "6061-T6": 0,
        "4130-normalized": 1,
        "Ti-6Al-4V-annealed": 2,
    }
    signed = {row["id"]: row for row in json.loads(raw)["alloys"]}
    for name, file_id in v2.ALLOY_FILE_IDS.items():
        row, got = signed[file_id], v2.ALLOYS[name]
        assert got["E_mpa"] == pytest.approx(row["E_GPa"] * 1000.0)
        assert got["nu"] == row["nu"]
        assert got["rho_t_per_mm3"] == pytest.approx(row["rho_kg_m3"] * 1e-12)
        assert (
            got["yield_mpa"] == row["Fty_selected"]["MPa"]
        )  # the selected (lowest published) Fty
    assert v2.ALLOYS["6061-T6"]["yield_mpa"] == 241.3
    assert v2.ALLOYS["4130-normalized"]["yield_mpa"] == 482.6
    assert v2.ALLOYS["Ti-6Al-4V-annealed"]["yield_mpa"] == 827.4


def test_production_builds_with_the_signed_alloys_and_records_the_decision_and_sha():
    for name in v2.ALLOY_IDS:
        mat = v2.material(name)
        assert (
            mat["tables"] == "REGISTERED" and mat["source"]["sha256"] == v2.ALLOY_SHA256
        )
    deck = v2.deck_text(
        {**CASE, "alloy": "4130-normalized"},
        _tiny_meta(),
        v2.material("4130-normalized"),
    )
    assert f"** alloy table: OWNER-F08-V2-ALLOYS-SIGNED-01 {v2.ALLOY_SHA256}" in deck
    assert (
        "199950.0,0.32" in deck and "7.8334e-09" in deck and "tables=REGISTERED" in deck
    )
    test_deck = v2.deck_text(
        CASE, _tiny_meta(), v2.material("TEST_ALLOY", table=TEST_TABLE, test_mode=True)
    )
    assert (
        "** alloy table" not in test_deck
    )  # a test table carries no signed provenance
    margin = v2.stress_margin({"peak_von_mises_mpa": 200.0}, v2.material("6061-T6"))
    assert margin["allowable_mpa"] == pytest.approx(241.3 / 1.5)
    assert margin["stress_ratio"] == pytest.approx(200.0 / (241.3 / 1.5))


def test_a_changed_or_missing_alloy_file_puts_human_input_back_and_refuses(monkeypatch):
    monkeypatch.setattr(v2, "ALLOY_SHA256", "sha256:" + "0" * 64)
    table, status = v2._load_signed_alloys()
    assert status == "ALLOY_FILE_NOT_THE_SIGNED_ONE"
    for name in v2.ALLOY_IDS:
        assert all(v == v2.HUMAN_INPUT for v in table[name].values())
        with pytest.raises(v2.Refused, match="alloy_value_not_registered_E_mpa"):
            v2.material(name, table=table)
    monkeypatch.setattr(v2, "ALLOY_FILE", "no_such_file.json")
    assert v2._load_signed_alloys()[1] == "ALLOY_FILE_MISSING"


def test_an_unknown_alloy_and_a_human_input_value_are_still_refused():
    with pytest.raises(v2.Refused, match="alloy_not_registered"):
        v2.material("TEST_ALLOY")
    with pytest.raises(v2.Refused, match="alloy_value_not_registered_yield_mpa"):
        v2.material(
            "TEST_ALLOY",
            table={
                "TEST_ALLOY": {**TEST_TABLE["TEST_ALLOY"], "yield_mpa": "HUMAN_INPUT"}
            },
        )
    row = v2.material("TEST_ALLOY", table=TEST_TABLE, test_mode=True)
    assert row["tables"] == "TEST_ONLY" and "source" not in row
    assert v2.material("TEST_ALLOY", table=TEST_TABLE)["tables"] == "REGISTERED"


def test_the_load_direction_is_a_unit_vector_and_zero_degrees_is_the_1_7_load():
    assert v2.load_components(0.0) == (0.0, 1.0)
    fy, fz = v2.load_components(30.0)
    assert math.isclose(fy**2 + fz**2, 1.0) and fy > 0
    weights = {10: 0.25, 11: 0.75}
    assert v2.load_lines(weights, 0.0) == "10,3,0.25\n11,3,0.75\n"
    assert "10,2," in v2.load_lines(weights, 90.0)


def test_the_gmsh_program_is_valid_python_and_has_the_fillet_refinement_and_offset_pad():
    text = v2.gmsh_script_v2(CASE, 3.0, 0.5)
    assert v2.script_compiles(text)
    for part in (
        "occ.fillet([body[0][1]], junction, [rf] * 4, True)",
        'field.add("Distance", 1)',
        "SizeMin",
        "ELSET=FILLET",
        "off - 10.0 / 2",
        "assert len(junction) == 4",
    ):
        assert part in text, part
    assert v2.HUMAN_INPUT not in text


def test_the_ccx_deck_has_one_damping_sweep_the_fillet_stress_print_and_the_alloy():
    meta = {
        "pad_tri6": [[1, 2, 3, 4, 5, 6]],
        "probe_tri6": [[1, 2, 3, 7, 8, 9]],
        "coords": {
            "1": [0.0, 0.0, 0.0],
            "2": [4.0, 0.0, 0.0],
            "3": [0.0, 4.0, 0.0],
            "4": [2.0, 0.0, 0.0],
            "5": [2.0, 2.0, 0.0],
            "6": [0.0, 2.0, 0.0],
            "7": [4.0, 4.0, 0.0],
            "8": [3.0, 3.0, 0.0],
            "9": [1.0, 3.0, 0.0],
        },
        "tip_node": 1,
        "probe_node": 2,
    }
    mat = v2.material("TEST_ALLOY", table=TEST_TABLE, test_mode=True)
    deck = v2.deck_text({**CASE, "load_angle_deg": 20.0}, meta, mat)
    assert (
        deck.count("*STEADY STATE DYNAMICS") == 1
    )  # damping is a condition, not three bands
    assert "*MODAL DAMPING\n1,48,0.01" in deck
    assert "*EL PRINT,ELSET=FILLET\nS" in deck
    assert "70000.0,0.33" in deck and "tables=TEST_ONLY" in deck
    assert ",2," in deck.split("*STATIC")[1]  # a y component for a nonzero load angle


UNIAXIAL = (50.0, 0.0, 0.0, 0.0, 0.0, 0.0)


def test_von_mises_reduces_the_known_states():
    assert v2.von_mises(UNIAXIAL) == pytest.approx(50.0)
    assert v2.von_mises((0.0, 0.0, 0.0, 30.0, 0.0, 0.0)) == pytest.approx(
        30.0 * math.sqrt(3.0)
    )
    hydrostatic = (80.0, 80.0, 80.0, 0.0, 0.0, 0.0)
    assert v2.von_mises(hydrostatic) == pytest.approx(0.0, abs=1e-12)


DAT = """
 stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz) for set FILLET and time  0.1000000E+01

         7   1  5.000000E+01  0.000000E+00  0.000000E+00  0.000000E+00  0.000000E+00  0.000000E+00
         7   2  1.000000E+02  0.000000E+00  0.000000E+00  0.000000E+00  0.000000E+00  0.000000E+00
         9   1 -1.200000E+02  0.000000E+00  0.000000E+00  0.000000E+00  0.000000E+00  0.000000E+00

 total force (fx,fy,fz) for set FILLET and time  0.1000000E+01
"""


def test_the_stress_parser_reads_ccx_rows_and_the_peak_is_the_largest_von_mises():
    rows = v2.parse_stress(DAT)
    assert [(e, p) for e, p, _ in rows] == [(7, 1), (7, 2), (9, 1)]
    peak = v2.peak_von_mises(rows)
    assert peak["peak_von_mises_mpa"] == pytest.approx(
        120.0
    )  # |-120|, not the largest signed value
    assert (peak["element"], peak["integration_point"]) == (9, 1)
    with pytest.raises(v2.Refused, match="no_fillet_stress_rows"):
        v2.peak_von_mises([])


def test_the_margin_uses_the_registered_safety_factor_and_the_alloy_yield():
    mat = v2.material("TEST_ALLOY", table=TEST_TABLE, test_mode=True)
    out = v2.observe_v2(CASE, DAT, mat)  # SF = 1.5 (OWNER-F08-V2-VALUES-01)
    assert out["tables"] == "TEST_ONLY"
    assert out["margin"]["allowable_mpa"] == pytest.approx(100.0 / 1.5)
    assert out["margin"]["stress_ratio"] == pytest.approx(120.0 / (100.0 / 1.5))
    with pytest.raises(v2.Refused, match="safety_factor_out_of_range"):
        v2.stress_margin(out, mat, 0.5)
    refused = v2.observe_v2(CASE, DAT, mat, safety_factor=v2.HUMAN_INPUT)
    assert refused["margin"] == {"refused": "safety_factor_not_registered"}
    no_yield = {**mat, "yield_mpa": v2.HUMAN_INPUT}
    assert v2.observe_v2(CASE, DAT, no_yield)["margin"] == {
        "refused": "yield_not_registered"
    }


def test_the_cantilever_control_is_elementary_beam_theory():
    # P = 1 N, L = 100, W = 20, t = 5: 6*1*100/(20*25) = 1.2 MPa
    assert v2.cantilever_root_bending_stress(1.0, 100.0, 20.0, 5.0) == pytest.approx(
        1.2
    )
    doubled = v2.cantilever_root_bending_stress(1.0, 100.0, 20.0, 10.0)
    assert doubled == pytest.approx(1.2 / 4.0)  # stress falls with t squared


def test_the_notch_control_needs_a_published_kt_and_a_tolerance():
    with pytest.raises(v2.Refused, match="published_kt_not_registered"):
        v2.notch_control(30.0, 10.0, v2.HUMAN_INPUT, tolerance=0.1)
    with pytest.raises(v2.Refused, match="notch_tolerance_not_registered"):
        v2.notch_control(30.0, 10.0, 3.0, tolerance=v2.HUMAN_INPUT)
    assert v2.notch_control(30.0, 10.0, 3.0, tolerance=0.05)["ok"] is True
    assert v2.notch_control(36.0, 10.0, 3.0, tolerance=0.05)["ok"] is False


def test_the_feature_vector_carries_the_geometry_the_new_inputs_the_alloy_id_and_its_properties():
    names = v2.feature_names()
    assert len(names) == 15 and names[-4:] == v2.PROPERTY_FEATURES
    table = {
        **TEST_TABLE,
        "A_FIRST": {**TEST_TABLE["TEST_ALLOY"], "E_mpa": 200000.0},
    }
    assert v2.alloy_ids(table) == {"TEST_ALLOY": 0, "A_FIRST": 1}
    row = v2.features(CASE, table=table)
    assert len(row) == len(names)
    assert row[names.index("alloy_id")] == 0.0
    assert (
        row[names.index("E_mpa")] == 70000.0 and row[names.index("yield_mpa")] == 100.0
    )
    with pytest.raises(v2.Refused, match="alloy_not_registered"):
        v2.features(CASE)  # the production table is empty


def _dat(peak):
    return f"""
 stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz) for set FILLET and time  0.1000000E+01

         3   1  {peak:.6E}  0.000000E+00  0.000000E+00  0.000000E+00  0.000000E+00  0.000000E+00

 total force (fx,fy,fz)
"""


def test_the_refinement_ladder_reports_each_rung_and_the_successive_change():
    mat = v2.material("TEST_ALLOY", table=TEST_TABLE, test_mode=True)
    out = v2.observe_rungs(
        CASE, {1.0: _dat(100.0), 0.5: _dat(110.0), 0.25: _dat(112.2)}, mat
    )
    assert [r["fillet_h_mm"] for r in out["rungs"]] == [
        1.0,
        0.5,
        0.25,
    ]  # coarse to fine
    assert [r["peak_von_mises_mpa"] for r in out["rungs"]] == pytest.approx(
        [100.0, 110.0, 112.2]
    )
    assert [c["rel_change"] for c in out["successive"]] == pytest.approx([0.10, 0.02])
    with pytest.raises(v2.Refused, match="fillet_refinement_needs_two_rungs"):
        v2.observe_rungs(CASE, {0.5: _dat(110.0)}, mat)


def test_the_solve_record_binds_the_deck_the_output_the_mesh_and_the_images_and_holds_no_stress():
    record = v2.solve_record(
        CASE,
        deck="deck text",
        mesh_meta={
            "nodes": 10,
            "elements": 4,
            "fillet_elements": 2,
            "mesh_volume_mm3": 1.5,
            "coords": {"1": [0, 0, 0]},
        },
        dat_text=_dat(100.0),
        image_ids={"mesh": "sha256:" + "a" * 64, "ccx": "sha256:" + "b" * 64},
        fillet_h_mm=0.5,
        wall_s=12.5,
    )
    assert record["schema"] == "carbon.f08.solve-record.v3" and record["wall_s"] == 12.5
    assert record["deck_revision"] == v2.DECK_REVISION == "f08-2.0-deck-solver-pastix"
    assert record["solver"] == v2.SOLVER == "PASTIX"
    assert (
        record["deck_sha256"].startswith("sha256:")
        and record["dat_sha256"] != record["deck_sha256"]
    )
    assert "coords" not in record["mesh"] and "peak_von_mises_mpa" not in record


def _modal_dat(modes, static_peak):
    blocks = []
    for k in range(modes):
        blocks.append(
            "\n stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz) for set FILLET"
            f" and time  {k + 1}.0\n\n"
            f"         5   1  {10.0 * (k + 1):.6E}  0.0  0.0  0.0  0.0  0.0\n"
            f"         5   2  {5.0 * (k + 1):.6E}  0.0  0.0  0.0  0.0  0.0\n"
        )
    blocks.append(_dat(static_peak))
    return "".join(blocks)


def test_the_modal_stress_fields_are_the_first_blocks_and_the_static_block_follows():
    keys, fields = v2.modal_stress_tensors(_modal_dat(3, 99.0), 3)
    assert keys == [(5, 1), (5, 2)] and fields.shape == (3, 2, 6)
    assert fields[2, 0, 0] == pytest.approx(30.0)
    with pytest.raises(v2.Refused, match="modal_stress_blocks_missing"):
        v2.modal_stress_tensors(_modal_dat(3, 99.0), 4)


def _one_mode(hz, pf, stress):
    omega = 2.0 * math.pi * hz
    return (
        [{"omega": omega, "hz": hz, "pf": pf}],
        v2.np.array([[[stress, 0.0, 0.0, 0.0, 0.0, 0.0]]]),
    )


def test_a_single_resonance_gives_the_textbook_dynamic_stress_peak_at_the_mode_frequency():
    modal, field = _one_mode(200.0, 0.5, 40.0)
    zeta = 0.01
    out = v2.worst_band_dynamic_stress(field, modal, zeta)
    omega = modal[0]["omega"]
    expected = (
        0.5 * 40.0 / (2.0 * zeta * omega**2)
    )  # |q| = pf / (2 zeta omega^2) at resonance
    assert out["dynamic_von_mises_mpa_per_n"] == pytest.approx(expected, rel=2e-3)
    assert out["frequency_hz"] == pytest.approx(200.0, abs=1.0)
    assert out["band_hz"] == [80.0, 600.0]


def test_the_dynamic_stress_depends_on_damping_and_on_where_the_mode_sits_against_the_band():
    modal, field = _one_mode(200.0, 0.5, 40.0)
    light = v2.worst_band_dynamic_stress(field, modal, 0.005)
    heavy = v2.worst_band_dynamic_stress(field, modal, 0.02)
    assert light["dynamic_von_mises_mpa_per_n"] == pytest.approx(
        4.0 * heavy["dynamic_von_mises_mpa_per_n"], rel=5e-3
    )
    outside, field_out = _one_mode(
        1500.0, 0.5, 40.0
    )  # same mode, stiffer alloy: out of the band
    off = v2.worst_band_dynamic_stress(field_out, outside, 0.01)
    assert (
        off["dynamic_von_mises_mpa_per_n"] < 0.05 * light["dynamic_von_mises_mpa_per_n"]
    )


def test_an_oscillating_shear_state_keeps_its_von_mises_amplitude():
    omega = 2.0 * math.pi * 200.0
    modal = [{"omega": omega, "hz": 200.0, "pf": 1.0}]
    shear = v2.np.array([[[0.0, 0.0, 0.0, 30.0, 0.0, 0.0]]])
    value = v2.dynamic_stress_amplitude(shear, modal, 200.0, 0.01)
    assert value == pytest.approx(
        30.0 * math.sqrt(3.0) / (2 * 0.01 * omega**2), rel=1e-6
    )


def test_the_dynamic_ladder_reports_each_rung_and_the_change():
    mat = v2.material("TEST_ALLOY", table=TEST_TABLE, test_mode=True)
    coarse, fine = _one_mode(200.0, 0.5, 40.0), _one_mode(200.0, 0.5, 42.0)
    out = v2.observe_dynamic_rungs(
        CASE, {1.0: (coarse[1], coarse[0]), 0.5: (fine[1], fine[0])}, mat
    )
    assert [r["fillet_h_mm"] for r in out["rungs"]] == [1.0, 0.5]
    assert out["successive"][0]["rel_change"] == pytest.approx(0.05, rel=2e-3)
    with pytest.raises(v2.Refused, match="fillet_refinement_needs_two_rungs"):
        v2.observe_dynamic_rungs(CASE, {1.0: (coarse[1], coarse[0])}, mat)


def test_the_modal_stress_is_requested_in_the_frequency_step_and_the_ruling_is_recorded():
    meta = {
        "pad_tri6": [[1, 2, 3, 4, 5, 6]],
        "probe_tri6": [[1, 2, 3, 7, 8, 9]],
        "coords": {str(n): [float(n % 3), float(n // 3), 0.0] for n in range(1, 10)},
        "tip_node": 1,
        "probe_node": 2,
    }
    mat = v2.material("TEST_ALLOY", table=TEST_TABLE, test_mode=True)
    deck = v2.deck_text(CASE, meta, mat)
    frequency = deck.split("*FREQUENCY")[1].split("*END STEP")[0]
    assert "*EL PRINT,ELSET=FILLET\nS" in frequency
    assert v2.STRESS_FIXED["primary"] == "worst_band_dynamic_von_mises"
    assert v2.STRESS_FIXED["constraint"] == "static_peak_von_mises"


def _tiny_meta():
    return {
        "pad_tri6": [[1, 2, 3, 4, 5, 6]],
        "probe_tri6": [[1, 2, 3, 7, 8, 9]],
        "coords": {
            "1": [0.0, 0.0, 0.0],
            "2": [4.0, 0.0, 0.0],
            "3": [0.0, 4.0, 0.0],
            "4": [2.0, 0.0, 0.0],
            "5": [2.0, 2.0, 0.0],
            "6": [0.0, 2.0, 0.0],
            "7": [4.0, 4.0, 0.0],
            "8": [3.0, 3.0, 0.0],
            "9": [1.0, 3.0, 0.0],
        },
        "tip_node": 1,
        "probe_node": 2,
    }


def test_load_angle_zero_reproduces_the_1_7_load_lines_exactly():
    meta = _tiny_meta()
    mat = v2.material("TEST_ALLOY", table=TEST_TABLE, test_mode=True)
    pad = v1.face_weights(meta["pad_tri6"], meta["coords"])
    total = math.fsum(pad.values())
    loads = {n: w / total for n, w in pad.items()}
    v1_lines = "".join(f"{n},3,{f:.12g}\n" for n, f in sorted(loads.items()))
    assert v2.load_lines(loads, 0.0) == v1_lines  # the 1.7 CLOAD text, byte for byte
    deck = v2.deck_text({**CASE, "load_angle_deg": 0.0}, meta, mat)
    assert deck.count(v1_lines) == 2  # the steady-state and the static step
    assert ",2," not in v1_lines
    # +y at 90 degrees is the in-plane transverse load
    assert "".join(f"{n},3," for n in loads) not in v2.load_lines(loads, 90.0)


def test_the_numerical_settings_are_fixed_and_written_in_every_deck_header():
    settings = v2.numerical_settings()
    assert (
        settings["oscillation_phases"] == 72 and settings["peak_refinement_rel"] == 1e-6
    )
    assert settings["band_hz"] == [80.0, 600.0]
    mat = v2.material("TEST_ALLOY", table=TEST_TABLE, test_mode=True)
    deck = v2.deck_text(CASE, _tiny_meta(), mat)
    header = deck.split("*INCLUDE")[0]
    assert "** numerical settings: " in header and '"oscillation_phases": 72' in header


# ---------------------------------------------------------------- the PaStiX re-pin (a versioned deck migration)


def _step_lines(deck):
    return [
        line for line in deck.splitlines() if line.startswith(("*FREQUENCY", "*STATIC"))
    ]


def test_every_frequency_and_static_step_of_a_2_0_deck_names_the_pastix_solver():
    assert v2.SOLVER == "PASTIX"
    mat = v2.material("TEST_ALLOY", table=TEST_TABLE, test_mode=True)
    for case in (
        CASE,
        {**CASE, "load_angle_deg": 20.0},
        {**CASE, "control": {"kind": "plain_plate"}},
        {**CASE, "control": {"kind": "hole_plate"}},
    ):
        lines = _step_lines(v2.deck_text(case, _tiny_meta(), mat))
        assert lines and all("SOLVER=PASTIX" in line for line in lines), case
        expected = ["*STATIC,SOLVER=PASTIX"]
        if case.get("control") is None:
            expected = ["*FREQUENCY,SOLVER=PASTIX,STORAGE=YES", *expected]
        assert lines == expected, case
    deck = v2.deck_text(CASE, _tiny_meta(), mat)
    assert deck.count("SOLVER=") == 2  # the steady-state step factorises nothing


def _fake_v1_mesh(out):
    (Path(out) / "mesh.json").write_text(
        json.dumps({**_tiny_meta(), "nodes": 9, "elements": 1})
    )


V17_CASE = {name: CASE[name] for name in v2.GEOMETRY}


def test_the_1_7_deck_default_bytes_are_unchanged_and_a_named_solver_edits_only_its_two_step_lines(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(v1, "mesh", _fake_v1_mesh)
    v1.write_case(V17_CASE, tmp_path / "registered")
    v2.write_case_v17(V17_CASE, tmp_path / "default")
    v2.write_case_v17(V17_CASE, tmp_path / "pastix", solver="PASTIX")
    for name in ("make_mesh.py", "mesh.json", "case.inp", "deck.json"):
        registered = (tmp_path / "registered" / name).read_bytes()
        assert (tmp_path / "default" / name).read_bytes() == registered, name
        if name != "case.inp":
            assert (tmp_path / "pastix" / name).read_bytes() == registered, name
    registered = (tmp_path / "registered/case.inp").read_text()
    assert "SOLVER=" not in registered
    assert _step_lines(registered) == ["*FREQUENCY,STORAGE=YES", "*STATIC"]
    pastix = (tmp_path / "pastix/case.inp").read_text()
    changed = [
        (a, b)
        for a, b in zip(registered.split("\n"), pastix.split("\n"), strict=True)
        if a != b
    ]
    assert changed == [
        ("*FREQUENCY,STORAGE=YES", "*FREQUENCY,SOLVER=PASTIX,STORAGE=YES"),
        ("*STATIC", "*STATIC,SOLVER=PASTIX"),
    ]
    assert hashlib.sha256(registered.encode()).hexdigest() == V17_FAKE_MESH_DECK_SHA256


#: sha256 of `f08_deck.write_case`'s case.inp for V17_CASE on `_fake_v1_mesh` (the registered generator, never edited).
V17_FAKE_MESH_DECK_SHA256 = (
    "c1a0219b17133fa04c4a9e2206df60af97b2bf3a8f1efcffcaae0354e61e75b2"
)


@pytest.mark.parametrize(
    "deck, solver, reason",
    [
        ("*FREQUENCY,STORAGE=YES\n*STATIC\n", "pastix", "solver_name_invalid"),
        ("*FREQUENCY,STORAGE=YES\n*STATIC\n", "PASTIX,X=1", "solver_name_invalid"),
        ("*FREQUENCY,STORAGE=YES\n*STATIC\n", None, "solver_name_invalid"),
        ("*FREQUENCY,STORAGE=YES\n", "PASTIX", "v17_deck_step_lines_unexpected"),
        (
            "*FREQUENCY,STORAGE=YES\n*STATIC\n*STATIC\n",
            "PASTIX",
            "v17_deck_step_lines_unexpected",
        ),
        (
            "*FREQUENCY,STORAGE=YES\n*STATIC\n*STATIC,SOLVER=SPOOLES\n",
            "PASTIX",
            "v17_deck_already_names_a_solver",
        ),
    ],
)
def test_naming_a_solver_on_a_1_7_deck_refuses_a_bad_name_or_an_unexpected_deck(
    deck, solver, reason
):
    with pytest.raises(v2.Refused, match=reason):
        v2.v17_with_solver(deck, solver)
