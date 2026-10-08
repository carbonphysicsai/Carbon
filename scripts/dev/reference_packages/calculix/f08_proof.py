"""f08 feature proof for the pinned CalculiX image (REFERENCE-PACKAGES-01).

#787 requires, before any f08 cost test: exact modal damping, mass-normalised
projection, the 12/24/48 mode ladder, complex phase and batched
damping/frequency outputs. Two decks demonstrate them:

    oscillators  ten uncoupled spring-mass oscillators (SPRINGA + MASS). The
                 exact answer is analytic: mode i is e_i/sqrt(m_i) and the tip
                 response is 1/(m_i (w_i^2 - w^2 + 2 i zeta w_i w)).
    plate        a clamped 220 x 80 x 6 mm Al-like C3D20R plate with the
                 packet's unit tip-pad force. One ccx process runs the eigen
                 step, three constant-modal-damping steady-state steps
                 (zeta 0.005, 0.01, 0.02) and a static step. Its complex
                 response is recomputed independently from ccx's own printed
                 mass-normalised modes; the 12/24/48 runs are the ladder.

The plate is a convention proof, not the ribbed f08 geometry and not a
reference-adequacy claim. Tolerances here are package checks only; f08's
acceptance tolerances remain HUMAN_INPUT.

    python3 f08_proof.py IMAGE OUTDIR EVIDENCE.json
"""

from __future__ import annotations

import cmath
import hashlib
import itertools
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ZETAS = (0.005, 0.01, 0.02)
BAND_HZ = (80.0, 600.0)
POINTS, BIAS = 20, 3.0
LADDER = (12, 24, 48)
# plate (mm, N, t, s)
L, W, T = 220.0, 80.0, 6.0
NX, NY, NZ = 44, 16, 2
E, NU, RHO = 70000.0, 0.33, 2.7e-9
PAD = (215.0, 220.0, -5.0, 5.0)  # x0, x1, y0, y1 on the top face, 1 N total
TIP = (217.5, 0.0, T)  # tip-pad centroid
MID = (110.0, 32.5, T)  # node nearest the packet's x=L/2, y=W/2-8 probe
# oscillators
N_OSC, OSC_MODES = 10, 6


def osc_params():
    out = []
    for i in range(N_OSC):
        m = (1.0 + 0.25 * i) * 1e-3
        f = 100.0 * 1.4**i
        out.append({"m": m, "f": f, "k": m * (2 * math.pi * f) ** 2})
    return out


def ssd_steps(nmodes, load_lines, nset):
    steps = []
    for zeta in ZETAS:
        steps.append(
            f"*STEP\n*STEADY STATE DYNAMICS\n{BAND_HZ[0]},{BAND_HZ[1]},{POINTS},{BIAS}\n"
            f"*MODAL DAMPING\n1,{nmodes},{zeta}\n*CLOAD,OP=NEW\n{load_lines}"
            f"*NODE PRINT,NSET={nset}\nU\n*END STEP\n"
        )
    return "".join(steps)


def oscillator_deck():
    lines = ["*HEADING", "f08 proof: uncoupled oscillators", "*NODE"]
    for i in range(N_OSC):
        lines += [f"{101 + i},{10.0 * i},0.,0.", f"{201 + i},{10.0 * i},0.,1."]
    for i, p in enumerate(osc_params()):
        lines += [f"*ELEMENT,TYPE=SPRINGA,ELSET=S{i}", f"{1 + i},{101 + i},{201 + i}"]
        lines += [f"*ELEMENT,TYPE=MASS,ELSET=M{i}", f"{21 + i},{201 + i}"]
        lines += [
            f"*SPRING,ELSET=S{i}",
            "",
            f"{p['k']!r}",
            f"*MASS,ELSET=M{i}",
            f"{p['m']!r}",
        ]
    lines += ["*NSET,NSET=GROUND"] + [str(101 + i) for i in range(N_OSC)]
    lines += ["*NSET,NSET=OBS"] + [str(201 + i) for i in range(N_OSC)]
    lines += ["*BOUNDARY", "GROUND,1,3", "OBS,1,2"]
    load = "".join(f"{201 + i},3,1.\n" for i in range(N_OSC))
    head = "\n".join(lines) + "\n"
    freq = f"*STEP\n*FREQUENCY,STORAGE=YES\n{OSC_MODES}\n*NODE PRINT,NSET=OBS\nU\n*END STEP\n"
    return head + freq + ssd_steps(OSC_MODES, load, "OBS"), load


