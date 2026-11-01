"""f08 decks, VERSION 2.0 (Ribbed Bracket 2.0, STRESS working choice), for the pinned CalculiX image (REFERENCE-PACKAGES-01).

A NEW file beside the pinned 1.7 deck (`f08_deck.py`, never edited). Working choice (F08_20_DESIGN_20261101, a1): the
peak von Mises stress at the rib-root fillet, a local NOTCH response, against the alloy's yield limit. Added to 1.7:

- a rib-root fillet (`fillet_radius_mm`) on the four rib/plate junction lines, with local mesh refinement
  (`fillet_h_mm`, the refinement rung), and a FILLET element set for the stress output;
- `alloy` (a categorical input: its E, nu, rho and yield come from a registered table), `load_angle_deg` (the load
  direction, rotated about the x axis from +z toward +y; the resultant stays 1 N), `load_offset_frac` (the pad centre's y
  offset on the free edge) and `damping_ratio` (a condition, one steady-state sweep instead of 1.7's three bands);
- `observe_v2`: peak von Mises over the FILLET integration points, and (only when the alloy's yield and the owner's safety
  factor are registered) the ratio to the allowable.

NOTHING owner-set is invented here. OWNER-F08-V2-VALUES-01 (2026-11-01) registers the new inputs' ranges (fillet 0.5-3.0
mm, load angle 0-45 deg, load offset -0.4 to +0.4 of the width, damping 0.005-0.02), the safety factor 1.5 and the three
alloy ids. OWNER-F08-V2-ALLOYS-SIGNED-01 signs the alloys' E, nu, rho and Fty (MIL-HDBK-5J, two transcriptions): the
vendored table is byte-identical to the signed file and checked on load; a changed or missing file puts `HUMAN_INPUT` back
and a production deck, observation or yield margin refuses. `test_mode=True` accepts clearly synthetic values and marks
every output `"tables": "TEST_ONLY"`.

The mesh runs in the pinned Gmsh image (not available on a desk); the tests here check the generated script compiles and
carry the stress parser, the von Mises reduction and the closed-form controls on synthetic data. NO solve is run by this
module's tests.
"""

from __future__ import annotations

import ast
import hashlib
import itertools
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f08_deck as v1  # the pinned 1.7 deck: imported for its constants, never edited
import f08_proof as proof

HUMAN_INPUT = "HUMAN_INPUT"
GEOMETRY = (
    "length_mm",
    "width_mm",
    "thickness_mm",
    "rib_height_mm",
    "rib_thickness_mm",
    "relief_length_mm",
)
NEW_INPUTS = (
    "fillet_radius_mm",
    "load_angle_deg",
    "load_offset_frac",
    "damping_ratio",
)
CATEGORICAL = "alloy"
ALL_INPUTS = (*GEOMETRY, *NEW_INPUTS, CATEGORICAL)
#: OWNER-F08-V2-VALUES-01 (owner-approved, 2026-11-01): the registered ranges of the NEW inputs.
#: load_offset_frac is the pad centre's y offset as a fraction of the plate width (0 = the centre).
DECISION = "OWNER-F08-V2-VALUES-01"
RANGES = {
    "fillet_radius_mm": (0.5, 3.0),
    "load_angle_deg": (0.0, 45.0),
    "load_offset_frac": (-0.4, 0.4),
    "damping_ratio": (0.005, 0.02),
}
#: The three registered alloy ids, in registration order (the categorical id is the position), and the SIGNED table
#: (OWNER-F08-V2-ALLOYS-SIGNED-01, 2026-11-01): MIL-HDBK-5J, two independent transcriptions, E, nu, rho and the selected Fty
#: (A-basis LT where A/B are given, S-basis where only S is, the lowest over the product forms covering the plate range).
#: The vendored file is byte-identical to the signed one (sha256 below, checked on every load); a changed or missing file
#: leaves HUMAN_INPUT in place, so a production deck, observation or yield margin is REFUSED.
ALLOY_IDS = ("6061-T6", "4130-normalized", "Ti-6Al-4V-annealed")
ALLOY_DECISION = "OWNER-F08-V2-ALLOYS-SIGNED-01"
ALLOY_FILE = "f08_v2_alloy_table.json"
ALLOY_SHA256 = "sha256:d5b8cc5638c3fa8d1bfd517b98d61c4735d59e3e6dd832c843e347dfd7b7fc10"
#: The signed file's ids for the three alloy ids above.
ALLOY_FILE_IDS = {
    "6061-T6": "AL_6061_T651_plate",
    "4130-normalized": "AISI_4130_normalized",
    "Ti-6Al-4V-annealed": "TI_6AL_4V_annealed_plate",
}
#: Unit conversions to the deck's mm-t-N-s system: GPa -> MPa, kg/m^3 -> t/mm^3.
GPA_TO_MPA = 1000.0
KG_M3_TO_T_MM3 = 1e-12


