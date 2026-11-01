"""Stress CONTROLS for the F08 2.0 deck: code verification of its stress observer against published closed forms.

Both controls go through the deck's OWN Gmsh/ccx/observer path (`f08_deck_v2`, with its optional `control` case key); no
separate mesh or solver is introduced. Nothing here runs a solve: the module builds the control cases, the three-rung
refinement ladder, the analytic references and the verdicts from the solver's `.dat` text.

1. KIRSCH (the PASS/FAIL control). A plate with a small circular through-hole under uniform axial tension has, in an
   infinite plate, the peak stress 3 x the nominal stress at the hole wall, at 90 degrees to the load (G. Kirsch, Z. VDI 42,
   1898, pp. 797-807). The control passes iff Kt = 3 lies inside this control's OWN Richardson-extrapolated value
   +/- its GCI band from its three refinement rungs, AND the observed order is positive and the rungs converge
   monotonically. No tolerance is chosen here. A fixed percentage band, if ever wanted, is a `HUMAN_INPUT` parameter
   that refuses when unset.
   Finite width: the plate is WIDE (hole diameter / width = `KIRSCH_DEFAULT["hole_radius_mm"] * 2 / width`, 0.05 by
   default) and NO finite-width correction is applied. The effect is small and not corrected: one verification source
   cites Peterson giving about 3.04 at a/W = 0.1, so the effect at a/W = 0.025 is smaller still (an estimate, not a
   registered value). The plate is thin (t = a / 2) so the field is plane stress, where the infinite-plate factor holds.
2. SHOULDER-FILLET SANITY (reports, never decides). A Peterson shoulder fillet in bending is the closest published case
   to the rib-root fillet. It is read from a chart, so its published Kt and chart id stay `HUMAN_INPUT` until confirmed from
   the source, and `shoulder_fillet_sanity` only reports the ratio. This module builds no stepped-bar geometry.
3. CANTILEVER (a report). A rib-less plate under the deck's own pad load has the elementary root bending stress
   sigma = 6 P (L - pad_x / 2) / (W t^2). The observed set is the elements touching the clamped root face, whose peak
   includes the clamp's local constraint (it is not a pure beam stress), so the control reports the ratio of the observer's peak
   to beam theory and decides nothing. Its tolerance is `HUMAN_INPUT`.

The GCI safety factor is the published three-grid convention Fs = 1.25 (P. J. Roache, "Perspective: A Method for Uniform
Reporting of Grid Refinement Studies", J. Fluids Eng. 116(3), 1994, pp. 405-413), a named constant, not a Carbon choice;
it is an argument so another can be passed.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f08_deck as v1
import f08_deck_v2 as v2

HUMAN_INPUT = v2.HUMAN_INPUT
#: Roache (1994): the three-grid factor of safety.
GCI_SAFETY_FACTOR = 1.25
#: Each rung halves the local element size near the observed feature.
REFINEMENT_RATIO = 2.0
KIRSCH_KT = 3.0
KIRSCH_SOURCE = "G. Kirsch, Z. Ver. Dtsch. Ing. 42 (1898) 797-807"
GCI_SOURCE = "P. J. Roache, J. Fluids Eng. 116(3) (1994) 405-413"

#: Geometry defaults (mm). The hole is small against the width (2a/W = 0.05) and the plate thin (t = a/2).
KIRSCH_DEFAULT = {
    "length_mm": 200.0,
    "width_mm": 80.0,
    "thickness_mm": 1.0,
    "hole_radius_mm": 2.0,
}
PLAIN_DEFAULT = {"length_mm": 220.0, "width_mm": 20.0, "thickness_mm": 6.0}


class ControlRefused(v2.Refused):
    """A control that cannot give a verdict (too few rungs, a missing .dat block, an unset owner value)."""


def _control_case(geometry, control, alloy, damping_ratio):
    case = {
        **geometry,
        "rib_height_mm": 0.0,
        "rib_thickness_mm": 0.0,
        "relief_length_mm": 0.0,
        "load_angle_deg": 0.0,
        "load_offset_frac": 0.0,
        "damping_ratio": damping_ratio,
        "alloy": alloy,
        "control": control,
    }
    case.pop("hole_radius_mm", None)
    return v2.validate_case(case)


def kirsch_case(alloy, *, damping_ratio=0.01, **geometry):
    """The Kirsch hole-in-plate case (uniform axial traction on the free end face, unit resultant)."""
    merged = {**KIRSCH_DEFAULT, **geometry}
    radius = merged["hole_radius_mm"]
    return _control_case(
        merged, {"kind": "hole_plate", "hole_radius_mm": radius}, alloy, damping_ratio
    )


def plain_plate_case(alloy, *, damping_ratio=0.01, **geometry):
    """The rib-less cantilever plate under the deck's own pad load (unit resultant)."""
    return _control_case(
        {**PLAIN_DEFAULT, **geometry}, {"kind": "plain_plate"}, alloy, damping_ratio
    )


