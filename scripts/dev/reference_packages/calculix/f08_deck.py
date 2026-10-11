"""f08 triage decks and observer for the pinned CalculiX image (REFERENCE-PACKAGES-01).

    python3 f08_deck.py write LABEL OUTDIR [--h MM] [--modes N] [--control beam]
    python3 f08_deck.py observe CASEDIR

Geometry (packet f08 section 2): cantilever plate L x W x t, two upper ribs
(height hr, thickness tr) along the full length at y = +-W/4, a through-plate
cable relief centred at (L/2, 0), length lr in x and 20 mm in y with 3 mm
rounded corners; root x = 0 fully clamped. The pinned Gmsh image meshes it
with quadratic tetrahedra (C3D10) and imprints the 5 x 10 mm tip pad and the
2 x 2 mm probe patch (x = L/2, y = W/2 - 8) on the top face. A uniform 1 N
+z traction on the pad becomes consistent nodal loads (6-node faces: corners
0, mid-sides A/3); the probe observer is the patch's area-weighted mean.

One ccx process per case: the eigen step (N retained modes, stored), three
constant-modal-damping steady-state steps (zeta 0.005, 0.01, 0.02 over
80-600 Hz, points bracketed by the eigenfrequencies) and the static step.
The observer recomputes every curve from ccx's mass-normalised modes
(f08_proof's projection), searches each damping curve on a grid no coarser
than a tenth of every in-band half-power bandwidth, and evaluates the
12/24/48 truncations of the same basis. Verdict values are diagnostics; the
f08 acceptance tolerances are HUMAN_INPUT.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f08_proof as proof

ROOT = HERE.parents[3]
PANELS = ROOT / "docs/development/challenge_pipeline/round1/reference-route-panels.json"
MESH_IMAGE = (
    "ghcr.io/carbonphysicsai/carbon-motor-reference@sha256:"
    "599521e79786ee0326a0754ba0545f51ee9665adff73c3515c8d4b8ba24c1c05"
)
E, NU, RHO = proof.E, proof.NU, proof.RHO  # MPa, -, t/mm^3
ZETAS, BAND_HZ = proof.ZETAS, proof.BAND_HZ
LIMITS = {
    "mass_kg": 0.45,
    "static_mm_per_n": 0.03,
    "dynamic_mm_per_n": 0.15,
}  # packet buyer anchors
RELIEF_W, RELIEF_R, PAD_X, PAD_Y, PROBE = 20.0, 3.0, 5.0, 10.0, 2.0
COMMAND = "ccx -i case > ccx.log 2>&1"


def panel_case(label):
    family = json.loads(PANELS.read_text())["families"]["f08"]
    row = next(c for c in family["public_cases"] if c["label"] == label)
    return dict(zip(family["panel_fields"], row["parameters"]))


BEAM_CONTROL = {"length_mm": 220.0, "width_mm": 20.0, "thickness_mm": 6.0,
                "rib_height_mm": 0.0, "rib_thickness_mm": 0.0, "relief_length_mm": 0.0}  # fmt: skip


def gmsh_script(case, h_mm):
    return f"""
import json, math, gmsh
case = {json.dumps(case)}
L, W, t = case["length_mm"], case["width_mm"], case["thickness_mm"]
hr, tr, lr = case["rib_height_mm"], case["rib_thickness_mm"], case["relief_length_mm"]
gmsh.initialize(["-nt", "1"])
gmsh.option.setNumber("General.Terminal", 0)
occ = gmsh.model.occ
body = [(3, occ.addBox(0, -W / 2, 0, L, W, t))]
if hr > 0:
    ribs = [(3, occ.addBox(0, s * W / 4 - tr / 2, t, L, tr, hr)) for s in (-1, 1)]
    body, _ = occ.fuse(body, ribs)
if lr > 0:
    face = occ.addRectangle(L / 2 - lr / 2, -{RELIEF_W} / 2, -1, lr, {RELIEF_W}, roundedRadius={RELIEF_R})
    cutter = occ.extrude([(2, face)], 0, 0, t + 2)
    body, _ = occ.cut(body, [e for e in cutter if e[0] == 3])