def _load_signed_alloys():
    """``(table, status)``: the three alloys' E, nu, rho and Fty from the signed file when its bytes hash to the signed
    sha256, else HUMAN_INPUT placeholders and the reason (fail closed)."""
    closed = {
        name: {
            field: HUMAN_INPUT
            for field in ("E_mpa", "nu", "rho_t_per_mm3", "yield_mpa")
        }
        for name in ALLOY_IDS
    }
    path = Path(__file__).with_name(ALLOY_FILE)
    try:
        raw = path.read_bytes().replace(b"\r\n", b"\n")
    except OSError:
        return closed, "ALLOY_FILE_MISSING"
    if "sha256:" + hashlib.sha256(raw).hexdigest() != ALLOY_SHA256:
        return closed, "ALLOY_FILE_NOT_THE_SIGNED_ONE"
    rows = {row["id"]: row for row in json.loads(raw)["alloys"]}
    table = {
        name: {
            "E_mpa": rows[file_id]["E_GPa"] * GPA_TO_MPA,
            "nu": rows[file_id]["nu"],
            "rho_t_per_mm3": rows[file_id]["rho_kg_m3"] * KG_M3_TO_T_MM3,
            "yield_mpa": rows[file_id]["Fty_selected"]["MPa"],
        }
        for name, file_id in ALLOY_FILE_IDS.items()
    }
    return table, "SIGNED"


def alloy_source():
    """What a deck built from the signed alloys records: the owner decision, the file name and its sha256."""
    return {"decision": ALLOY_DECISION, "sha256": ALLOY_SHA256, "file": ALLOY_FILE}


ALLOYS, ALLOY_STATUS = _load_signed_alloys()
ALLOY_FIELDS = ("E_mpa", "nu", "rho_t_per_mm3", "yield_mpa")
#: Owner values for the stress margin.
SAFETY_FACTOR = (
    1.5  # OWNER-F08-V2-VALUES-01: the constraint is static fillet stress <= Fty / 1.5
)
STRESS_FIXED = {
    "step": "*EL PRINT,ELSET=FILLET: S at the integration points (C3D10: 4 per element)",
    "reduction": "von Mises",
    # Validator ruling 2026-11-01: PRIMARY = worst-band DYNAMIC von Mises at the fillet (modal superposition of the
    # mass-normalised modal stresses under the harmonic load, peak over the band and over the oscillation phase);
    # the STATIC peak is the safety-constraint output.
    "primary": "worst_band_dynamic_von_mises",
    "constraint": "static_peak_von_mises",
}


class Refused(ValueError):
    """A case, table or output that needs an owner value that is not registered, or is out of range."""


def _need(value, name):
    if value == HUMAN_INPUT or value is None:
        raise Refused(f"{name}_not_registered")
    return value


# ---------------------------------------------------------------- inputs, tables


def validate_case(case, *, ranges=None, test_mode=False):
    """The case's inputs, in range. A range that is HUMAN_INPUT refuses unless ``test_mode`` supplies it."""
    if case.get("control") is not None:
        return _validate_control_case(case)
    ranges = RANGES if ranges is None else ranges
    missing = [name for name in ALL_INPUTS if name not in case]
    if missing:
        raise Refused("case_missing_" + ",".join(missing))
    for name in NEW_INPUTS:
        bounds = ranges.get(name, HUMAN_INPUT)
        if bounds == HUMAN_INPUT:
            if not test_mode:
                raise Refused(f"range_not_registered_{name}")
            continue
        low, high = bounds
        if not (type(case[name]) in (int, float) and low <= case[name] <= high):
            raise Refused(f"{name}_out_of_range")
    W, t = case["width_mm"], case["thickness_mm"]
    if case["rib_height_mm"] <= 0 or case["rib_thickness_mm"] <= 0:
        raise Refused("fillet_needs_a_rib")
    rf = case["fillet_radius_mm"]
    if not (0 < rf < min(case["rib_height_mm"], t, case["rib_thickness_mm"])):
        raise Refused("fillet_radius_exceeds_the_junction")
    if abs(case["load_offset_frac"]) * W + v1.PAD_Y / 2 > W / 2:
        raise Refused("load_pad_leaves_the_plate")
    if not (0 < case["damping_ratio"] < 1):
        raise Refused("damping_ratio_out_of_range")
    return dict(case)


def _validate_control_case(case):
    """A CONTROL case (the optional ``control`` key): plain geometry, no ribs, no fillet. It checks the control's own
    shape only; it grants no range of a production input."""
    control = case["control"]
    kind = control.get("kind") if isinstance(control, dict) else None
    if kind not in CONTROL_KINDS:
        raise Refused("control_kind_not_registered")
    need = (
        *GEOMETRY,
        "load_angle_deg",
        "load_offset_frac",
        "damping_ratio",
        CATEGORICAL,
    )
    missing = [name for name in need if name not in case]
    if missing:
        raise Refused("case_missing_" + ",".join(missing))
    if (
        case["rib_height_mm"] != 0
        or case["rib_thickness_mm"] != 0
        or case["relief_length_mm"] != 0
    ):
        raise Refused("control_case_has_no_ribs_or_relief")
    if case["load_angle_deg"] != 0 or (
        kind == "hole_plate" and case["load_offset_frac"] != 0
    ):
        raise Refused("control_load_is_fixed")
    if kind == "hole_plate":
        radius = control.get("hole_radius_mm")
        if not (type(radius) in (int, float) and 0 < radius < case["width_mm"] / 2):
            raise Refused("hole_radius_out_of_range")
        if set(control) != {"kind", "hole_radius_mm"}:
            raise Refused("control_keys_not_registered")
    elif set(control) != {"kind"}:
        raise Refused("control_keys_not_registered")
    return dict(case)


