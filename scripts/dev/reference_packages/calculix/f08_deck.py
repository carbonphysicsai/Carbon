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
12/24/48 truncations of the same basis; every near-top crest is refined by
golden section. The buyer objective is worst-band TIP compliance; the probe
is a diagnostic (F08-READINESS-REUSE-01). Bands are the DEVELOPMENT values of
F08-SCIENCE-VALUES-01; verdicts are engineering evidence, not qualification.
"""

from __future__ import annotations

import argparse
import cmath
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
#: ccx, then the container's own cgroup CPU and memory counters (v2 or v1) for the
#: ledger; the subshell keeps ccx's exit code for the runner.
COMMAND = (
    "ccx -i case > ccx.log 2>&1; rc=$?; grep -H . /sys/fs/cgroup/cpu.stat /sys/fs/cgroup/memory.peak"
    " /sys/fs/cgroup/cpuacct/cpuacct.usage /sys/fs/cgroup/memory/memory.max_usage_in_bytes"
    " > cgroup.txt 2>/dev/null; (exit $rc)"
)
DECISION = "F08-SCIENCE-VALUES-01"
#: DEVELOPMENT bands, .agent/decisions/2026-10-15-F08-SCIENCE-VALUES-01.md (set before the triage ran).
BANDS = {
    "eigen_rel": 0.01, "peak_rel": 0.05, "location_hz": 2.0, "location_rel": 0.01,
    "phase_deg": 5.0, "phase_floor_mm_per_n": 0.015, "curve_rel": 0.05,
    "curve_abs_mm_per_n": 0.0015, "off_peak_bandwidths": 3.0, "static_rel": 0.02,
    "mass_rel": 0.005, "grid_bandwidth_fraction": 0.1, "sampling_loss_rel": 0.005,
    "mode_cutoff_hz": 900.0, "truncation_rel": 0.01, "ladder_rel": 0.01,
    "oscillator_rel": 1e-6, "oscillator_phase_deg": 0.01,
    "beam_static_rel": 0.02, "beam_freq_rel": 0.01, "beam_peak_rel": 0.03,
}  # fmt: skip


#: Measured cost model for one f08 launch (static + 48-mode eigen + three damping
#: sweeps), fitted to the 2026-10-15 local runs (cgroup CPU and memory peak vs mesh
#: nodes, 25k-137k nodes; triage-f08-observed.json). Host profile
#: local-dev-4vcpu-15g-contended: CPU-s are comparable, local wall-s are not.
COST_MODEL = {
    "cpu_s": (9.912e-06, 1.5187),
    "mem_mib": (6.571e-03, 1.1026),
    "cpu_margin": 1.2,
    "mem_margin": 1.2,
    "wall_per_cpu_uncontended": 1.25,
    "basis": "power-law fit to 12 local f08 launches; margins cover the worst observed/fit ratio (1.15 CPU, 1.08 memory)",
}


def estimate(nodes):
    """estimate_cpu_s / estimate_wall_s / estimate_mem_mib for one launch (bulk runner fields)."""
    a, b = COST_MODEL["cpu_s"]
    c, d = COST_MODEL["mem_mib"]
    cpu = COST_MODEL["cpu_margin"] * a * nodes**b
    return {
        "estimate_cpu_s": round(cpu, 1),
        "estimate_wall_s": round(cpu * COST_MODEL["wall_per_cpu_uncontended"], 1),
        "estimate_mem_mib": round(COST_MODEL["mem_margin"] * c * nodes**d + 64),
    }


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


#: Gmsh inside MESH_IMAGE. A host without Docker (a native pod) sets
#: CARBON_F08_NATIVE_GMSH=1 and must provide this exact Gmsh on python3's path;
#: the frozen digests are only reproducible with it.
GMSH_VERSION = "4.15.2"


def mesh(out):
    """Run make_mesh.py in the case directory, in MESH_IMAGE or natively."""
    if os.environ.get("CARBON_F08_NATIVE_GMSH") == "1":
        found = subprocess.run(
            ["python3", "-c", "import gmsh; print(gmsh.__version__)"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()  # fmt: skip
        if found != GMSH_VERSION:
            raise SystemExit(f"native Gmsh {found} differs from pinned {GMSH_VERSION}")
        subprocess.run(
            ["python3", "make_mesh.py"], cwd=out, check=True, capture_output=True
        )
        return
    subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "--cpus", "1", "--memory", "4g",
         "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{Path(out).resolve()}:/w", "-w", "/w", MESH_IMAGE, "python3", "make_mesh.py"],
        check=True, capture_output=True,
    )  # fmt: skip


def write_case(case, out, h_mm=3.0, modes=48):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "make_mesh.py").write_text(gmsh_script(case, h_mm))
    mesh(out)
    meta = json.loads((out / "mesh.json").read_text())
    pad = face_weights(meta["pad_tri6"], meta["coords"])
    total = math.fsum(pad.values())  # correctly rounded: same digest on any Python
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
    """F1: <= 0.1 half-power bandwidth within 5 bandwidths of each mode, 0.5 Hz elsewhere."""
    lo, hi = BAND_HZ
    grid = {lo + k * 0.5 for k in range(int((hi - lo) / 0.5) + 1)}
    for f in omegas_hz:
        bw = 2 * zeta * f
        if lo - 5 * bw <= f <= hi + 5 * bw:
            step = bw * BANDS["grid_bandwidth_fraction"]
            grid |= {f + k * step for k in range(-50, 51) if lo <= f + k * step <= hi}
    return sorted(grid)


def modal_data(eig, shapes, loads, tip, probe_w):
    """Per-mode omega, load participation phi.f, tip and probe-mean phi."""
    total = sum(probe_w.values())
    return [
        {
            "omega": m["rad"],
            "hz": m["hz"],
            "pf": sum(phi[n] * f for n, f in loads.items()),
            "tip": phi[tip],
            "probe": sum(phi[n] * w for n, w in probe_w.items()) / total,
        }
        for m, phi in zip(eig, shapes)
    ]


def response(modal, f_hz, zeta, key="tip", n=None):
    """Mass-normalised modal superposition, exp(+i omega t), constant zeta."""
    w = 2 * math.pi * f_hz
    total = 0j
    for m in modal[:n]:
        wj = m["omega"]
        total += m[key] * m["pf"] / (wj * wj - w * w + 2j * zeta * wj * w)
    return total


def _golden(fun, a, b, rel=1e-6):
    g = (math.sqrt(5) - 1) / 2
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = fun(c), fun(d)
    while b - a > rel * max(abs(b), 1.0):
        if fc >= fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = fun(c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = fun(d)
    return (a + b) / 2


def resolved_peak(curve_fn, grid):
    """F1/F2: grid crest, then golden-section refinement of every near-top crest."""
    vals = [abs(curve_fn(f)) for f in grid]
    top = max(vals)
    best_f, best_u = grid[vals.index(top)], curve_fn(grid[vals.index(top)])
    for i, v in enumerate(vals):
        left = vals[i - 1] if i > 0 else -1.0
        right = vals[i + 1] if i + 1 < len(vals) else -1.0
        if v < 0.99 * top or v < left or v < right:
            continue
        a, b = grid[max(i - 1, 0)], grid[min(i + 1, len(grid) - 1)]
        f = _golden(lambda x: abs(curve_fn(x)), a, b)
        u = curve_fn(f)
        if abs(u) > abs(best_u):
            best_f, best_u = f, u
    return {
        "hz": best_f,
        "mm_per_n": abs(best_u),
        "phase_deg": math.degrees(cmath.phase(best_u)),
        "grid_mm_per_n": top,
        "sampling_loss_rel": (abs(best_u) - top) / abs(best_u),
    }


def location_ok(f, f_ref):
    return abs(f - f_ref) <= min(BANDS["location_hz"], BANDS["location_rel"] * f_ref)


def wrapped_deg(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def observe(case_dir):
    """Tip is the buyer objective (F08-READINESS-REUSE-01); the probe is diagnostic."""
    case_dir = Path(case_dir)
    out = observe_data(
        json.loads((case_dir / "deck.json").read_text()),
        json.loads((case_dir / "mesh.json").read_text()),
        proof.parse_dat((case_dir / "case.dat").read_text(errors="replace")),
    )
    (case_dir / "observed.json").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n"
    )
    return out


def observe_data(deck, meta, steps):
    """observe() on parsed inputs: deck.json, mesh.json and ccx's parsed steps."""
    eig, shapes = steps[0]["eigen"], proof.mode_shapes(steps[0])
    hz = [m["hz"] for m in eig]
    loads = {int(n): f for n, f in deck["loads"].items()}
    tip = meta["tip_node"]
    probe_w = {
        int(n): w for n, w in face_weights(meta["probe_tri6"], meta["coords"]).items()
    }
    modal = modal_data(eig, shapes, loads, tip, probe_w)
    static = steps[4]["events"][0][1]
    static_tip = static[tip][2]
    mass_kg = RHO * meta["mesh_volume_mm3"] * 1000.0
    cad_mass_kg = RHO * meta["cad_volume_mm3"] * 1000.0
    modal_static = sum(m["tip"] * m["pf"] / m["omega"] ** 2 for m in modal)
    out = {"case": deck["case"], "h_mm": deck["h_mm"], "modes": deck["modes"],
           "mesh": {"nodes": meta["nodes"], "elements": meta["elements"]},
           "mass_kg": mass_kg, "cad_mass_kg": cad_mass_kg,
           "mass_mesh_vs_cad_rel": abs(mass_kg - cad_mass_kg) / cad_mass_kg,
           "static_tip_mm_per_n": static_tip,
           "static_probe_mm_per_n": _probe_mean({n: v[2] for n, v in static.items()}, probe_w),
           "eigen_hz": hz, "in_band_modes_hz": [f for f in hz if BAND_HZ[0] <= f <= BAND_HZ[1]],
           "modal_static_tip_over_static": modal_static / static_tip,
           "modal": modal}  # fmt: skip
    residual = abs(static_tip - modal_static)
    cutoff = hz[-1]
    damping = {}
    for zeta, step in zip(ZETAS, steps[1:4]):
        rows = proof.harmonic(step)
        ccx_tip = [(f, uz[tip]) for f, _, uz in rows]
        ccx_probe = [(f, _probe_mean(uz, probe_w)) for f, _, uz in rows]
        scale = max(abs(u) for _, u in ccx_tip)
        err = max(abs(u - response(modal, f, zeta)) for f, u in ccx_tip) / scale
        ladder = {}
        for n in sorted({12, 24, 48, len(modal)} & set(range(1, len(modal) + 1))):
            grid = dense_grid(hz[:n], zeta)
            ladder[f"modes_{n}"] = {
                "tip": resolved_peak(lambda f, n=n, z=zeta: response(modal, f, z, "tip", n), grid),
                "probe": resolved_peak(lambda f, n=n, z=zeta: response(modal, f, z, "probe", n), grid),
                "grid_points": len(grid),
            }  # fmt: skip
        full = ladder[f"modes_{len(modal)}"]["tip"]
        row = {
            "ccx_points": len(rows), "ccx_tip_peak": proof.peak(ccx_tip), "ccx_probe_peak": proof.peak(ccx_probe),
            "ccx_vs_projection_max_err_over_peak": err, "dense": ladder,
            "worst_mm_per_n": full["mm_per_n"], "worst_hz": full["hz"],
            "probe_diagnostic_mm_per_n": ladder[f"modes_{len(modal)}"]["probe"]["mm_per_n"],
            "truncation_bound_rel": (residual / (1 - (BAND_HZ[1] / cutoff) ** 2) / full["mm_per_n"]
                                     if cutoff > BAND_HZ[1] else None),
        }  # fmt: skip
        if "modes_24" in ladder and len(modal) >= 48:
            half = ladder["modes_24"]["tip"]
            row["ladder_24_vs_48"] = {
                "peak_rel": abs(half["mm_per_n"] - full["mm_per_n"]) / full["mm_per_n"],
                "location_ok": location_ok(half["hz"], full["hz"]),
            }
        damping[f"zeta_{zeta}"] = row
    out["damping"] = damping
    out["mode_ladder"] = mode_ladder_verdict(out)
    worst = max(v["worst_mm_per_n"] for v in damping.values())
    out["diagnostic_margins"] = {
        "mass_kg": LIMITS["mass_kg"] - mass_kg,
        "static_mm_per_n": LIMITS["static_mm_per_n"] - static_tip,
        "dynamic_mm_per_n": LIMITS["dynamic_mm_per_n"] - worst,
    }
    out["worst_dynamic_mm_per_n"] = worst
    out["probe_diagnostic_worst_mm_per_n"] = max(
        v["probe_diagnostic_mm_per_n"] for v in damping.values()
    )
    out["objective"] = (
        "worst-band TIP dynamic compliance over all damping; probe is diagnostic only"
    )
    out["bands_decision"] = DECISION
    out["phase_convention"] = "exp(+i omega t); peak phases near -90 deg at resonance"
    return out


