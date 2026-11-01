"""F08 2.0 stress controls: the deck's optional `control` hook leaves every existing output byte-identical, the control
cases go through the deck's own Gmsh/ccx path, and the Kirsch / cantilever / shoulder-fillet verdicts are right on synthetic
data. No solve, no Gmsh, no CalculiX is run; pass tolerances stay HUMAN_INPUT.
"""

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
import f08_v2_controls as ctl

ALLOY = "TEST_ALLOY"
TEST_TABLE = {
    ALLOY: {
        "E_mpa": 70000.0,
        "nu": 0.33,
        "rho_t_per_mm3": 2.7e-9,
        "yield_mpa": 100.0,
    }
}
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
    "alloy": ALLOY,
}
META = {
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
MAT = v2.material(ALLOY, table=TEST_TABLE, test_mode=True)

# sha256 of the deck's outputs for these cases, taken from f08_deck_v2.py at 1860bc1f BEFORE the `control` hook existed.
PINNED = {
    "gmsh_base": "8a64159459519eabe8f9d93ab7d143a6b08e3dba33ae0111e92dbaf647f3de8c",
    "deck_base": "7337462ddfda7eb136c8509829ff93df27e4656716679faaf2316d2e6c4f6655",
    "gmsh_norelief": "20466bef6ca2298d08ff3c23aaddb20be712c86def685422a2f8c9e138998fbd",
    "deck_norelief": "bb737ae556d3ce4eacd1d71276a1625d18b8428372c09e338fddf914d009e9b5",
    "gmsh_offset_angle": "1ff74b231957f96d4023a22c035ed097879a879ffc080b0e2facc712af2f33a2",
    "deck_offset_angle": "1ed920788f0c61b644315801b9192c874f24efaab6e38b879b8cd9684be5ede6",
}


def _sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def test_a_case_without_control_leaves_every_existing_output_byte_identical():
    cases = {
        "base": CASE,
        "norelief": {**CASE, "relief_length_mm": 0.0},
        "offset_angle": {**CASE, "load_offset_frac": 0.2, "load_angle_deg": 20.0},
    }
    got = {}
    for name, case in cases.items():
        got["gmsh_" + name] = _sha(v2.gmsh_script_v2(case, 3.0, 0.5))
        got["deck_" + name] = _sha(v2.deck_text(case, META, MAT))
    assert got == PINNED


def test_the_control_case_validation_refuses_what_it_does_not_register():
    with pytest.raises(v2.Refused, match="control_kind_not_registered"):
        v2.validate_case({**CASE, "control": {"kind": "ribbed"}})
    good = ctl.kirsch_case(ALLOY)
    for change, code in (
        ({"rib_height_mm": 1.0}, "control_case_has_no_ribs_or_relief"),
        ({"load_angle_deg": 10.0}, "control_load_is_fixed"),
        ({"load_offset_frac": 0.1}, "control_load_is_fixed"),
        (
            {"control": {"kind": "hole_plate", "hole_radius_mm": 50.0}},
            "hole_radius_out_of_range",
        ),
        (
            {"control": {"kind": "hole_plate", "hole_radius_mm": 2.0, "x": 1}},
            "control_keys_not_registered",
        ),
        ({"control": {"kind": "plain_plate", "x": 1}}, "control_keys_not_registered"),
    ):
        with pytest.raises(v2.Refused, match=code):
            v2.validate_case({**good, **change})
    missing = {k: v for k, v in good.items() if k != "alloy"}
    with pytest.raises(v2.Refused, match="case_missing_alloy"):
        v2.validate_case(missing)


def test_the_kirsch_case_is_a_wide_thin_plate_with_a_small_hole():
    case = ctl.kirsch_case(ALLOY)
    radius = case["control"]["hole_radius_mm"]
    assert 2 * radius / case["width_mm"] == pytest.approx(0.05)
    assert case["thickness_mm"] == pytest.approx(radius / 2)  # plane stress
    assert "fillet_radius_mm" not in case
    assert (case["rib_height_mm"], case["rib_thickness_mm"]) == (0.0, 0.0)


def test_the_control_gmsh_programs_use_the_decks_own_path():
    hole = v2.gmsh_script_v2(ctl.kirsch_case(ALLOY), 8.0, 0.5)
    plain = v2.gmsh_script_v2(ctl.plain_plate_case(ALLOY), 3.0, 0.5)
    default = v2.gmsh_script_v2(CASE, 3.0, 0.5)
    for text in (hole, plain, default):
        assert v2.script_compiles(text)
        for part in ("ELSET=FILLET", 'field.add("Distance", 1)', "SizeMin"):
            assert part in text, part
    assert "addCylinder(L / 2, 0, -1, 0, 0, t + 2, rf)" in hole
    assert "occ.fillet" not in hole and "ribs" not in hole
    assert (
        "pad_faces = faces(L, -W, -1, L, W, t + 1)" in hole
    )  # the end face carries the load
    assert "fillet_faces = root_faces" in plain
    assert "occ.fillet" not in plain and "ribs" not in plain
    assert "addCylinder" not in default and "fillet_faces = root_faces" not in default


def test_a_control_deck_is_one_static_step_and_the_hole_load_is_axial():
    hole = v2.deck_text(ctl.kirsch_case(ALLOY), META, MAT)
    plain = v2.deck_text(ctl.plain_plate_case(ALLOY), META, MAT)
    for deck in (hole, plain):
        assert deck.count("*STEP") == 1 and "*STATIC" in deck
        assert "*FREQUENCY" not in deck and "*STEADY STATE DYNAMICS" not in deck
        assert "*EL PRINT,ELSET=FILLET\nS" in deck
    loads_hole = hole.split("*CLOAD,OP=NEW\n")[1].split("*NODE PRINT")[0]
    assert loads_hole.strip().splitlines() and all(
        line.split(",")[1] == "1" for line in loads_hole.strip().splitlines()
    )
    loads_plain = plain.split("*CLOAD,OP=NEW\n")[1].split("*NODE PRINT")[0]
    assert {line.split(",")[1] for line in loads_plain.strip().splitlines()} == {"3"}
    total = sum(float(line.split(",")[2]) for line in loads_hole.strip().splitlines())
    assert total == pytest.approx(1.0)  # a unit resultant


def test_the_analytic_references_are_beam_theory_and_the_gross_nominal_stress():
    kirsch, plain = ctl.kirsch_case(ALLOY), ctl.plain_plate_case(ALLOY)
    assert ctl.kirsch_nominal_mpa(kirsch) == pytest.approx(1.0 / (80.0 * 1.0))
    assert ctl.plain_nominal_mpa(plain) == pytest.approx(
        6.0 * (220.0 - 2.5) / (20.0 * 6.0**2)
    )


def test_the_ladder_halves_the_local_size_and_keeps_the_global_size():
    rungs = ctl.ladder(0.8, 8.0)
    assert [r["fillet_h_mm"] for r in rungs] == pytest.approx([0.8, 0.4, 0.2])
    assert {r["h_mm"] for r in rungs} == {8.0}
    with pytest.raises(ctl.ControlRefused, match="ladder_arguments_out_of_range"):
        ctl.ladder(0.8, 8.0, ratio=1.0)
    assert len(ctl.rung_scripts(ctl.kirsch_case(ALLOY), rungs)) == 3


def _dat(*peaks):
    """A ccx-style .dat with one stress block whose largest von Mises is max(peaks) (uniaxial sxx rows)."""
    rows = "".join(
        f"{i + 1:10d}{1:4d}  {p:.6E}  0.000000E+00  0.000000E+00  0.000000E+00  0.000000E+00  0.000000E+00\n"
        for i, p in enumerate(peaks)
    )
    return (
        " stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz) for set FILLET and time  0.1E+01\n\n"
        + rows
        + "\n total force (fx,fy,fz) for set FILLET and time  0.1E+01\n"
    )


def test_richardson_recovers_the_limit_and_the_order_of_a_second_order_sequence():
    h = 0.4
    value = lambda s: 3.0 - 0.5 * s * s
    out = ctl.richardson_gci(value(h / 4), value(h / 2), value(h))
    assert out["monotone"] and out["order"] == pytest.approx(2.0)
    assert out["extrapolated"] == pytest.approx(3.0)
    assert out["halfwidth"] == pytest.approx(
        1.25 * abs(value(h / 4) - value(h / 2)) / 3.0
    )


@pytest.mark.parametrize(
    "values",
    [
        (3.0, 2.9, 3.1),  # not monotone
        (1.0, 1.0, 1.0),  # no change
        (2.0, 2.5, 2.6),  # diverging: negative order
    ],
)
def test_a_non_monotone_flat_or_diverging_sequence_gives_no_extrapolation(values):
    out = ctl.richardson_gci(*values)
    assert out["extrapolated"] is None and out["halfwidth"] is None


def _kirsch_dats(case, limit, c=0.6, h=(0.8, 0.4, 0.2)):
    nominal = ctl.kirsch_nominal_mpa(case)
    # Kt(h) = limit - c * h^2 (second order, from below); fine to coarse in the fine-first dict order
    return {size: (limit - c * size * size) * nominal for size in h}


def test_kirsch_passes_when_three_is_inside_the_rungs_own_extrapolation_band():
    case = ctl.kirsch_case(ALLOY)
    dats = {h: _dat(peak) for h, peak in _kirsch_dats(case, 3.0).items()}
    out = ctl.kirsch_verdict(dats, case)
    assert out["passed"] and out["published_kt"] == 3.0
    assert out["richardson"]["order"] == pytest.approx(2.0)
    assert out["finite_width"].startswith("none applied")
    assert (
        out["source"].startswith("G. Kirsch") and "secondary sources" in out["source"]
    )


def test_kirsch_fails_when_the_rungs_converge_to_another_value():
    case = ctl.kirsch_case(ALLOY)
    for limit in (3.3, 2.7):
        dats = {h: _dat(p) for h, p in _kirsch_dats(case, limit).items()}
        assert ctl.kirsch_verdict(dats, case)["passed"] is False


def test_kirsch_fails_without_a_positive_monotone_order():
    case = ctl.kirsch_case(ALLOY)
    nominal = ctl.kirsch_nominal_mpa(case)
    # exactly 3.0 at the middle rung but not monotone: no pass can come from a fluke
    bumpy = {0.2: 3.05 * nominal, 0.4: 2.95 * nominal, 0.8: 3.2 * nominal}
    assert (
        ctl.kirsch_verdict({h: _dat(p) for h, p in bumpy.items()}, case)["passed"]
        is False
    )


def test_kirsch_refuses_other_than_three_rungs_or_a_changing_ratio():
    case = ctl.kirsch_case(ALLOY)
    nominal = ctl.kirsch_nominal_mpa(case)
    two = {0.2: _dat(3 * nominal), 0.4: _dat(2.9 * nominal)}
    with pytest.raises(ctl.ControlRefused, match="exactly_three_rungs"):
        ctl.kirsch_verdict(two, case)
    uneven = {
        0.2: _dat(3 * nominal),
        0.4: _dat(2.9 * nominal),
        1.0: _dat(2.5 * nominal),
    }
    with pytest.raises(ctl.ControlRefused, match="constant_refinement_ratio"):
        ctl.kirsch_verdict(uneven, case)
    with pytest.raises(ctl.ControlRefused, match="control_stress_block_missing"):
        ctl.static_peak_mpa("no stress here")


def test_the_peak_is_the_largest_von_mises_of_the_single_static_block():
    assert ctl.static_peak_mpa(_dat(10.0, 40.0, 25.0)) == pytest.approx(40.0)


def test_the_cantilever_report_states_the_ratio_and_no_verdict_without_a_tolerance():
    case = ctl.plain_plate_case(ALLOY)
    nominal = ctl.plain_nominal_mpa(case)
    out = ctl.plain_plate_report(_dat(1.1 * nominal), case)
    assert out["ratio"] == pytest.approx(1.1)
    assert out["tolerance"] == v2.HUMAN_INPUT and "within_tolerance" not in out
    owner = ctl.plain_plate_report(_dat(1.1 * nominal), case, tolerance=0.2)
    assert owner["within_tolerance"] is True
    assert (
        ctl.plain_plate_report(_dat(1.5 * nominal), case, tolerance=0.2)[
            "within_tolerance"
        ]
        is False
    )


def test_the_shoulder_fillet_sanity_reports_and_never_decides():
    unset = ctl.shoulder_fillet_sanity(2.1)
    assert unset["state"] == "NOT_CONFIGURED"
    assert (
        unset["published_kt"] == v2.HUMAN_INPUT and unset["chart_id"] == v2.HUMAN_INPUT
    )
    reported = ctl.shoulder_fillet_sanity(2.1, published_kt=2.0, chart_id="X")
    assert reported["state"] == "REPORTED"
    assert reported["ratio_to_published"] == pytest.approx(1.05)
    for out in (unset, reported):
        assert "passed" not in out and "within_tolerance" not in out


def test_the_gci_safety_factor_is_the_cited_three_grid_value_and_is_an_argument():
    import f08_v2_payload as payload

    assert ctl.GCI_SAFETY_FACTOR is payload.SAFETY  # one registered value, not a copy
    assert ctl.GCI_SAFETY_FACTOR == 1.25 and "Roache" in ctl.GCI_SOURCE
    wide = ctl.richardson_gci(2.9, 2.7, 2.1, safety_factor=2.5)
    narrow = ctl.richardson_gci(2.9, 2.7, 2.1)
    assert wide["halfwidth"] == pytest.approx(2.0 * narrow["halfwidth"])
    assert math.isfinite(narrow["extrapolated"])