def material(alloy, *, table=None, test_mode=False):
    """The alloy's registered row, or a refusal. The default table is the owner-signed one (HUMAN_INPUT placeholders if
    its file is not the signed one); ``table`` supplies another (test values)."""
    signed = table is None
    table = ALLOYS if table is None else table
    row = table.get(alloy)
    if row is None:
        raise Refused("alloy_not_registered")
    for field in ALLOY_FIELDS:
        if row.get(field) in (HUMAN_INPUT, None):
            raise Refused(f"alloy_value_not_registered_{field}")
    if not (row["E_mpa"] > 0 and 0 < row["nu"] < 0.5 and row["rho_t_per_mm3"] > 0):
        raise Refused("alloy_value_out_of_range")
    out = {**row, "tables": "TEST_ONLY" if test_mode else "REGISTERED"}
    if signed and not test_mode:
        out["source"] = alloy_source()
    return out


# ---------------------------------------------------------------- load


def load_components(angle_deg):
    """Unit load direction in the (y, z) plane: 0 deg = +z (1.7's load), 90 deg = +y."""
    angle = math.radians(angle_deg)
    return (math.sin(angle), math.cos(angle))


def load_lines(loads, angle_deg):
    """``*CLOAD`` lines for per-node unit-resultant z weights ``loads`` along the chosen direction."""
    fy, fz = load_components(angle_deg)
    out = []
    for node, weight in sorted(loads.items()):
        if fy:
            out.append(f"{node},2,{weight * fy:.12g}\n")
        out.append(f"{node},3,{weight * fz:.12g}\n")
    return "".join(out)


def axial_load_lines(loads):
    """``*CLOAD`` lines for per-node unit-resultant weights along +x (a uniform axial traction on the free end face; used
    only by the ``hole_plate`` control)."""
    return "".join(
        f"{node},1,{weight:.12g}\n" for node, weight in sorted(loads.items())
    )


# ---------------------------------------------------------------- mesh script


CONTROL_KINDS = ("plain_plate", "hole_plate")


def _pad_block():
    return f"""pad = occ.addRectangle(L - {v1.PAD_X}, off - {v1.PAD_Y} / 2, t, {v1.PAD_X}, {v1.PAD_Y})
probe = occ.addRectangle(L / 2 - {v1.PROBE} / 2, W / 2 - 8 - {v1.PROBE} / 2, t, {v1.PROBE}, {v1.PROBE})
occ.fragment(body, [(2, pad), (2, probe)])
occ.synchronize()"""


def _face_lines():
    return f"""pad_faces = faces(L - {v1.PAD_X}, off - {v1.PAD_Y} / 2, t, L, off + {v1.PAD_Y} / 2, t)
probe_faces = faces(L / 2 - {v1.PROBE} / 2, W / 2 - 9, t, L / 2 + {v1.PROBE} / 2, W / 2 - 7, t)
root_faces = faces(0, -W, -1, 0, W, t + hr + 1)"""


def _tip_points():
    return f"""p_tip = occ.addPoint(L - {v1.PAD_X} / 2, off, t)
p_probe = occ.addPoint(L / 2, W / 2 - 8, t)
occ.synchronize()
gmsh.model.mesh.embed(0, [p_tip], 2, pad_faces[0])
gmsh.model.mesh.embed(0, [p_probe], 2, probe_faces[0])"""