def node_id(i, j, k):
    return 1 + i + (2 * NX + 1) * (j + (2 * NY + 1) * k)


def coord(i, j, k):
    return (i * L / (2 * NX), -W / 2 + j * W / (2 * NY), k * T / (2 * NZ))


CORNERS = (
    (0, 0, 0),
    (2, 0, 0),
    (2, 2, 0),
    (0, 2, 0),
    (0, 0, 2),
    (2, 0, 2),
    (2, 2, 2),
    (0, 2, 2),
)
MIDS = ((1, 0, 0), (2, 1, 0), (1, 2, 0), (0, 1, 0), (1, 0, 2), (2, 1, 2),
        (1, 2, 2), (0, 1, 2), (0, 0, 1), (2, 0, 1), (2, 2, 1), (0, 2, 1))  # fmt: skip


def plate_mesh():
    nodes = {}
    for k in range(2 * NZ + 1):
        for j in range(2 * NY + 1):
            for i in range(2 * NX + 1):
                if (i % 2) + (j % 2) + (k % 2) <= 1:
                    nodes[node_id(i, j, k)] = coord(i, j, k)
    elements = []
    for k in range(NZ):
        for j in range(NY):
            for i in range(NX):
                ids = [
                    node_id(2 * i + a, 2 * j + b, 2 * k + c)
                    for a, b, c in CORNERS + MIDS
                ]
                elements.append(ids)
    return nodes, elements


def pad_loads():
    """Consistent loads of a uniform 1 N traction on the top-face pad (8-node
    serendipity faces: corners -A p/12, mid-sides +A p/3)."""
    p = 1.0 / ((PAD[1] - PAD[0]) * (PAD[3] - PAD[2]))
    dx, dy = L / NX, W / NY
    loads = {}
    k = 2 * NZ
    for i in range(NX):
        for j in range(NY):
            x0, y0 = i * dx, -W / 2 + j * dy
            if not (x0 >= PAD[0] - 1e-9 and x0 + dx <= PAD[1] + 1e-9):
                continue
            if not (y0 >= PAD[2] - 1e-9 and y0 + dy <= PAD[3] + 1e-9):
                continue
            area = dx * dy
            for a, b in ((0, 0), (2, 0), (2, 2), (0, 2)):
                n = node_id(2 * i + a, 2 * j + b, k)
                loads[n] = loads.get(n, 0.0) - area * p / 12.0
            for a, b in ((1, 0), (2, 1), (1, 2), (0, 1)):
                n = node_id(2 * i + a, 2 * j + b, k)
                loads[n] = loads.get(n, 0.0) + area * p / 3.0
    return loads


def nearest(nodes, point):
    return min(nodes, key=lambda n: sum((a - b) ** 2 for a, b in zip(nodes[n], point)))


