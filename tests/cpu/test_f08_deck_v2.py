"""F08 2.0 deck (STRESS working choice): owner values refuse, the Gmsh program compiles, the stress reduction and the
closed-form controls are right on synthetic data. No solve, no Gmsh, no CalculiX is run."""

from __future__ import annotations

import hashlib
import math
import sys
from pathlib import Path

import pytest

CALCULIX = (
    Path(__file__).resolve().parents[2] / "scripts/dev/reference_packages/calculix"
)
sys.path.insert(0, str(CALCULIX))

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
    "load_offset_mm": 0.0,
    "damping_ratio": 0.01,
    "alloy": "TEST_ALLOY",
}
#: Clearly synthetic: never a registered range or alloy.
TEST_RANGES = {
    "fillet_radius_mm": (0.5, 4.0),
    "load_angle_deg": (-30.0, 30.0),
    "load_offset_mm": (-10.0, 10.0),
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


def test_a_production_case_refuses_until_the_owner_registers_the_new_ranges():
    with pytest.raises(v2.Refused, match="range_not_registered_fillet_radius_mm"):
        v2.validate_case(CASE)
    assert v2.validate_case(CASE, ranges=TEST_RANGES)["alloy"] == "TEST_ALLOY"
    assert v2.validate_case(CASE, test_mode=True)["fillet_radius_mm"] == 2.0


@pytest.mark.parametrize(
    "change, code",
    [
        ({"fillet_radius_mm": 9.0}, "out_of_range"),
        ({"fillet_radius_mm": 0.1}, "out_of_range"),
        ({"rib_height_mm": 0.0}, "fillet_needs_a_rib"),
        ({"load_offset_mm": 10.0, "width_mm": 30.0}, "load_pad_leaves_the_plate"),
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


def test_the_alloy_table_is_empty_and_every_value_refuses_until_registered():
    assert v2.ALLOYS == {} and v2.SAFETY_FACTOR == v2.HUMAN_INPUT
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
    assert row["tables"] == "TEST_ONLY"
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


def test_the_margin_needs_the_alloy_yield_and_the_owners_safety_factor():
    mat = v2.material("TEST_ALLOY", table=TEST_TABLE, test_mode=True)
    out = v2.observe_v2(CASE, DAT, mat)
    assert out["margin"] == {"refused": "safety_factor_not_registered"}
    assert out["tables"] == "TEST_ONLY"
    out = v2.observe_v2(CASE, DAT, mat, safety_factor=1.5)
    assert out["margin"]["allowable_mpa"] == pytest.approx(100.0 / 1.5)
    assert out["margin"]["stress_ratio"] == pytest.approx(120.0 / (100.0 / 1.5))
    with pytest.raises(v2.Refused, match="safety_factor_out_of_range"):
        v2.stress_margin(out, mat, 0.5)


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
    assert v2.alloy_ids(table) == {"A_FIRST": 0, "TEST_ALLOY": 1}
    row = v2.features(CASE, table=table)
    assert len(row) == len(names)
    assert row[names.index("alloy_id")] == 1.0
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
    assert record["schema"] == "carbon.f08.solve-record.v2" and record["wall_s"] == 12.5
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