def mode_ladder_verdict(obs):
    """M2: cutoff, residual-flexibility truncation bound and 24->48 stability."""
    rows = obs["damping"].values()
    checks = {
        "cutoff_hz": obs["eigen_hz"][-1],
        "cutoff_ok": obs["eigen_hz"][-1] >= BANDS["mode_cutoff_hz"],
        "truncation_ok": all(
            r["truncation_bound_rel"] is not None
            and r["truncation_bound_rel"] <= BANDS["truncation_rel"]
            for r in rows
        ),
        "ladder_ok": all(
            "ladder_24_vs_48" in r
            and r["ladder_24_vs_48"]["peak_rel"] <= BANDS["ladder_rel"]
            and r["ladder_24_vs_48"]["location_ok"]
            for r in rows
        ),
        "sampling_ok": all(
            r["dense"][f"modes_{len(obs['eigen_hz'])}"]["tip"]["sampling_loss_rel"]
            <= BANDS["sampling_loss_rel"]
            for r in rows
        ),
        "mass_ok": obs["mass_mesh_vs_cad_rel"] <= BANDS["mass_rel"],
    }
    keys = ("cutoff_ok", "truncation_ok", "ladder_ok", "sampling_ok", "mass_ok")
    checks["verdict"] = "PASS" if all(checks[k] for k in keys) else "UNRESOLVED_MODES"
    return checks