def plate_deck(nmodes):
    nodes, elements = plate_mesh()
    loads = pad_loads()
    tip, mid = nearest(nodes, TIP), nearest(nodes, MID)
    out = ["*HEADING", "f08 proof: clamped plate", "*NODE"]
    out += [f"{n},{x!r},{y!r},{z!r}" for n, (x, y, z) in sorted(nodes.items())]
    out.append("*ELEMENT,TYPE=C3D20R,ELSET=EALL")
    for e, ids in enumerate(elements, 1):
        out.append(f"{e}," + ",".join(map(str, ids[:15])) + ",")
        out.append(",".join(map(str, ids[15:])))
    root = [n for n, (x, _, _) in nodes.items() if abs(x) < 1e-9]
    out += ["*NSET,NSET=ROOT"] + [str(n) for n in sorted(root)]
    obs = sorted(set(loads) | {tip, mid})
    out += ["*NSET,NSET=OBS"] + [str(n) for n in obs]
    out += ["*BOUNDARY", "ROOT,1,3", "*MATERIAL,NAME=AL", "*ELASTIC", f"{E},{NU}",
            "*DENSITY", f"{RHO}", "*SOLID SECTION,ELSET=EALL,MATERIAL=AL"]  # fmt: skip
    load = "".join(f"{n},3,{f!r}\n" for n, f in sorted(loads.items()))
    deck = "\n".join(out) + "\n"
    deck += (
        f"*STEP\n*FREQUENCY,STORAGE=YES\n{nmodes}\n*NODE PRINT,NSET=OBS\nU\n*END STEP\n"
    )
    deck += ssd_steps(nmodes, load, "OBS")
    deck += f"*STEP\n*STATIC\n*CLOAD,OP=NEW\n{load}*NODE PRINT,NSET=OBS\nU\n*END STEP\n"
    mass = RHO * L * W * T
    return (
        deck,
        loads,
        {
            "tip": tip,
            "mid": mid,
            "nodes": len(nodes),
            "elements": len(elements),
            "mass_t": mass,
        },
    )


# ---------------------------------------------------------------- .dat parse

NUM = r"[-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?"


def parse_dat(text):
    steps, step = [], None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r"\s+S T E P\s+\d+", line):
            step = {"eigen": [], "events": []}
            steps.append(step)
        elif "E I G E N V A L U E   O U T P U T" in line:
            i += 1
            while i < len(lines) and not re.match(
                rf"\s+\d+\s+{NUM}\s+{NUM}\s+{NUM}\s+{NUM}\s*$", lines[i]
            ):
                i += 1
            while i < len(lines) and re.match(
                rf"\s+\d+\s+{NUM}\s+{NUM}\s+{NUM}\s+{NUM}\s*$", lines[i]
            ):
                parts = lines[i].split()
                step["eigen"].append({"mode": int(parts[0]), "eigenvalue": float(parts[1]),
                                      "rad": float(parts[2]), "hz": float(parts[3])})  # fmt: skip
                i += 1
            continue
        elif "T O T A L   E F F E C T I V E   M A S S" in line:
            j = i + 1
            while not re.search(NUM, lines[j]) or "COMPONENT" in lines[j]:
                j += 1
            step["total_effective_mass"] = [float(x) for x in lines[j].split()]
        elif "E F F E C T I V E   M O D A L   M A S S" in line:
            j, rows = i + 1, []
            while j < len(lines) and not lines[j].startswith("TOTAL"):
                if re.match(r"\s+\d+\s", lines[j]):
                    rows.append([float(x) for x in lines[j].split()[1:]])
                j += 1
            step["effective_modal_mass"] = rows
        elif "F R E Q U E N C Y" in line and "P A R T I C I P A T I O N" in line:
            hz = float(re.findall(NUM, line.split("F R E Q U E N C Y")[1])[0])
            j, factors = i + 1, []
            while j < len(lines) and "displacements" not in lines[j]:
                parts = lines[j].split()
                if len(parts) == 4 and parts[0].isdigit():
                    factors.append(complex(float(parts[2]), float(parts[3])))
                j += 1
            step["events"].append(("freq", hz, factors))
        elif line.strip().startswith("displacements"):
            j, block = i + 2, {}
            while j < len(lines) and lines[j].strip():
                parts = lines[j].split()
                block[int(parts[0])] = tuple(float(x) for x in parts[1:4])
                j += 1
            step["events"].append(("disp", block))
            i = j
            continue
        i += 1
    return steps