def ladder(fillet_h_coarse_mm, global_h_mm, *, ratio=REFINEMENT_RATIO):
    """Three rungs, coarse to fine: ``[{"h_mm": ..., "fillet_h_mm": ...}, ...]``. The local size near the observed feature
    shrinks by ``ratio`` per rung; the global size is fixed."""
    if not (ratio > 1.0 and fillet_h_coarse_mm > 0 and global_h_mm > 0):
        raise ControlRefused("ladder_arguments_out_of_range")
    return [
        {"h_mm": global_h_mm, "fillet_h_mm": fillet_h_coarse_mm / ratio**k}
        for k in range(3)
    ]


def rung_scripts(case, rungs):
    """The deck's Gmsh program for each rung (the deck's own path; nothing is run here)."""
    return [v2.gmsh_script_v2(case, r["h_mm"], r["fillet_h_mm"]) for r in rungs]


# ---------------------------------------------------------------- analytic references (unit resultant load, N and mm)


def kirsch_nominal_mpa(case):
    """The gross nominal axial stress of the unit end traction: P / (W t), the stress Kirsch's 3 refers to."""
    return 1.0 / (case["width_mm"] * case["thickness_mm"])


def plain_nominal_mpa(case):
    """Elementary beam theory at the root for the unit pad load, acting at the pad centre (L - pad_x / 2)."""
    return v2.cantilever_root_bending_stress(
        1.0, case["length_mm"] - v1.PAD_X / 2, case["width_mm"], case["thickness_mm"]
    )


# ---------------------------------------------------------------- the solver's output


def static_peak_mpa(dat_text):
    """The peak von Mises over the FILLET (observed) set of the control's single static step: the last stress block of
    the .dat. A control deck has no modal blocks, so there is exactly one."""
    blocks = v2.parse_stress_blocks(dat_text)
    if not blocks:
        raise ControlRefused("control_stress_block_missing")
    return v2.peak_von_mises(blocks[-1])["peak_von_mises_mpa"]


# ---------------------------------------------------------------- Richardson and GCI


def richardson_gci(
    fine, medium, coarse, *, ratio=REFINEMENT_RATIO, safety_factor=GCI_SAFETY_FACTOR
):
    """Three-grid Richardson extrapolation and GCI of a scalar at constant refinement ``ratio`` (fine < medium < coarse).

    ``order`` p = ln((coarse - medium) / (medium - fine)) / ln(ratio); ``extrapolated`` = fine + (fine - medium) /
    (ratio**p - 1); ``halfwidth`` = ``safety_factor`` x |fine - medium| / (ratio**p - 1). ``monotone`` is True when
    both successive differences share a sign and neither is zero; only then are p and the extrapolation defined
    (otherwise they are None and the control cannot pass)."""
    d_fine, d_coarse = medium - fine, coarse - medium
    monotone = d_fine != 0 and d_coarse != 0 and (d_fine > 0) == (d_coarse > 0)
    out = {
        "values": [fine, medium, coarse],
        "ratio": ratio,
        "monotone": monotone,
        "order": None,
        "extrapolated": None,
        "halfwidth": None,
        "safety_factor": safety_factor,
        "gci_source": GCI_SOURCE,
    }
    if not monotone:
        return out
    order = math.log(d_coarse / d_fine) / math.log(ratio)
    out["order"] = order
    if order > 0:
        scale = ratio**order - 1.0
        out["extrapolated"] = fine - d_fine / scale
        out["halfwidth"] = safety_factor * abs(d_fine) / scale
    return out