def _control_pieces(control):
    """The Gmsh pieces of a CONTROL case, in `gmsh_script_v2`'s order: ``(RF_OFF, BODY, PADBLOCK, FACELINES, POINTS,
    TIP_NODE, PROBE_NODE)``. The deck's own refinement field, element-set and stress path is kept; only the geometry, the
    loaded face and the observed set change.

    - ``plain_plate``: the rib-less plate (no fillet), the deck's own pad load, and the observed set is the elements touching
      the clamped root face. Beam theory gives its root bending stress.
    - ``hole_plate``: a plate with a through-hole of ``hole_radius_mm`` at mid-length on the centreline, a uniform axial
      traction on the free end face, and the observed set is the elements touching the hole wall (Kirsch).
    """
    kind = control.get("kind") if isinstance(control, dict) else None
    if kind == "plain_plate":
        return (
            'rf, off = t, case["load_offset_frac"] * W',
            """body = [(3, occ.addBox(0, -W / 2, 0, L, W, t))]
e = 1e-6
occ.synchronize()""",
            _pad_block(),
            _face_lines() + "\nfillet_faces = root_faces",
            _tip_points(),
            f"nearest((L - {v1.PAD_X} / 2, off, t))",
            "nearest((L / 2, W / 2 - 8, t))",
        )
    if kind == "hole_plate":
        return (
            f"rf, off = {float(control['hole_radius_mm'])!r}, 0.0",
            """body = [(3, occ.addBox(0, -W / 2, 0, L, W, t))]
e = 1e-6
hole = occ.addCylinder(L / 2, 0, -1, 0, 0, t + 2, rf)
body, _ = occ.cut(body, [(3, hole)])
occ.synchronize()""",
            "occ.synchronize()",
            """pad_faces = faces(L, -W, -1, L, W, t + 1)
probe_faces = []
root_faces = faces(0, -W, -1, 0, W, t + 1)
fillet_faces = [tg for d, tg in gmsh.model.getEntities(2) if gmsh.model.getType(d, tg) == "Cylinder"]""",
            "occ.synchronize()",
            "nearest((L, 0.0, t / 2))",
            "nearest((L / 2, W / 2, t / 2))",
        )
    raise Refused("control_kind_not_registered")