def harmonic(step):
    """[(hz, factors, {node: complex uz})] from a steady-state step."""
    rows, pending = [], None
    disps = []
    for event in step["events"]:
        if event[0] == "freq":
            if pending:
                rows.append((pending[0], pending[1], disps))
            pending, disps = (event[1], event[2]), []
        else:
            disps.append(event[1])
    if pending:
        rows.append((pending[0], pending[1], disps))
    out = []
    for hz, factors, (re_block, im_block) in rows:
        out.append(
            (
                hz,
                factors,
                {n: complex(re_block[n][2], im_block[n][2]) for n in re_block},
            )
        )
    return out


# ---------------------------------------------------------------- run


def run_ccx(image, case, name, deck):
    case.mkdir(parents=True, exist_ok=True)
    (case / f"{name}.inp").write_text(deck)
    start = time.monotonic()
    done = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "--read-only", "--tmpfs", "/tmp", "--cpus", "1",
         "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{case.resolve()}:/case", image,
         "bash", "-c", f"ccx -i {name} > ccx.log 2>&1"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    wall = time.monotonic() - start
    dat = case / f"{name}.dat"
    if done.returncode != 0 or not dat.exists():
        tail = (
            (case / "ccx.log").read_text(errors="replace")[-2000:]
            if (case / "ccx.log").exists()
            else ""
        )
        raise RuntimeError(f"ccx {name} failed ({done.returncode}): {tail}")
    return parse_dat(dat.read_text(errors="replace")), {
        "deck_sha256": hashlib.sha256(deck.encode()).hexdigest(),
        "wall_s": round(wall, 2),
        "processes": 1,
    }


def project(modes, omegas, rhs, probe, w, zeta):
    """u_probe(w) = sum_j phi_j(probe) (phi_j . f)/(w_j^2 - w^2 + 2 i zeta w_j w)."""
    total, factors = 0j, []
    for phi, wj in zip(modes, omegas):
        q = sum(phi[n] * f for n, f in rhs.items()) / (
            wj * wj - w * w + 2j * zeta * wj * w
        )
        factors.append(q)
        total += phi[probe] * q
    return total, factors


def mode_shapes(step):
    return [
        {n: v[2] for n, v in e[1].items()} for e in step["events"] if e[0] == "disp"
    ]


def rel(a, b, floor):
    return abs(a - b) / max(abs(b), floor)


def phase_deg(a, b):
    return abs(math.degrees(cmath.phase(a / b))) if a and b else None


def peak(curve):
    hz, u = max(curve, key=lambda r: abs(r[1]))
    return {"hz": hz, "mm_per_n": abs(u), "phase_deg": math.degrees(cmath.phase(u))}


def oscillators(image, out):
    deck, _ = oscillator_deck()
    steps, run = run_ccx(image, out / "oscillators", "osc", deck)
    params = osc_params()
    eig = steps[0]["eigen"]
    shapes = mode_shapes(steps[0])
    norm = []
    for mode, shape in zip(eig, shapes):
        node = max(shape, key=lambda n: abs(shape[n]))
        i = node - 201
        norm.append({
            "mode": mode["mode"], "oscillator": i,
            "hz_rel_err": abs(mode["hz"] - params[i]["f"]) / params[i]["f"],
            "phi_sqrt_m_minus_1": abs(abs(shape[node]) * math.sqrt(params[i]["m"]) - 1.0),
            "off_node_max": max(abs(v) for n, v in shape.items() if n != node),
        })  # fmt: skip
    damping = {}
    for zeta, step in zip(ZETAS, steps[1:]):
        worst, worst_phase, retained, zero = (
            0.0,
            0.0,
            {r["oscillator"] for r in norm},
            0.0,
        )
        for hz, _, uz in harmonic(step):
            w = 2 * math.pi * hz
            for i, p in enumerate(params):
                got = uz[201 + i]
                if i not in retained:
                    zero = max(zero, abs(got))
                    continue
                wi = 2 * math.pi * p["f"]
                exact = 1.0 / (p["m"] * (wi * wi - w * w + 2j * zeta * wi * w))
                worst = max(worst, rel(got, exact, 1e-12))
                worst_phase = max(worst_phase, phase_deg(got, exact) or 0.0)
        damping[f"zeta_{zeta}"] = {"frequencies": len(harmonic(step)), "max_rel_err_vs_analytic": worst,
                                   "max_phase_err_deg": worst_phase, "unretained_max_abs": zero}  # fmt: skip
    return {"run": run, "modes": norm, "damping": damping}


