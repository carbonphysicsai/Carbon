"""f08 code-verification decks for the pinned CalculiX image (F08-SCIENCE-VALUES-01).

    python3 f08_verify.py IMAGE OUTDIR EVIDENCE.json [--only mms|rod]

mms  3D small-strain elasticity, manufactured cubic field u_i = a x_i^3 / L^2
     on the unit cube (structures_readiness.manufactured), C3D10 from the
     pinned Gmsh image at h = 0.25/0.125/0.0625 mm. Exact displacement on every
     boundary node, consistent body-force loads integrated per element (5^3
     collapsed Gauss points, exact for the cubic integrand), independent L2 and
     H1-seminorm error integration, and reaction/body-force balance. Band C3:
     observed order on the last two rungs L2 in [2.5, 3.5], H1 in [1.5, 2.5];
     balance <= 1e-5.
rod  closed-form free and forced vibration (substitute for the NAFEMS P18 /
     R0016 decks, which are not available offline): a 500 x 20 x 20 mm fixed-
     free rod, nu = 0, lateral DOF fixed, so 3D elasticity reduces exactly to
     the 1D wave equation. f_n = (2n-1) c / 4L; tip FRF under a uniform 1 N
     end traction with constant modal damping is the exact series
     sum_n (2/m) / (w_n^2 - w^2 + 2 i zeta w_n w). Band C4: first three axial
     f <= 0.2 %; crest <= 1 %, location <= min(2 Hz, 1 %), phase <= 5 deg at
     each zeta, from ccx's own steady-state output and from the projection.

Engineering verification of the code path, not task adequacy or qualification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f08_deck as deck
import f08_freeze
import f08_proof as proof

E, NU, RHO = proof.E, proof.NU, proof.RHO
MMS_H = (0.25, 0.125, 0.0625)
MMS_A, MMS_L = 1e-4, 1.0
ROD = {"L": 500.0, "A": 20.0, "h": 10.0, "modes": 10, "band": (2000.0, 3200.0)}
BANDS = {
    "mms_l2_order": (2.5, 3.5),
    "mms_h1_order": (1.5, 2.5),
    "mms_balance_rel": 1e-5,
    "rod_freq_rel": 0.002,
    "rod_peak_rel": 0.01,
    "rod_phase_deg": 5.0,
}

BOX_MESH = """
import json, gmsh
LX, LY, LZ, H = {lx}, {ly}, {lz}, {h}
gmsh.initialize(["-nt", "1"])
gmsh.option.setNumber("General.Terminal", 0)
gmsh.model.occ.addBox(0, 0, 0, LX, LY, LZ)
gmsh.model.occ.synchronize()
gmsh.option.setNumber("Mesh.MeshSizeMax", H)
gmsh.option.setNumber("Mesh.MeshSizeMin", H / 2)
gmsh.option.setNumber("Mesh.ElementOrder", 2)
gmsh.option.setNumber("Mesh.SecondOrderLinear", 1)
gmsh.option.setNumber("Mesh.Algorithm3D", 1)
gmsh.option.setNumber("Mesh.RandomSeed", 1)
gmsh.model.mesh.generate(3)
tags, xyz, _ = gmsh.model.mesh.getNodes()
coords = {{int(n): [xyz[3 * i], xyz[3 * i + 1], xyz[3 * i + 2]] for i, n in enumerate(tags)}}
tets = []
for ty, ns in zip(*gmsh.model.mesh.getElements(3)[::2]):
    assert ty == 11, ty
    ns = [int(x) for x in ns]
    for k in range(0, len(ns), 10):
        c = ns[k:k + 10]
        tets.append(c[:8] + [c[9], c[8]])  # gmsh -> ccx C3D10 edge order