def gmsh_script_v2(case, h_mm, fillet_h_mm):
    """The Gmsh program for one case: 1.7's body, the fillet on the four rib junction lines, a refinement field around
    the fillet faces, the pad at ``load_offset_frac`` and a FILLET element set. Returned as text; it runs in MESH_IMAGE.

    A case with the optional ``control`` key is a code-verification CONTROL case (see `CONTROL_KINDS`): the same program
    with the rib/fillet, load and observation pieces swapped. A case without the key gets exactly the text it always got
    (pinned in tests/cpu/test_f08_deck_v2.py).
    """
    control = case.get("control")
    if control is None:
        RF_OFF = 'rf, off = case["fillet_radius_mm"], case["load_offset_frac"] * W'
        BODY = """body = [(3, occ.addBox(0, -W / 2, 0, L, W, t))]
ribs = [(3, occ.addBox(0, s * W / 4 - tr / 2, t, L, tr, hr)) for s in (-1, 1)]
body, _ = occ.fuse(body, ribs)
occ.synchronize()
e = 1e-6
junction = []
for s in (-1, 1):
    for side in (-1, 1):
        y = s * W / 4 + side * tr / 2
        found = gmsh.model.getEntitiesInBoundingBox(-e, y - e, t - e, L + e, y + e, t + e, 1)
        junction += [tag for d, tag in found if abs(occ.getMass(1, tag) - L) < 1e-6]
assert len(junction) == 4, junction
filleted = occ.fillet([body[0][1]], junction, [rf] * 4, True)
body = [(3, filleted[0][1])]"""
        PADBLOCK = _pad_block()
        FACELINES = (
            _face_lines()
            + """
fillet_faces = [tg for d, tg in gmsh.model.getEntities(2) if gmsh.model.getType(d, tg) == "Cylinder"]"""
        )
        POINTS = _tip_points()
        TIP_NODE = f"nearest((L - {v1.PAD_X} / 2, off, t))"
        PROBE_NODE = "nearest((L / 2, W / 2 - 8, t))"
    else:
        RF_OFF, BODY, PADBLOCK, FACELINES, POINTS, TIP_NODE, PROBE_NODE = (
            _control_pieces(control)
        )
    return f"""
import json, math, gmsh
case = {json.dumps(case)}
L, W, t = case["length_mm"], case["width_mm"], case["thickness_mm"]
hr, tr, lr = case["rib_height_mm"], case["rib_thickness_mm"], case["relief_length_mm"]
{RF_OFF}
gmsh.initialize(["-nt", "1"])
gmsh.option.setNumber("General.Terminal", 0)
occ = gmsh.model.occ
{BODY}
if lr > 0:
    face = occ.addRectangle(L / 2 - lr / 2, -{v1.RELIEF_W} / 2, -1, lr, {v1.RELIEF_W}, roundedRadius={v1.RELIEF_R})
    cutter = occ.extrude([(2, face)], 0, 0, t + 2)
    body, _ = occ.cut(body, [x for x in cutter if x[0] == 3])
{PADBLOCK}
def faces(x0, y0, z0, x1, y1, z1):
    return [tg for d, tg in gmsh.model.getEntitiesInBoundingBox(x0 - e, y0 - e, z0 - e, x1 + e, y1 + e, z1 + e, 2)]
{FACELINES}
{POINTS}
field = gmsh.model.mesh.field
field.add("Distance", 1)
field.setNumbers(1, "SurfacesList", fillet_faces)
field.add("Threshold", 2)
field.setNumber(2, "InField", 1)
field.setNumber(2, "SizeMin", {fillet_h_mm})
field.setNumber(2, "SizeMax", {h_mm})
field.setNumber(2, "DistMin", rf)
field.setNumber(2, "DistMax", 4 * rf)
field.setAsBackgroundMesh(2)
vols = [tg for d, tg in gmsh.model.getEntities(3)]
cad_volume = sum(occ.getMass(3, v) for v in vols)
gmsh.option.setNumber("Mesh.MeshSizeMax", {h_mm})
gmsh.option.setNumber("Mesh.MeshSizeMin", {fillet_h_mm})
gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
gmsh.option.setNumber("Mesh.ElementOrder", 2)
gmsh.option.setNumber("Mesh.SecondOrderLinear", 0)
gmsh.option.setNumber("Mesh.Algorithm3D", 1)
gmsh.option.setNumber("Mesh.RandomSeed", 1)
gmsh.model.mesh.generate(3)
tags, xyz, _ = gmsh.model.mesh.getNodes()
coords = {{int(n): (xyz[3 * i], xyz[3 * i + 1], xyz[3 * i + 2]) for i, n in enumerate(tags)}}
tets = []
for v in vols:
    types, _, nodes = gmsh.model.mesh.getElements(3, v)
    for ty, ns in zip(types, nodes):
        assert ty == 11, ty
        ns = [int(x) for x in ns]
        for k in range(0, len(ns), 10):
            c = ns[k:k + 10]
            tets.append(c[:8] + [c[9], c[8]])
def tri6(face_tags):
    out = []
    for f in face_tags:
        types, _, nodes = gmsh.model.mesh.getElements(2, f)
        for ty, ns in zip(types, nodes):
            assert ty == 9, ty
            ns = [int(x) for x in ns]
            out += [ns[k:k + 6] for k in range(0, len(ns), 6)]
    return out
root = set()
for f in root_faces:
    n, _, _ = gmsh.model.mesh.getNodes(2, f, includeBoundary=True)
    root |= {{int(x) for x in n}}
fillet_nodes = set()
for f in fillet_faces:
    n, _, _ = gmsh.model.mesh.getNodes(2, f, includeBoundary=True)
    fillet_nodes |= {{int(x) for x in n}}
fillet_elements = [i for i, c in enumerate(tets, 1) if fillet_nodes & set(c)]
def vol(c):
    a, b, cc, d = (coords[i] for i in c[:4])
    u = [b[k] - a[k] for k in range(3)]; v = [cc[k] - a[k] for k in range(3)]; w = [d[k] - a[k] for k in range(3)]
    return (u[0] * (v[1] * w[2] - v[2] * w[1]) - u[1] * (v[0] * w[2] - v[2] * w[0]) + u[2] * (v[0] * w[1] - v[1] * w[0])) / 6
volumes = [vol(c) for c in tets]
assert min(volumes) > 0, "inverted element"
assert fillet_elements, "no element touches the fillet"
def nearest(p):
    return min(coords, key=lambda n: sum((coords[n][k] - p[k]) ** 2 for k in range(3)))
with open("mesh.inp", "w") as fh:
    fh.write("*NODE\\n")
    for n in sorted(coords):
        x, y, z = coords[n]
        fh.write(f"{{n}},{{x:.12g}},{{y:.12g}},{{z:.12g}}\\n")
    fh.write("*ELEMENT,TYPE=C3D10,ELSET=EALL\\n")
    for i, c in enumerate(tets, 1):
        fh.write(f"{{i}}," + ",".join(map(str, c)) + "\\n")
    fh.write("*ELSET,ELSET=FILLET\\n")
    for i in range(0, len(fillet_elements), 8):
        fh.write(",".join(map(str, fillet_elements[i:i + 8])) + "\\n")
    fh.write("*NSET,NSET=ROOT\\n")
    for n in sorted(root):
        fh.write(f"{{n}}\\n")
meta = {{"cad_volume_mm3": cad_volume, "mesh_volume_mm3": sum(volumes), "nodes": len(coords), "elements": len(tets),
        "fillet_elements": len(fillet_elements), "pad_tri6": tri6(pad_faces), "probe_tri6": tri6(probe_faces),
        "tip_node": {TIP_NODE}, "probe_node": {PROBE_NODE}}}
used = {{n for tri in meta["pad_tri6"] + meta["probe_tri6"] for n in tri}} | {{meta["tip_node"], meta["probe_node"]}}
meta["coords"] = {{str(n): coords[n] for n in sorted(used)}}
json.dump(meta, open("mesh.json", "w"))
gmsh.finalize()
"""


def script_compiles(text) -> bool:
    """The generated Gmsh program is valid Python (a desk check; Gmsh itself is not imported)."""
    ast.parse(text)
    return True


# ---------------------------------------------------------------- ccx deck