def plate(image, out):
    rungs, results = {}, {}
    for nmodes in LADDER:
        deck, loads, meta = plate_deck(nmodes)
        steps, run = run_ccx(image, out / f"plate-m{nmodes}", f"plate{nmodes}", deck)
        eig, shapes = steps[0]["eigen"], mode_shapes(steps[0])
        omegas = [m["rad"] for m in eig]
        tip, mid = meta["tip"], meta["mid"]
        static = steps[4]["events"][0][1]
        rung = {"run": run, "mesh": {k: meta[k] for k in ("nodes", "elements")},
                "hz": [m["hz"] for m in eig],
                "total_effective_mass_z": steps[0].get("total_effective_mass", [None] * 3)[2],
                "static_tip_mm_per_n": static[tip][2], "static_mid_mm_per_n": static[mid][2]}  # fmt: skip
        modal_static = sum(
            phi[tip] * sum(phi[n] * f for n, f in loads.items()) / wj**2
            for phi, wj in zip(shapes, omegas)
        )
        rung["modal_static_tip_over_static"] = modal_static / static[tip][2]
        per_zeta = {}
        for zeta, step in zip(ZETAS, steps[1:4]):
            rows = harmonic(step)
            err_u, err_q, err_ph, curve_tip, curve_mid = 0.0, 0.0, 0.0, [], []
            scale = max(abs(r[2][tip]) for r in rows)
            for hz, factors, uz in rows:
                w = 2 * math.pi * hz
                mine, q = project(shapes, omegas, loads, tip, w, zeta)
                err_u = max(err_u, abs(uz[tip] - mine) / scale)
                err_q = max(
                    err_q,
                    max(
                        rel(a, b, 1e-6 * max(abs(x) for x in q))
                        for a, b in zip(factors, q)
                    ),
                )
                if abs(uz[tip]) > 1e-2 * scale:
                    err_ph = max(err_ph, phase_deg(uz[tip], mine) or 0.0)
                curve_tip.append((hz, uz[tip]))
                curve_mid.append((hz, uz[mid]))
            per_zeta[f"zeta_{zeta}"] = {
                "frequencies": len(rows),
                "ccx_vs_projection_max_err_over_peak": err_u,
                "modal_factor_max_rel_err": err_q,
                "phase_max_err_deg_above_1pct_of_peak": err_ph,
                "tip_peak": peak(curve_tip), "mid_peak": peak(curve_mid),
            }  # fmt: skip
            results[(nmodes, zeta)] = (shapes, omegas, loads, tip, rows)
        rung["damping"] = per_zeta
        rungs[f"modes_{nmodes}"] = rung
    # basis reuse: the 48-mode basis truncated to 12/24 reproduces ccx's own 12/24-mode runs
    reuse = {}
    for nmodes in LADDER[:-1]:
        worst = 0.0
        for zeta in ZETAS:
            shapes, omegas, loads, tip, _ = results[(LADDER[-1], zeta)]
            rows = results[(nmodes, zeta)][4]
            scale = max(abs(r[2][tip]) for r in rows)
            for hz, _, uz in rows:
                mine, _ = project(
                    shapes[:nmodes], omegas[:nmodes], loads, tip, 2 * math.pi * hz, zeta
                )
                worst = max(worst, abs(uz[tip] - mine) / scale)
        reuse[f"truncate_48_to_{nmodes}_vs_ccx_{nmodes}_max_err_over_peak"] = worst
    return {
        "rungs": rungs,
        "basis_reuse": reuse,
        "mass_t_analytic": plate_deck(LADDER[0])[2]["mass_t"],
    }