def _rel(a, b):
    return abs(a - b) / abs(b)


def compare_rungs(coarse, fine):
    """V1-V7: one geometry at a coarser mesh against its finest rung."""
    hz_c, hz_f = coarse["eigen_hz"], fine["eigen_hz"]
    upto = next((i for i, f in enumerate(hz_f) if f > BAND_HZ[1]), len(hz_f) - 1)
    eigen = [_rel(a, b) for a, b in zip(hz_c[: upto + 1], hz_f[: upto + 1])]
    out = {
        "eigen_max_rel": max(eigen),
        "eigen_ok": max(eigen) <= BANDS["eigen_rel"],
        "static_rel": _rel(coarse["static_tip_mm_per_n"], fine["static_tip_mm_per_n"]),
        "mass_rel": _rel(coarse["mass_kg"], fine["mass_kg"]),
        "damping": {},
    }
    out["static_ok"] = out["static_rel"] <= BANDS["static_rel"]
    out["mass_ok"] = out["mass_rel"] <= BANDS["mass_rel"]
    ok = out["eigen_ok"] and out["static_ok"] and out["mass_ok"]
    for (key, c), f in zip(coarse["damping"].items(), fine["damping"].values()):
        zeta = float(key.split("_")[1])
        pc = c["dense"][f"modes_{len(coarse['eigen_hz'])}"]["tip"]
        pf = f["dense"][f"modes_{len(fine['eigen_hz'])}"]["tip"]
        row = {
            "peak_rel": _rel(pc["mm_per_n"], pf["mm_per_n"]),
            "location_hz": abs(pc["hz"] - pf["hz"]),
            "location_ok": location_ok(pc["hz"], pf["hz"]),
            "phase_deg": wrapped_deg(pc["phase_deg"], pf["phase_deg"]),
        }
        row["peak_ok"] = row["peak_rel"] <= BANDS["peak_rel"]
        row["phase_ok"] = (
            pf["mm_per_n"] < BANDS["phase_floor_mm_per_n"]
            or row["phase_deg"] <= BANDS["phase_deg"]
        )
        row["curve_worst_excess_mm_per_n"] = _curve_excess(coarse, fine, zeta)
        row["curve_ok"] = row["curve_worst_excess_mm_per_n"] <= 0.0
        ok &= all(row[k] for k in ("peak_ok", "location_ok", "phase_ok", "curve_ok"))
        out["damping"][key] = row
    out["verdict"] = "PASS" if ok else "FAIL"
    return out