pad = occ.addRectangle(L - {PAD_X}, -{PAD_Y} / 2, t, {PAD_X}, {PAD_Y})
probe = occ.addRectangle(L / 2 - {PROBE} / 2, W / 2 - 8 - {PROBE} / 2, t, {PROBE}, {PROBE})
occ.fragment(body, [(2, pad), (2, probe)])
occ.synchronize()
e = 1e-6
def faces(x0, y0, z0, x1, y1, z1):
    return [tg for d, tg in gmsh.model.getEntitiesInBoundingBox(x0 - e, y0 - e, z0 - e, x1 + e, y1 + e, z1 + e, 2)]
pad_faces = faces(L - {PAD_X}, -{PAD_Y} / 2, t, L, {PAD_Y} / 2, t)
probe_faces = faces(L / 2 - {PROBE} / 2, W / 2 - 9, t, L / 2 + {PROBE} / 2, W / 2 - 7, t)
root_faces = faces(0, -W, -1, 0, W, t + hr + 1)
p_tip = occ.addPoint(L - {PAD_X} / 2, 0, t)
p_probe = occ.addPoint(L / 2, W / 2 - 8, t)
occ.synchronize()
gmsh.model.mesh.embed(0, [p_tip], 2, pad_faces[0])
gmsh.model.mesh.embed(0, [p_probe], 2, probe_faces[0])
vols = [tg for d, tg in gmsh.model.getEntities(3)]
cad_volume = sum(occ.getMass(3, v) for v in vols)
gmsh.option.setNumber("Mesh.MeshSizeMax", {h_mm})
gmsh.option.setNumber("Mesh.MeshSizeMin", {h_mm} / 4)
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
            tets.append(c[:8] + [c[9], c[8]])  # gmsh -> ccx C3D10 edge order
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
def vol(c):
    a, b, cc, d = (coords[i] for i in c[:4])
    u = [b[k] - a[k] for k in range(3)]; v = [cc[k] - a[k] for k in range(3)]; w = [d[k] - a[k] for k in range(3)]
    return (u[0] * (v[1] * w[2] - v[2] * w[1]) - u[1] * (v[0] * w[2] - v[2] * w[0]) + u[2] * (v[0] * w[1] - v[1] * w[0])) / 6
volumes = [vol(c) for c in tets]
assert min(volumes) > 0, "inverted element"
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
    fh.write("*NSET,NSET=ROOT\\n")
    for n in sorted(root):
        fh.write(f"{{n}}\\n")
meta = {{"cad_volume_mm3": cad_volume, "mesh_volume_mm3": sum(volumes), "nodes": len(coords), "elements": len(tets),
        "pad_tri6": tri6(pad_faces), "probe_tri6": tri6(probe_faces),
        "tip_node": nearest((L - {PAD_X} / 2, 0, t)), "probe_node": nearest((L / 2, W / 2 - 8, t))}}