e = 1e-4
end = []
for d, f in gmsh.model.getEntitiesInBoundingBox(LX - e, -e, -e, LX + e, LY + e, LZ + e, 2):
    for ty, ns in zip(*gmsh.model.mesh.getElements(2, f)[::2]):
        assert ty == 9, ty
        ns = [int(x) for x in ns]
        end += [ns[k:k + 6] for k in range(0, len(ns), 6)]
json.dump({{"coords": coords, "tets": tets, "end_tri6": end}}, open("mesh.json", "w"))
gmsh.finalize()
"""


def _num(value):
    """At most 20 characters: ccx truncates longer numeric fields."""
    return f"{float(value):.13e}"


def _mesh(out, lx, ly, lz, h):
    out.mkdir(parents=True, exist_ok=True)
    (out / "make_mesh.py").write_text(BOX_MESH.format(lx=lx, ly=ly, lz=lz, h=h))
    subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "--cpus", "1", "--memory", "3g",
         "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{out.resolve()}:/w", "-w", "/w",
         deck.MESH_IMAGE, "python3", "make_mesh.py"],
        check=True, capture_output=True,
    )  # fmt: skip
    meta = json.loads((out / "mesh.json").read_text())
    nodes = sorted(int(n) for n in meta["coords"])
    index = {n: i for i, n in enumerate(nodes)}
    # coordinates exactly as ccx reads them back from the deck
    xyz = np.array([[float(_num(v)) for v in meta["coords"][str(n)]] for n in nodes])
    tets = np.array([[index[n] for n in t] for t in meta["tets"]])
    return nodes, xyz, tets, meta


def _run(image, case, memory="3g"):
    start = time.monotonic()
    done = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "--read-only", "--tmpfs", "/tmp", "--cpus", "1",
         "--memory", memory, "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{case.resolve()}:/case",
         image, "bash", "-c", deck.COMMAND],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    wall = time.monotonic() - start
    if done.returncode != 0 or not (case / "case.dat").exists():
        raise RuntimeError(
            f"ccx failed in {case}: {(case / 'ccx.log').read_text()[-1500:]}"
        )
    cost = f08_freeze.cgroup_counters((case / "cgroup.txt").read_text())
    return {"wall_s": round(wall, 2), **cost}


def _print_block(text, label):
    """{node: tuple} of every *NODE PRINT block whose header contains label."""
    out, lines, i = {}, text.splitlines(), 0
    while i < len(lines):
        if lines[i].strip().startswith(label):
            i += 2
            while i < len(lines) and lines[i].strip():
                parts = lines[i].split()
                out[int(parts[0])] = tuple(float(x) for x in parts[1:4])
                i += 1
        i += 1
    return out


# ------------------------------------------------------------ quadrature


def _tet_rule(n=5):
    """Collapsed Gauss-Legendre rule on the unit tetrahedron (barycentric L2..L4)."""
    g, w = np.polynomial.legendre.leggauss(n)
    g, w = (g + 1) / 2, w / 2
    pts, wts = [], []
    for i in range(n):
        for j in range(n):
            for k in range(n):
                u, v, s = g[i], g[j], g[k]
                pts.append((u, v * (1 - u), s * (1 - u) * (1 - v)))
                wts.append(w[i] * w[j] * w[k] * (1 - u) ** 2 * (1 - v))
    return np.array(pts), np.array(wts)


EDGES = ((0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3))  # ccx C3D10 nodes 5..10


def _shape(bary):
    """C3D10 shape functions at barycentric points: (q, 10)."""
    lam = np.column_stack([1 - bary.sum(1), bary])
    corner = lam * (2 * lam - 1)
    edge = np.column_stack([4 * lam[:, a] * lam[:, b] for a, b in EDGES])
    return np.hstack([corner, edge]), lam


def _shape_grad(lam, dlam):
    """Gradients (e, q, 10, 3) from barycentric lam (q, 4) and dlam (e, 4, 3)."""
    corner = (4 * lam - 1)[None, :, :, None] * dlam[:, None, :, :]
    edge = [
        4
        * (
            lam[None, :, a, None] * dlam[:, None, b, :]
            + lam[None, :, b, None] * dlam[:, None, a, :]
        )
        for a, b in EDGES
    ]
    return np.concatenate([corner, np.stack(edge, axis=2)], axis=2)


def _geometry(xyz, tets):
    x0 = xyz[tets[:, 0]]
    jac = np.stack(
        [xyz[tets[:, k]] - x0 for k in (1, 2, 3)], axis=2
    )  # (e, 3, 3) columns
    det = np.linalg.det(jac)
    inv = np.linalg.inv(jac)  # rows: grad of L2..L4
    dlam = np.concatenate([-inv.sum(1, keepdims=True), inv], axis=1)
    return x0, jac, det, dlam


# ------------------------------------------------------------------- MMS


def _exact(x):
    return MMS_A * x**3 / MMS_L**2


def _exact_grad(x):
    return 3 * MMS_A * x**2 / MMS_L**2  # diagonal displacement gradient


def _body(x):
    lam = E * NU / ((1 + NU) * (1 - 2 * NU))
    mu = E / (2 * (1 + NU))
    return -6 * MMS_A * (lam + 2 * mu) * x / MMS_L**2


def _chunks(n, size=4000):
    return [slice(i, min(i + size, n)) for i in range(0, n, size)]


def mms_rung(image, out, h):
    nodes, xyz, tets, _ = _mesh(out, MMS_L, MMS_L, MMS_L, h)
    bary, wq = _tet_rule()
    shape, lam = _shape(bary)
    x0, jac, det, dlam = _geometry(xyz, tets)
    assert det.min() > 0, "inverted element"
    # consistent body-force loads: F_a = int f N_a dV
    loads = np.zeros_like(xyz)
    for s_ in _chunks(len(tets)):
        xq = x0[s_, None, :] + np.einsum("eij,qj->eqi", jac[s_], bary)
        contrib = np.einsum("eqi,qa,q,e->eai", _body(xq), shape, wq, det[s_])
        np.add.at(loads, tets[s_], contrib)
    on_face = np.any((xyz < 1e-9) | (xyz > MMS_L - 1e-9), axis=1)
    bnd = [nodes[i] for i in np.flatnonzero(on_face)]
    lines = ["*HEADING", f"f08 MMS h={h}", "*NODE"]
    lines += [
        f"{n},{_num(x)},{_num(y)},{_num(z)}"
        for n, (x, y, z) in zip(nodes, xyz.tolist())
    ]
    lines.append("*ELEMENT,TYPE=C3D10,ELSET=EALL")
    lines += [
        f"{e + 1}," + ",".join(str(nodes[i]) for i in t) for e, t in enumerate(tets)
    ]
    lines += ["*NSET,NSET=NBND"] + [str(n) for n in bnd]
    lines += ["*NSET,NSET=ALLN"] + [str(n) for n in nodes]
    lines += ["*MATERIAL,NAME=AL", "*ELASTIC", f"{E},{NU}", "*DENSITY", f"{RHO}",
              "*SOLID SECTION,ELSET=EALL,MATERIAL=AL", "*BOUNDARY"]  # fmt: skip
    for i in np.flatnonzero(on_face):
        for d in range(3):
            lines.append(f"{nodes[i]},{d + 1},{d + 1},{_num(_exact(xyz[i, d]))}")
    lines += ["*STEP", "*STATIC", "*CLOAD"]
    for i in np.flatnonzero(~on_face):
        for d in range(3):
            lines.append(f"{nodes[i]},{d + 1},{_num(loads[i, d])}")
    lines += ["*NODE PRINT,NSET=ALLN", "U", "*NODE PRINT,NSET=NBND", "RF", "*END STEP"]
    (out / "case.inp").write_text("\n".join(lines) + "\n")
    run = _run(image, out)
    text = (out / "case.dat").read_text(errors="replace")
    disp = _print_block(text, "displacements")
    forces = _print_block(text, "forces")
    u = np.array([disp[n] for n in nodes])
    sums = np.zeros(4)  # l2 err, l2 ref, h1 err, h1 ref (squared)
    for s_ in _chunks(len(tets)):
        xq = x0[s_, None, :] + np.einsum("eij,qj->eqi", jac[s_], bary)
        weight = wq[None, :] * det[s_, None]
        uq = np.einsum("qa,eai->eqi", shape, u[tets[s_]])
        guq = np.einsum("eqak,eai->eqik", _shape_grad(lam, dlam[s_]), u[tets[s_]])
        exact_g = np.zeros_like(guq)
        for d in range(3):
            exact_g[..., d, d] = _exact_grad(xq[..., d])
        sums += [
            np.sum(weight[..., None] * (uq - _exact(xq)) ** 2),
            np.sum(weight[..., None] * _exact(xq) ** 2),
            np.sum(weight[..., None, None] * (guq - exact_g) ** 2),
            np.sum(weight[..., None, None] * exact_g**2),
        ]
    l2, l2_ref, h1, h1_ref = (math.sqrt(float(v)) for v in sums)
    reaction = np.array([forces[n] for n in bnd]).sum(0)
    applied = loads[~on_face].sum(0)
    return {
        "h_target_mm": h,
        "h_effective_mm": (MMS_L**3 / len(tets)) ** (1 / 3),
        "nodes": len(nodes),
        "elements": len(tets),
        "l2_rel": l2 / l2_ref,
        "h1_rel": h1 / h1_ref,
        "balance_rel": float(np.abs(reaction + applied).max() / np.abs(applied).max()),
        "deck_sha256": hashlib.sha256((out / "case.inp").read_bytes()).hexdigest(),
        "run": run,
    }


def mms(image, out):
    rungs = [mms_rung(image, out / f"mms-h{h:g}", h) for h in MMS_H]
    orders = {}
    for key in ("l2_rel", "h1_rel"):
        a, b = rungs[-2], rungs[-1]
        orders[key] = math.log(a[key] / b[key]) / math.log(
            a["h_effective_mm"] / b["h_effective_mm"]
        )
    lo2, hi2 = BANDS["mms_l2_order"]
    lo1, hi1 = BANDS["mms_h1_order"]
    ok = (
        lo2 <= orders["l2_rel"] <= hi2
        and lo1 <= orders["h1_rel"] <= hi1
        and all(r["balance_rel"] <= BANDS["mms_balance_rel"] for r in rungs)
    )
    return {
        "rungs": rungs,
        "observed_order": orders,
        "verdict": "PASS" if ok else "FAIL",
    }


# ------------------------------------------------------------------- rod


def rod_exact(f_hz, zeta, terms=20000):
    L, A = ROD["L"], ROD["A"] ** 2
    c, m = math.sqrt(E / RHO), RHO * A * L
    w = 2 * math.pi * f_hz
    total = 0j
    for n in range(1, terms + 1):
        wn = (2 * n - 1) * math.pi * c / (2 * L)
        total += (2 / m) / (wn * wn - w * w + 2j * zeta * wn * w)
    return total


def rod(image, out):
    out = out / "rod"
    L, a = ROD["L"], ROD["A"]
    nodes, xyz, tets, meta = _mesh(out, L, a, a, ROD["h"])
    coords = {str(n): xyz[i].tolist() for i, n in enumerate(nodes)}
    pad = deck.face_weights(meta["end_tri6"], coords)
    total = math.fsum(pad.values())
    loads = {n: w / total for n, w in pad.items()}
    tip = min(
        nodes,
        key=lambda n: sum(
            (p - q) ** 2 for p, q in zip(coords[str(n)], (L, a / 2, a / 2))
        ),
    )
    root = [n for n, x in zip(nodes, xyz) if x[0] < 1e-9]
    load = "".join(f"{n},1,{_num(f)}\n" for n, f in sorted(loads.items()))
    lo, hi = ROD["band"]
    lines = ["*HEADING", "f08 closed-form rod", "*NODE"]
    lines += [
        f"{n},{_num(x)},{_num(y)},{_num(z)}"
        for n, (x, y, z) in zip(nodes, xyz.tolist())
    ]
    lines.append("*ELEMENT,TYPE=C3D10,ELSET=EALL")
    lines += [
        f"{e + 1}," + ",".join(str(nodes[i]) for i in t) for e, t in enumerate(tets)
    ]
    lines += ["*NSET,NSET=ROOT"] + [str(n) for n in root]
    lines += ["*NSET,NSET=ALLN"] + [str(n) for n in nodes]
    lines += ["*NSET,NSET=OBS"] + [str(n) for n in sorted(set(loads) | {tip})]
    lines += ["*BOUNDARY", "ROOT,1,1", "ALLN,2,3", "*MATERIAL,NAME=AL", "*ELASTIC", f"{E},0.0",
              "*DENSITY", f"{RHO}", "*SOLID SECTION,ELSET=EALL,MATERIAL=AL"]  # fmt: skip
    deck_text = "\n".join(lines) + "\n"
    deck_text += f"*STEP\n*FREQUENCY,STORAGE=YES\n{ROD['modes']}\n*NODE PRINT,NSET=OBS\nU\n*END STEP\n"
    for zeta in deck.ZETAS:
        deck_text += (
            f"*STEP\n*STEADY STATE DYNAMICS\n{lo},{hi},40,1.\n*MODAL DAMPING\n1,{ROD['modes']},{zeta}\n"
            f"*CLOAD,OP=NEW\n{load}*NODE PRINT,NSET=OBS\nU\n*END STEP\n"
        )
    deck_text += (
        f"*STEP\n*STATIC\n*CLOAD,OP=NEW\n{load}*NODE PRINT,NSET=OBS\nU\n*END STEP\n"
    )
    (out / "case.inp").write_text(deck_text)
    run = _run(image, out)
    steps = proof.parse_dat((out / "case.dat").read_text(errors="replace"))
    eig = steps[0]["eigen"]
    shapes = [
        {n: v[0] for n, v in e[1].items()} for e in steps[0]["events"] if e[0] == "disp"
    ]
    modal = [{"omega": m["rad"], "hz": m["hz"], "pf": sum(s[n] * f for n, f in loads.items()), "tip": s[tip]}
             for m, s in zip(eig, shapes)]  # fmt: skip
    c = math.sqrt(E / RHO)
    exact_f = [(2 * n - 1) * c / (4 * L) for n in (1, 2, 3)]
    axial = [
        m["hz"]
        for m in modal
        if abs(m["pf"] * m["tip"]) / m["omega"] ** 2 > 1e-6 * L / (E * a * a)
    ]
    freq = [abs(g - x) / x for g, x in zip(axial, exact_f)]
    out_doc = {"exact_hz": exact_f, "ccx_axial_hz": axial[:3], "freq_rel": freq,
               "static_rel": abs(steps[4]["events"][0][1][tip][0] - L / (E * a * a)) / (L / (E * a * a)),
               "mesh": {"nodes": len(nodes), "elements": len(tets)}, "run": run,
               "deck_sha256": hashlib.sha256((out / "case.inp").read_bytes()).hexdigest(), "damping": {}}  # fmt: skip
    ok = len(freq) == 3 and max(freq) <= BANDS["rod_freq_rel"]
    for zeta, step in zip(deck.ZETAS, steps[1:4]):
        rows = []
        for hz, _, disp in _harmonic_x(step):
            rows.append((hz, disp[tip]))
        grid = [lo + k * (hi - lo) / 1200 for k in range(1201)]
        ref = deck.resolved_peak(lambda f, z=zeta: rod_exact(f, z, 4000), grid)
        proj = deck.resolved_peak(lambda f, z=zeta: deck.response(modal, f, z), grid)
        ccx_curve = max(rows, key=lambda r: abs(r[1]))
        r = {
            "exact_peak": ref,
            "projection_peak": proj,
            "ccx_native_max": {"hz": ccx_curve[0], "mm_per_n": abs(ccx_curve[1])},
            "projection_peak_rel": abs(proj["mm_per_n"] - ref["mm_per_n"])
            / ref["mm_per_n"],
            "projection_location_ok": deck.location_ok(proj["hz"], ref["hz"]),
            "projection_phase_deg": deck.wrapped_deg(
                proj["phase_deg"], ref["phase_deg"]
            ),
            # C4 judges ccx's own crest sample against the exact series at that frequency
            "ccx_native_crest_rel": abs(
                ccx_curve[1] - rod_exact(ccx_curve[0], zeta, 4000)
            )
            / abs(rod_exact(ccx_curve[0], zeta, 4000)),
            # diagnostic: every ccx sample >= 10 % of the crest (includes 10-mode truncation)
            "ccx_vs_exact_max_rel_near_crest": max(
                abs(u - rod_exact(f, zeta, 4000)) / abs(rod_exact(f, zeta, 4000))
                for f, u in rows
                if abs(rod_exact(f, zeta, 4000)) >= 0.1 * ref["mm_per_n"]
            ),
        }
        ok &= (
            r["projection_peak_rel"] <= BANDS["rod_peak_rel"]
            and r["projection_location_ok"]
            and r["projection_phase_deg"] <= BANDS["rod_phase_deg"]
            and r["ccx_native_crest_rel"] <= BANDS["rod_peak_rel"]
        )
        out_doc["damping"][f"zeta_{zeta}"] = r
    out_doc["verdict"] = "PASS" if ok else "FAIL"
    return out_doc


def _harmonic_x(step):
    """proof.harmonic for the x component: [(hz, factors, {node: complex ux})]."""
    out, pending, disps = [], None, []
    for event in step["events"] + [("freq", None, None)]:
        if event[0] == "freq":
            if pending and len(disps) == 2:
                re_b, im_b = disps
                out.append(
                    (
                        pending[0],
                        pending[1],
                        {n: complex(re_b[n][0], im_b[n][0]) for n in re_b},
                    )
                )
            pending, disps = (event[1], event[2]), []
        else:
            disps.append(event[1])
    return out


def main(argv=None):
    p = argparse.ArgumentParser(prog="f08_verify")
    p.add_argument("image")
    p.add_argument("out", type=Path)
    p.add_argument("evidence", type=Path)
    p.add_argument("--only", choices=("mms", "rod"))
    args = p.parse_args(argv)
    image_id = subprocess.run(["docker", "image", "inspect", args.image, "--format", "{{.Id}}"],
                              capture_output=True, text=True, check=True).stdout.strip()  # fmt: skip
    doc = json.loads(args.evidence.read_text()) if args.evidence.exists() else {}
    doc.update({
        "schema": "carbon.f08-code-verification.v1", "family": "f08", "image_id": image_id,
        "mesh_image": deck.MESH_IMAGE, "script": "scripts/dev/reference_packages/calculix/f08_verify.py",
        "bands": BANDS, "bands_decision": deck.DECISION, "units": "mm, N, t, s; MPa; Hz",
        "scope": "DEVELOPMENT code verification; not task adequacy, Tier 2 or qualification. NAFEMS P18.FV4/FV73 "
                 "and R0016.5H decks are not available offline; the rod is a closed-form substitute.",
    })  # fmt: skip
    if args.only in (None, "mms"):
        doc["mms"] = mms(args.image, args.out)
    if args.only in (None, "rod"):
        doc["rod"] = rod(args.image, args.out)
    args.evidence.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k]["verdict"] for k in ("mms", "rod") if k in doc}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