def _curve_excess(coarse, fine, zeta):
    """V5 off-peak: max(|du| - (0.05|u_ref| + 0.0015)) outside the peak windows."""
    half = BANDS["off_peak_bandwidths"] * 2 * zeta
    centres = [m["hz"] for m in coarse["modal"] + fine["modal"]]
    worst = -math.inf
    for f in dense_grid([m["hz"] for m in fine["modal"]], zeta):
        if any(abs(f - c) <= half * c for c in centres):
            continue
        ref = response(fine["modal"], f, zeta)
        got = response(coarse["modal"], f, zeta)
        allowed = BANDS["curve_rel"] * abs(ref) + BANDS["curve_abs_mm_per_n"]
        worst = max(worst, abs(got - ref) - allowed)
    return worst


def convergence(rungs):
    """V1-V9 over a geometry's {h: observed} ladder; finest rung is the reference."""
    hs = sorted(rungs, reverse=True)
    fine = rungs[hs[-1]]
    out = {"reference_h_mm": hs[-1], "rungs": {}}
    for h in hs[:-1]:
        out["rungs"][f"h{h:g}"] = compare_rungs(rungs[h], fine)
    if len(hs) == 3:
        a, b, c = (rungs[h] for h in hs)
        series = {"f1_hz": [r["eigen_hz"][0] for r in (a, b, c)]}
        for key in a["damping"]:
            series[f"peak_{key}"] = [
                r["damping"][key]["worst_mm_per_n"] for r in (a, b, c)
            ]
        out["asymptotic"] = {
            k: abs(v[1] - v[2]) <= abs(v[0] - v[1]) for k, v in series.items()
        }
        out["asymptotic_ok"] = all(out["asymptotic"].values())
    return out