CHECKS = {
    "oscillator_analytic_rel": 1e-5,
    "mass_normalisation_rel": 1e-6,
    "projection_over_peak": 1e-4,
    "modal_factor_rel": 1e-4,
    "phase_deg": 0.01,
}


def summarize(document):
    """Package checks (print-precision bounds, not f08 acceptance tolerances)."""
    osc, plate_doc = document["oscillators"], document["plate"]
    rungs = plate_doc["rungs"]
    zs = [z for r in rungs.values() for z in r["damping"].values()]
    ladder = [rungs[f"modes_{n}"]["modal_static_tip_over_static"] for n in LADDER]
    peaks = [z["tip_peak"]["phase_deg"] for z in zs]
    return {
        "tolerances": CHECKS,
        "exact_modal_damping": all(
            v["max_rel_err_vs_analytic"] <= CHECKS["oscillator_analytic_rel"]
            for v in osc["damping"].values()
        )
        and all(
            z["modal_factor_max_rel_err"] <= CHECKS["modal_factor_rel"] for z in zs
        ),
        "mass_normalised_projection": all(
            m["phi_sqrt_m_minus_1"] <= CHECKS["mass_normalisation_rel"]
            for m in osc["modes"]
        )
        and all(
            z["ccx_vs_projection_max_err_over_peak"] <= CHECKS["projection_over_peak"]
            for z in zs
        ),
        "mode_ladder": len(rungs) == len(LADDER)
        and all(abs(1 - b) < abs(1 - a) for a, b in itertools.pairwise(ladder))
        and all(
            v <= CHECKS["projection_over_peak"]
            for v in plate_doc["basis_reuse"].values()
        ),
        "complex_phase": all(
            v["max_phase_err_deg"] <= CHECKS["phase_deg"]
            for v in osc["damping"].values()
        )
        and all(
            z["phase_max_err_deg_above_1pct_of_peak"] <= CHECKS["phase_deg"] for z in zs
        )
        and all(abs(ph + 90.0) <= 0.5 for ph in peaks),
        "batched_damping_frequency_outputs": all(
            r["run"]["processes"] == 1 for r in rungs.values()
        )
        and all(len(r["damping"]) == len(ZETAS) for r in rungs.values()),
        "notes": "one ccx process per rung: eigen step, three constant-zeta steady-state steps over the eigenfrequency-bracketed 80-600 Hz grid, and the static step; peak samples sit on eigenfrequencies with phase -90 deg (exp(+i omega t) lag)",
    }


def main(image, out, evidence):
    out = Path(out)
    image_id = subprocess.run(["docker", "image", "inspect", image, "--format", "{{.Id}}"],
                              capture_output=True, text=True, check=True).stdout.strip()  # fmt: skip
    document = {
        "schema": "carbon.reference-package.feature-proof.v1",
        "ticket": "REFERENCE-PACKAGES-01",
        "family": "f08-ccx-modal-support",
        "image_id": image_id,
        "script": "scripts/dev/reference_packages/calculix/f08_proof.py",
        "convention": "harmonic exp(+i omega t): u(t) = Re[U exp(i omega t)]; ccx prints Re U then Im U",
        "zetas": list(ZETAS), "band_hz": list(BAND_HZ), "points_between_eigenfrequencies": POINTS, "bias": BIAS,
        "oscillators": oscillators(image, out),
        "plate": plate(image, out),
        "scope": "package convention proof only: not the ribbed f08 geometry, not reference adequacy; f08 acceptance tolerances remain HUMAN_INPUT",
    }  # fmt: skip
    document["proofs"] = summarize(document)
    Path(evidence).write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
    return document


if __name__ == "__main__":
    doc = main(*sys.argv[1:4])
    print(json.dumps({k: doc[k] for k in ("oscillators",)}, indent=1)[:3000])