# ---------------------------------------------------------------- verdicts


def kirsch_verdict(rung_dats, case, *, safety_factor=GCI_SAFETY_FACTOR):
    """The Kirsch control from the three rungs' .dat texts, ``rung_dats``: ``{fillet_h_mm: dat_text}`` (any order).

    PASSES iff the observed order is positive, the rungs converge monotonically, and Kt = 3 lies in
    ``extrapolated +/- halfwidth`` of the rungs' own Kt = peak / nominal. Refuses fewer or more than three rungs; it
    never uses a fixed percentage."""
    if len(rung_dats) != 3:
        raise ControlRefused("kirsch_needs_exactly_three_rungs")
    sizes = sorted(rung_dats)  # fine to coarse
    ratios = [sizes[1] / sizes[0], sizes[2] / sizes[1]]
    if abs(ratios[0] - ratios[1]) > 1e-9 * ratios[0]:
        raise ControlRefused("rungs_not_at_a_constant_refinement_ratio")
    nominal = kirsch_nominal_mpa(case)
    kts = [static_peak_mpa(rung_dats[h]) / nominal for h in sizes]
    gci = richardson_gci(*kts, ratio=ratios[0], safety_factor=safety_factor)
    inside = (
        gci["order"] is not None
        and gci["order"] > 0
        and gci["extrapolated"] is not None
        and abs(KIRSCH_KT - gci["extrapolated"]) <= gci["halfwidth"]
    )
    return {
        "control": "kirsch_hole_in_plate",
        "passed": bool(gci["monotone"] and inside),
        "published_kt": KIRSCH_KT,
        "source": KIRSCH_SOURCE,
        "rung_fillet_h_mm": sizes,
        "kt_by_rung": kts,
        "nominal_mpa": nominal,
        "richardson": gci,
        "finite_width": "none applied: wide plate, 2a/W = "
        f"{2 * case['control']['hole_radius_mm'] / case['width_mm']:.3g}",
    }


def plain_plate_report(dat_text, case, *, tolerance=HUMAN_INPUT):
    """The cantilever control: the observer's peak against beam theory. Reports the ratio; with ``tolerance`` unset it
    states no verdict (a set tolerance is the owner's, and only then is ``within_tolerance`` given).
    """
    peak = static_peak_mpa(dat_text)
    nominal = plain_nominal_mpa(case)
    out = {
        "control": "rib_less_cantilever",
        "peak_mpa": peak,
        "beam_theory_mpa": nominal,
        "ratio": peak / nominal,
        "tolerance": tolerance,
    }
    if tolerance != HUMAN_INPUT:
        out["within_tolerance"] = abs(out["ratio"] - 1.0) <= tolerance
    return out


def shoulder_fillet_sanity(
    measured_kt, *, published_kt=HUMAN_INPUT, chart_id=HUMAN_INPUT
):
    """The Peterson shoulder-fillet sanity control. It REPORTS and never decides: the published Kt and the chart id are
    read from the source by a person (they stay `HUMAN_INPUT` here), and the result has no pass or fail field.
    """
    out = {
        "control": "shoulder_fillet_in_bending",
        "measured_kt": measured_kt,
        "published_kt": published_kt,
        "chart_id": chart_id,
    }
    if HUMAN_INPUT in (published_kt, chart_id):
        out["state"] = "NOT_CONFIGURED"
    else:
        out["state"] = "REPORTED"
        out["ratio_to_published"] = measured_kt / published_kt
    return out