BETA_L = (
    1.8751040687,
    4.6940911330,
    7.8547574382,
    10.9955407349,
    14.1371683910,
    17.2787595321,
)


def beam_theory(case=BEAM_CONTROL, x_load=None):
    """Euler-Bernoulli cantilever at the pad centroid: static, modes and modal FRF."""
    L, W, t = case["length_mm"], case["width_mm"], case["thickness_mm"]
    a = x_load or L - PAD_X / 2
    inertia = W * t**3 / 12.0
    mass = RHO * W * t * L
    static = a**3 / (3 * E * inertia)  # load and observer both at a
    modes = []
    for bl in BETA_L:
        b = bl / L
        sigma = (math.cosh(bl) + math.cos(bl)) / (math.sinh(bl) + math.sin(bl))
        shape = (
            math.cosh(b * a)
            - math.cos(b * a)
            - sigma * (math.sinh(b * a) - math.sin(b * a))
        )
        omega = bl**2 * math.sqrt(E * inertia / (RHO * W * t * L**4))
        modes.append({"omega": omega, "hz": omega / (2 * math.pi), "pf": shape / math.sqrt(mass),
                      "tip": shape / math.sqrt(mass), "probe": 0.0})  # fmt: skip
    return {"static_mm_per_n": static, "f1_hz": modes[0]["hz"], "f2_hz": modes[1]["hz"],
            "modal_static_over_static": sum(m["pf"] * m["tip"] / m["omega"] ** 2 for m in modes) / static,
            "modal": modes}  # fmt: skip


def beam_control(obs, theory=None):
    """C2: 3D unribbed beam against Euler-Bernoulli (model discrepancy, not mesh error)."""
    theory = theory or beam_theory()
    share = [
        m["tip"] * m["pf"] / m["omega"] ** 2 / obs["static_tip_mm_per_n"]
        for m in obs["modal"]
    ]
    bending = [m["hz"] for m, s in zip(obs["modal"], share) if s >= 0.005]
    out = {
        "static_rel": _rel(obs["static_tip_mm_per_n"], theory["static_mm_per_n"]),
        "f1_rel": _rel(bending[0], theory["f1_hz"]),
        "f2_rel": _rel(bending[1], theory["f2_hz"]) if len(bending) > 1 else None,
        "z_bending_hz": bending[:3],
        "damping": {},
    }
    ok = (out["static_rel"] <= BANDS["beam_static_rel"] and out["f1_rel"] <= BANDS["beam_freq_rel"]
          and out["f2_rel"] is not None and out["f2_rel"] <= BANDS["beam_freq_rel"])  # fmt: skip
    for key, row in obs["damping"].items():
        zeta = float(key.split("_")[1])
        ref = resolved_peak(
            lambda f, z=zeta: response(theory["modal"], f, z),
            dense_grid([m["hz"] for m in theory["modal"]], zeta),
        )
        got = row["dense"][f"modes_{len(obs['eigen_hz'])}"]["tip"]
        r = {"eb_peak_mm_per_n": ref["mm_per_n"], "eb_peak_hz": ref["hz"],
             "peak_rel": _rel(got["mm_per_n"], ref["mm_per_n"]), "location_ok": location_ok(got["hz"], ref["hz"])}  # fmt: skip
        ok &= r["peak_rel"] <= BANDS["beam_peak_rel"] and r["location_ok"]
        out["damping"][key] = r
    out["verdict"] = "PASS" if ok else "FAIL"
    return out


def oscillator_control(check):
    """C1 on f08_proof.oscillator_check output."""
    rows = check["damping"].values()
    ok = all(
        r["max_rel_err_vs_analytic"] <= BANDS["oscillator_rel"]
        and r["max_phase_err_deg"] <= BANDS["oscillator_phase_deg"]
        and r["unretained_max_abs"] <= 1e-12
        for r in rows
    ) and all(
        m["phi_sqrt_m_minus_1"] <= BANDS["oscillator_rel"] for m in check["modes"]
    )
    return {**check, "verdict": "PASS" if ok else "FAIL", "bands_decision": DECISION}


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