def deck_text(case, meta, mat, *, modes=48, loads=None):
    """The CalculiX input for one case: eigen step, ONE steady-state sweep at the case's damping ratio, and the static
    step with the FILLET stress print. ``meta`` is mesh.json; ``mat`` is `material(...)`.
    """
    pad = v1.face_weights(meta["pad_tri6"], meta["coords"])
    total = math.fsum(pad.values())
    weights = loads or {n: w / total for n, w in pad.items()}
    control = case.get("control")
    if control is not None and control.get("kind") == "hole_plate":
        lines_text = axial_load_lines(weights)
    else:
        lines_text = load_lines(weights, case["load_angle_deg"])
    obs = sorted(
        set(weights)
        | set(v1.face_weights(meta["probe_tri6"], meta["coords"]))
        | {meta["tip_node"], meta["probe_node"]}
    )
    lines = [
        "*HEADING",
        f"f08 2.0 {json.dumps(case, sort_keys=True)} modes={modes} tables={mat['tables']}",
        # Numerical settings (Validator, 2026-11-01): fixed, never tuned; the refinement ladder verifies them.
        f"** numerical settings: {json.dumps(numerical_settings(), sort_keys=True)}",
        *(
            [f"** alloy table: {mat['source']['decision']} {mat['source']['sha256']}"]
            if mat.get("source")
            else []
        ),
        "*INCLUDE,INPUT=mesh.inp",
        "*NSET,NSET=OBS",
        *map(str, obs),
        "*BOUNDARY",
        "ROOT,1,3",
        "*MATERIAL,NAME=ALLOY",
        "*ELASTIC",
        f"{mat['E_mpa']},{mat['nu']}",
        "*DENSITY",
        f"{mat['rho_t_per_mm3']}",
        "*SOLID SECTION,ELSET=EALL,MATERIAL=ALLOY",
    ]
    deck = "\n".join(lines) + "\n"
    if (
        control is None
    ):  # a control case is a static verification: no eigen or steady-state step
        deck += (
            f"*STEP\n*FREQUENCY,STORAGE=YES\n{modes}\n*NODE PRINT,NSET=OBS\nU\n"
            "*EL PRINT,ELSET=FILLET\nS\n*END STEP\n"
        )
        zeta = case["damping_ratio"]
        deck += (
            f"*STEP\n*STEADY STATE DYNAMICS\n{proof.BAND_HZ[0]},{proof.BAND_HZ[1]},{proof.POINTS},{proof.BIAS}\n"
            f"*MODAL DAMPING\n1,{modes},{zeta}\n*CLOAD,OP=NEW\n{lines_text}"
            "*NODE PRINT,NSET=OBS\nU\n*END STEP\n"
        )
    deck += (
        f"*STEP\n*STATIC\n*CLOAD,OP=NEW\n{lines_text}*NODE PRINT,NSET=OBS\nU\n"
        "*EL PRINT,ELSET=FILLET\nS\n*END STEP\n"
    )
    return deck


# ---------------------------------------------------------------- stress observation

NUM = proof.NUM


def von_mises(s):
    """Von Mises of (sxx, syy, szz, sxy, sxz, syz)."""
    sxx, syy, szz, sxy, sxz, syz = s
    return math.sqrt(
        0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2)
        + 3.0 * (sxy**2 + sxz**2 + syz**2)
    )


def parse_stress(dat_text):
    """ccx ``*EL PRINT ... S`` rows: ``[(element, integration_point, (sxx, syy, szz, sxy, sxz, syz)), ...]``."""
    rows = []
    reading = False
    row = re.compile(rf"^\s*(\d+)\s+(\d+)\s+((?:{NUM}\s+){{5}}{NUM})\s*$")
    for line in dat_text.splitlines():
        if "stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz)" in line:
            reading = True
            continue
        if reading:
            match = row.match(line)
            if match:
                rows.append(
                    (
                        int(match.group(1)),
                        int(match.group(2)),
                        tuple(float(x) for x in match.group(3).split()),
                    )
                )
            elif line.strip():
                reading = False
    return rows


def peak_von_mises(rows):
    if not rows:
        raise Refused("no_fillet_stress_rows")
    best = max(rows, key=lambda r: von_mises(r[2]))
    return {
        "peak_von_mises_mpa": von_mises(best[2]),
        "element": best[0],
        "integration_point": best[1],
        "rows": len(rows),
    }


def stress_margin(peak, mat, safety_factor=None):
    """peak / (yield / SF), when the alloy's yield and the owner's safety factor are registered; else a refusal."""
    sf = _need(
        SAFETY_FACTOR if safety_factor is None else safety_factor, "safety_factor"
    )
    if not (type(sf) in (int, float) and sf >= 1.0):
        raise Refused("safety_factor_out_of_range")
    allowable = _need(mat.get("yield_mpa"), "yield") / sf
    return {
        "allowable_mpa": allowable,
        "stress_ratio": peak["peak_von_mises_mpa"] / allowable,
        "tables": mat["tables"],
    }


def observe_v2(case, dat_text, mat, *, safety_factor=None):
    """The stress observation of one solved case: the fillet peak and (when registered) its margin."""
    peak = peak_von_mises(parse_stress(dat_text))
    out = {"case": case, "tables": mat["tables"], **peak, "stress_fixed": STRESS_FIXED}
    try:
        out["margin"] = stress_margin(peak, mat, safety_factor)
    except Refused as refusal:
        out["margin"] = {"refused": str(refusal)}
    return out


# ---------------------------------------------------------------- closed-form controls (no solve)