used = {{n for tri in meta["pad_tri6"] + meta["probe_tri6"] for n in tri}} | {{meta["tip_node"], meta["probe_node"]}}
meta["coords"] = {{str(n): coords[n] for n in sorted(used)}}
json.dump(meta, open("mesh.json", "w"))
gmsh.finalize()
"""


def face_weights(tris, coords):
    """Consistent weights of a uniform unit traction: mid-side nodes A/3."""
    weights = {}
    for tri in tris:
        a, b, c = (coords[str(n)] for n in tri[:3])
        u = [b[k] - a[k] for k in range(3)]
        v = [c[k] - a[k] for k in range(3)]
        cross = (
            u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0],
        )
        area = 0.5 * math.sqrt(sum(x * x for x in cross))
        for n in tri[3:]:
            weights[n] = weights.get(n, 0.0) + area / 3.0
    return weights


def write_case(case, out, h_mm=3.0, modes=48):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "make_mesh.py").write_text(gmsh_script(case, h_mm))
    subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "--user", f"{os.getuid()}:{os.getgid()}",
         "-v", f"{out.resolve()}:/w", "-w", "/w", MESH_IMAGE, "python3", "make_mesh.py"],
        check=True, capture_output=True,
    )  # fmt: skip
    meta = json.loads((out / "mesh.json").read_text())
    pad = face_weights(meta["pad_tri6"], meta["coords"])
    total = sum(pad.values())
    loads = {n: w / total for n, w in pad.items()}  # 1 N resultant
    obs = sorted(
        set(loads)
        | set(face_weights(meta["probe_tri6"], meta["coords"]))
        | {meta["tip_node"], meta["probe_node"]}
    )
    load = "".join(f"{n},3,{f:.12g}\n" for n, f in sorted(loads.items()))
    lines = ["*HEADING", f"f08 triage {json.dumps(case)} h={h_mm} modes={modes}", "*INCLUDE,INPUT=mesh.inp",
             "*NSET,NSET=OBS"] + [str(n) for n in obs] + [
             "*BOUNDARY", "ROOT,1,3", "*MATERIAL,NAME=AL", "*ELASTIC", f"{E},{NU}", "*DENSITY", f"{RHO}",
             "*SOLID SECTION,ELSET=EALL,MATERIAL=AL"]  # fmt: skip
    deck = "\n".join(lines) + "\n"
    deck += (
        f"*STEP\n*FREQUENCY,STORAGE=YES\n{modes}\n*NODE PRINT,NSET=OBS\nU\n*END STEP\n"
    )
    deck += proof.ssd_steps(modes, load, "OBS")
    deck += f"*STEP\n*STATIC\n*CLOAD,OP=NEW\n{load}*NODE PRINT,NSET=OBS\nU\n*END STEP\n"
    (out / "case.inp").write_text(deck)
    deck_meta = {"case": case, "h_mm": h_mm, "modes": modes, "zetas": list(ZETAS), "band_hz": list(BAND_HZ),
                 "mesh_image": MESH_IMAGE, "loads": {str(n): f for n, f in loads.items()}}  # fmt: skip
    (out / "deck.json").write_text(
        json.dumps(deck_meta, indent=1, sort_keys=True) + "\n"
    )
    return {"nodes": meta["nodes"], "elements": meta["elements"]}


def _probe_mean(u_by_node, weights):
    return sum(u_by_node[n] * w for n, w in weights.items()) / sum(weights.values())


def dense_grid(omegas_hz, zeta):
    lo, hi = BAND_HZ
    grid = {lo + k * 0.5 for k in range(int((hi - lo) / 0.5) + 1)}
    for f in omegas_hz:
        bw = 2 * zeta * f
        if lo - 5 * bw <= f <= hi + 5 * bw:
            step = bw / 10.0
            grid |= {f + k * step for k in range(-50, 51) if lo <= f + k * step <= hi}
    return sorted(grid)


def observe(case_dir):
    case_dir = Path(case_dir)
    deck = json.loads((case_dir / "deck.json").read_text())
    meta = json.loads((case_dir / "mesh.json").read_text())
    steps = proof.parse_dat((case_dir / "case.dat").read_text(errors="replace"))
    eig, shapes = steps[0]["eigen"], proof.mode_shapes(steps[0])
    omegas = [m["rad"] for m in eig]
    hz = [m["hz"] for m in eig]
    loads = {int(n): f for n, f in deck["loads"].items()}
    tip = meta["tip_node"]
    probe_w = face_weights(meta["probe_tri6"], meta["coords"])
    static = steps[4]["events"][0][1]
    mass_kg = RHO * meta["mesh_volume_mm3"] * 1000.0
    out = {"case": deck["case"], "h_mm": deck["h_mm"], "modes": deck["modes"],
           "mesh": {"nodes": meta["nodes"], "elements": meta["elements"]},
           "mass_kg": mass_kg, "cad_mass_kg": RHO * meta["cad_volume_mm3"] * 1000.0,
           "static_tip_mm_per_n": static[tip][2],
           "static_probe_mm_per_n": _probe_mean({n: v[2] for n, v in static.items()}, probe_w),
           "eigen_hz": hz, "in_band_modes_hz": [f for f in hz if BAND_HZ[0] <= f <= BAND_HZ[1]]}  # fmt: skip
    out["modal_static_tip_over_static"] = (
        sum(
            phi[tip] * sum(phi[n] * f for n, f in loads.items()) / w**2
            for phi, w in zip(shapes, omegas)
        )
        / static[tip][2]
    )
    damping = {}
    for zeta, step in zip(ZETAS, steps[1:4]):
        rows = proof.harmonic(step)
        ccx_tip = [(f, uz[tip]) for f, _, uz in rows]
        ccx_probe = [(f, _probe_mean(uz, probe_w)) for f, _, uz in rows]
        scale = max(abs(u) for _, u in ccx_tip)
        err = (
            max(
                abs(
                    u
                    - proof.project(shapes, omegas, loads, tip, 2 * math.pi * f, zeta)[
                        0
                    ]
                )
                for f, u in ccx_tip
            )
            / scale
        )
        ladder = {}
        for n in sorted({12, 24, 48, len(shapes)} & set(range(1, len(shapes) + 1))):
            curve_tip, curve_probe = [], []
            for f in dense_grid(hz[:n], zeta):
                w = 2 * math.pi * f
                curve_tip.append(
                    (f, proof.project(shapes[:n], omegas[:n], loads, tip, w, zeta)[0])
                )
                probe = sum(
                    proof.project(shapes[:n], omegas[:n], loads, p, w, zeta)[0] * wt
                    for p, wt in probe_w.items()
                )
                curve_probe.append((f, probe / sum(probe_w.values())))
            ladder[f"modes_{n}"] = {"tip": proof.peak(curve_tip), "probe": proof.peak(curve_probe),
                                    "grid_points": len(curve_tip)}  # fmt: skip
        damping[f"zeta_{zeta}"] = {
            "ccx_points": len(rows), "ccx_tip_peak": proof.peak(ccx_tip), "ccx_probe_peak": proof.peak(ccx_probe),
            "ccx_vs_projection_max_err_over_peak": err, "dense": ladder,
            "worst_mm_per_n": max(ladder[f"modes_{len(shapes)}"]["tip"]["mm_per_n"],
                                  ladder[f"modes_{len(shapes)}"]["probe"]["mm_per_n"]),
        }  # fmt: skip
    out["damping"] = damping
    worst = max(v["worst_mm_per_n"] for v in damping.values())
    out["diagnostic_margins"] = {
        "mass_kg": LIMITS["mass_kg"] - mass_kg,
        "static_mm_per_n": LIMITS["static_mm_per_n"] - out["static_tip_mm_per_n"],
        "dynamic_mm_per_n": LIMITS["dynamic_mm_per_n"] - worst,
    }
    out["worst_dynamic_mm_per_n"] = worst
    out["phase_convention"] = "exp(+i omega t); peak phases near -90 deg at resonance"
    (case_dir / "observed.json").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n"
    )
    return out


def beam_theory(case=BEAM_CONTROL, x_load=None):
    """Euler-Bernoulli tip compliance at the pad centroid and first frequency."""
    L, W, t = case["length_mm"], case["width_mm"], case["thickness_mm"]
    a = x_load or L - PAD_X / 2
    inertia = W * t**3 / 12.0
    static = a**3 / (3 * E * inertia)  # load and observer both at a
    f1 = 1.8751041**2 / (2 * math.pi) * math.sqrt(E * inertia / (RHO * W * t * L**4))
    return {"static_mm_per_n": static, "f1_hz": f1}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="f08_deck")
    sub = parser.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write")
    w.add_argument("label")
    w.add_argument("out", type=Path)
    w.add_argument("--h", type=float, default=3.0)
    w.add_argument("--modes", type=int, default=48)
    o = sub.add_parser("observe")
    o.add_argument("case_dir", type=Path)
    args = parser.parse_args(argv)
    if args.cmd == "write":
        case = BEAM_CONTROL if args.label == "control-beam" else panel_case(args.label)
        print(json.dumps(write_case(case, args.out, args.h, args.modes)))
    else:
        doc = observe(args.case_dir)
        print(
            json.dumps(
                {
                    k: doc[k]
                    for k in (
                        "mass_kg",
                        "static_tip_mm_per_n",
                        "in_band_modes_hz",
                        "worst_dynamic_mm_per_n",
                    )
                }
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