def cantilever_root_bending_stress(load_n, length_mm, width_mm, thickness_mm):
    """Elementary beam theory: the extreme-fibre bending stress at the root of a rectangular cantilever (no ribs) under
    a tip load P: sigma = 6 P L / (W t^2), in MPa for N and mm."""
    return 6.0 * load_n * length_mm / (width_mm * thickness_mm**2)


def notch_control(measured_peak, nominal, published_kt, *, tolerance):
    """Compare a solved peak/nominal concentration with a PUBLISHED Kt for the same notch. ``published_kt`` and
    ``tolerance`` are owner values from a cited source; HUMAN_INPUT refuses."""
    kt = _need(published_kt, "published_kt")
    tol = _need(tolerance, "notch_tolerance")
    ratio = measured_peak / nominal
    return {"measured_kt": ratio, "published_kt": kt, "ok": abs(ratio - kt) <= tol * kt}


# ---------------------------------------------------------------- miner features, rungs, solve record

PROPERTY_FEATURES = ("E_mpa", "nu", "rho_t_per_mm3", "yield_mpa")


def feature_names():
    """The numeric feature vector a model sees per case: the 6 geometry inputs, the 4 new numeric inputs, the alloy's
    categorical id and the alloy's registered property vector (so a model can generalise through properties instead of
    memorising labels)."""
    return (*GEOMETRY, *NEW_INPUTS, "alloy_id", *PROPERTY_FEATURES)


def alloy_ids(table=None):
    """Stable categorical ids: the registered alloys in registration order (0, 1, 2)."""
    table = ALLOYS if table is None else table
    return {name: index for index, name in enumerate(table)}


def features(case, *, table=None):
    """The case's feature vector in `feature_names()` order. The property values come from the registered table, so an
    unregistered alloy or a HUMAN_INPUT value refuses here exactly as `material` does.
    """
    table = ALLOYS if table is None else table
    row = material(case["alloy"], table=table)
    ids = alloy_ids(table)
    return [
        *(float(case[name]) for name in (*GEOMETRY, *NEW_INPUTS)),
        float(ids[case["alloy"]]),
        *(float(row[name]) for name in PROPERTY_FEATURES),
    ]


def observe_rungs(case, rung_dats, mat):
    """The fillet-refinement ladder for one case (capture 5): ``rung_dats`` maps ``fillet_h_mm`` to that rung's .dat
    text. Reports each rung's peak von Mises and the relative change between successive (finer) rungs, so U per output
    can be derived from the raw rungs. Refuses fewer than two rungs."""
    if len(rung_dats) < 2:
        raise Refused("fillet_refinement_needs_two_rungs")
    ordered = sorted(rung_dats, reverse=True)  # coarse to fine
    peaks = [
        {"fillet_h_mm": h, **peak_von_mises(parse_stress(rung_dats[h]))}
        for h in ordered
    ]
    changes = [
        {
            "from_h_mm": a["fillet_h_mm"],
            "to_h_mm": b["fillet_h_mm"],
            "rel_change": (b["peak_von_mises_mpa"] - a["peak_von_mises_mpa"])
            / a["peak_von_mises_mpa"],
        }
        for a, b in itertools.pairwise(peaks)
    ]
    return {
        "case": case,
        "tables": mat["tables"],
        "rungs": peaks,
        "successive": changes,
    }


def solve_record(
    case, *, deck, mesh_meta, dat_text, image_ids, fillet_h_mm, wall_s=None
):
    """The per-case reference-solve record (capture 7): what was solved, with what, with digests; no stress values.
    ``image_ids`` binds the mesher and solver images; ``wall_s`` is the measured wall time when known.
    """
    import hashlib

    def sha(text):
        return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()

    return {
        "schema": "carbon.f08.solve-record.v2",
        "case": case,
        "fillet_h_mm": fillet_h_mm,
        "deck_sha256": sha(deck),
        "dat_sha256": sha(dat_text),
        "mesh": {
            key: mesh_meta.get(key)
            for key in ("nodes", "elements", "fillet_elements", "mesh_volume_mm3")
        },
        "images": dict(image_ids),
        "wall_s": wall_s,
    }


# ---------------------------------------------------------------- dynamic (primary) fillet stress

PHASES = 72  # oscillation phases scanned for the von Mises amplitude of an oscillating stress tensor
HEADER = "stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz)"
_ROW = re.compile(rf"^\s*(\d+)\s+(\d+)\s+((?:{NUM}\s+){{5}}{NUM})\s*$")


def parse_stress_blocks(dat_text):
    """Every ``*EL PRINT ... S`` block of a .dat, in file order: a list of `parse_stress`-style row lists."""
    blocks = []
    current = None
    for line in dat_text.splitlines():
        if HEADER in line:
            current = []
            blocks.append(current)
            continue
        if current is not None:
            match = _ROW.match(line)
            if match:
                current.append(
                    (
                        int(match.group(1)),
                        int(match.group(2)),
                        tuple(float(x) for x in match.group(3).split()),
                    )
                )
            elif line.strip():
                current = None
    return blocks


def modal_stress_tensors(dat_text, modes):
    """The mass-normalised modal stress fields from the frequency step: ``(keys, array[mode, row, 6])``. The first
    ``modes`` FILLET blocks of the .dat are the modes in order; the static step's block is the one after them.
    """
    blocks = parse_stress_blocks(dat_text)
    if len(blocks) < modes + 1:
        raise Refused("modal_stress_blocks_missing")
    keys = [(e, ip) for e, ip, _ in blocks[0]]
    for block in blocks[:modes]:
        if [(e, ip) for e, ip, _ in block] != keys:
            raise Refused("modal_stress_rows_differ")
    return keys, np.array([[list(r[2]) for r in block] for block in blocks[:modes]])


def _vm_rows(tensors):
    """Von Mises of an array[..., 6] of (sxx, syy, szz, sxy, sxz, syz)."""
    sxx, syy, szz, sxy, sxz, syz = (tensors[..., k] for k in range(6))
    return np.sqrt(
        0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2)
        + 3.0 * (sxy**2 + sxz**2 + syz**2)
    )


def dynamic_stress_amplitude(modal_stress, modal, f_hz, zeta):
    """The von Mises amplitude of the oscillating stress at ``f_hz``, per N: the complex modal sum
    sigma(f) = sum_j q_j(f) sigma_j, then the largest von Mises over one oscillation (``PHASES`` phases) and over every
    integration point. ``modal`` is v1.modal_data's list (omega, pf per mode)."""
    w = 2.0 * math.pi * f_hz
    q = np.array(
        [
            m["pf"] / (m["omega"] ** 2 - w * w + 2j * zeta * m["omega"] * w)
            for m in modal
        ]
    )
    sigma = np.tensordot(q, modal_stress, axes=(0, 0))  # [row, 6], complex
    phase = np.exp(1j * np.linspace(0.0, math.pi, PHASES, endpoint=False))
    oscillating = np.real(sigma[None, :, :] * phase[:, None, None])  # [phase, row, 6]
    return float(_vm_rows(oscillating).max())


def worst_band_dynamic_stress(modal_stress, modal, zeta, *, band_hz=None):
    """The primary output: the peak of `dynamic_stress_amplitude` over the registered band at the case's damping, found
    on the same grid rule as the displacement peak (every in-band mode resolved) and refined by golden section.
    """
    lo, hi = proof.BAND_HZ if band_hz is None else band_hz
    grid = [f for f in v1.dense_grid([m["hz"] for m in modal], zeta) if lo <= f <= hi]

    def value(f):
        return dynamic_stress_amplitude(modal_stress, modal, f, zeta)

    values = [value(f) for f in grid]
    top = max(values)
    i = values.index(top)
    a, b = grid[max(i - 1, 0)], grid[min(i + 1, len(grid) - 1)]
    f_peak = v1._golden(value, a, b)
    refined = value(f_peak)
    best_f, best = (f_peak, refined) if refined > top else (grid[i], top)
    return {
        "frequency_hz": best_f,
        "dynamic_von_mises_mpa_per_n": best,
        "grid_points": len(grid),
        "band_hz": [lo, hi],
        "damping_ratio": zeta,
    }


def observe_dynamic_rungs(case, rung_inputs, mat):
    """The dynamic fillet stress over the refinement ladder (capture 5). ``rung_inputs`` maps ``fillet_h_mm`` to
    ``(modal_stress, modal)``; reports each rung's worst-band value and the change between successive rungs.
    """
    if len(rung_inputs) < 2:
        raise Refused("fillet_refinement_needs_two_rungs")
    peaks = []
    for h in sorted(rung_inputs, reverse=True):
        stress, modal = rung_inputs[h]
        peaks.append(
            {
                "fillet_h_mm": h,
                **worst_band_dynamic_stress(stress, modal, case["damping_ratio"]),
            }
        )
    changes = [
        {
            "from_h_mm": a["fillet_h_mm"],
            "to_h_mm": b["fillet_h_mm"],
            "rel_change": (
                b["dynamic_von_mises_mpa_per_n"] - a["dynamic_von_mises_mpa_per_n"]
            )
            / a["dynamic_von_mises_mpa_per_n"],
        }
        for a, b in itertools.pairwise(peaks)
    ]
    return {
        "case": case,
        "tables": mat["tables"],
        "rungs": peaks,
        "successive": changes,
    }


def numerical_settings():
    """The numerical settings of the dynamic fillet-stress observation, recorded in every deck header. They are fixed
    (never tuned); the refinement ladder is what verifies them."""
    return {
        "oscillation_phases": PHASES,
        "peak_refinement": "golden section on the bracketing grid points",
        "peak_refinement_rel": 1e-6,
        "frequency_grid": "f08_deck.dense_grid: <= 0.1 half-power bandwidth near each mode, 0.5 Hz elsewhere",
        "band_hz": list(proof.BAND_HZ),
        "stress_points": "C3D10 integration points of the FILLET element set",
    }
