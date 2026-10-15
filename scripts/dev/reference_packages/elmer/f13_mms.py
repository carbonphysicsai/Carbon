"""Helmholtz MMS on f13's own element route (F13-SCIENCE-VALUES-01 B1).

    python -m scripts.dev.reference_packages.elmer.f13_mms --work DIR --out EVIDENCE.json

Unit cube, Gmsh second-order tetrahedra (the f13 mesher image), Elmer
HelmholtzSolve with the 2-dof complex pressure (the f13 image),
p = (1 + 0.5i) sin(pi x) sin(pi y) sin(pi z), exact Dirichlet data p = 0 on
every face, k = 10 (c = 1, between the Dirichlet eigenvalues 9 pi^2 and
11 pi^2). Elmer's operator is -lap(p) - k^2 p = f, so the source is
(3 pi^2 - k^2) p. h = 0.2, 0.1, 0.05, 0.025.

The L2 and H1-seminorm errors are integrated here, independently of Elmer,
from the native VTU P2 field: each tetrahedron's ten nodal values are
matched to its vertices and edge midpoints by coordinates (no assumed node
order) and integrated with a collapsed 5x5x5 Gauss rule. The observed order
uses h_eff = nodes^(-1/3); the nominal Gmsh size is recorded too.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.reference_packages.elmer import f13_deck as deck
from scripts.dev.reference_packages.elmer import f13_proof as proof

K = 10.0
LADDER = (0.2, 0.1, 0.05, 0.025)
BANDS = {"l2": (2.5, 3.5), "h1": (1.5, 2.5)}  # B1
IMAG = 0.5

MESH = """
import json, gmsh
gmsh.initialize(["-nt", "1"])
gmsh.option.setNumber("General.Terminal", 0)
gmsh.model.occ.addBox(0, 0, 0, 1, 1, 1)
gmsh.model.occ.synchronize()
gmsh.model.addPhysicalGroup(3, [1], 1)
gmsh.model.addPhysicalGroup(2, [t for d, t in gmsh.model.getEntities(2)], 1)
gmsh.option.setNumber("Mesh.MeshSizeMax", {h})
gmsh.option.setNumber("Mesh.MeshSizeMin", {h} / 2)
gmsh.option.setNumber("Mesh.ElementOrder", 2)
gmsh.option.setNumber("Mesh.Algorithm3D", 1)
gmsh.option.setNumber("Mesh.RandomSeed", 1)
gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
gmsh.model.mesh.generate(3)
gmsh.write("mesh.msh")
json.dump({{"nodes": len(gmsh.model.mesh.getNodes()[0])}}, open("groups.json", "w"))
gmsh.finalize()
"""

SIF = """Header
  Mesh DB "." "mesh"
End
Simulation
  Coordinate System = Cartesian 3D
  Simulation Type = Steady State
  Steady State Max Iterations = 1
End
Body 1
  Equation = 1
  Material = 1
  Body Force = 1
End
Equation 1
  Active Solvers(2) = 1 2
End
Material 1
  Density = 1.0
  Sound Speed = 1.0
End
Body Force 1
  Pressure Source 1 = Variable Coordinate 1, Coordinate 2, Coordinate 3
    Real MATC "({a})*sin(pi*tx(0))*sin(pi*tx(1))*sin(pi*tx(2))"
  Pressure Source 2 = Variable Coordinate 1, Coordinate 2, Coordinate 3
    Real MATC "({b})*sin(pi*tx(0))*sin(pi*tx(1))*sin(pi*tx(2))"
End
Solver 1
  Equation = Helmholtz
  Procedure = "HelmholtzSolve" "HelmholtzSolver"
  Variable = Pressure[Pressure 1:1 Pressure 2:1]
  Variable Dofs = 2
  Frequency = Real {f!r}
{solver}
  Nonlinear System Max Iterations = 1
End
Solver 2
  Exec Solver = After Simulation
  Equation = ResultOutput
  Procedure = "ResultOutputSolve" "ResultOutputSolver"
  Output File Name = final
  Vtu Format = Logical True
  Ascii Output = Logical True
End
Boundary Condition 1
  Target Boundaries(1) = 1
  Pressure 1 = Real 0.0
  Pressure 2 = Real 0.0
End
"""


def exact(x):
    s = (
        np.sin(np.pi * x[..., 0])
        * np.sin(np.pi * x[..., 1])
        * np.sin(np.pi * x[..., 2])
    )
    return s


def exact_grad(x):
    sx, sy, sz = (np.sin(np.pi * x[..., i]) for i in range(3))
    cx, cy, cz = (np.cos(np.pi * x[..., i]) for i in range(3))
    return np.pi * np.stack([cx * sy * sz, sx * cy * sz, sx * sy * cz], axis=-1)


def _rule(n=5):
    g, w = np.polynomial.legendre.leggauss(n)
    g, w = (g + 1) / 2, w / 2
    pts, wts = [], []
    for a, wa in zip(g, w):
        for b, wb in zip(g, w):
            for c, wc in zip(g, w):
                z = c
                y = b * (1 - c)
                x = a * (1 - b) * (1 - c)
                pts.append((x, y, z))
                wts.append(wa * wb * wc * (1 - b) * (1 - c) ** 2)
    return np.array(pts), np.array(wts)


def _p2(xi):
    """P2 shape functions and reference gradients at points xi (q, 3).
    Order: vertices 0-3, edges (01, 12, 02, 03, 13, 23)."""
    x, y, z = xi[:, 0], xi[:, 1], xi[:, 2]
    lam = np.stack([1 - x - y - z, x, y, z], axis=1)
    dlam = np.array([[-1, -1, -1], [1, 0, 0], [0, 1, 0], [0, 0, 1]], float)
    edges = ((0, 1), (1, 2), (0, 2), (0, 3), (1, 3), (2, 3))
    n = [lam[:, i] * (2 * lam[:, i] - 1) for i in range(4)]
    dn = [np.outer(4 * lam[:, i] - 1, dlam[i]) for i in range(4)]
    for i, j in edges:
        n.append(4 * lam[:, i] * lam[:, j])
        dn.append(4 * (np.outer(lam[:, j], dlam[i]) + np.outer(lam[:, i], dlam[j])))
    return np.stack(n, axis=1), np.stack(dn, axis=1)  # (q,10), (q,10,3)


EDGES = ((0, 1), (1, 2), (0, 2), (0, 3), (1, 3), (2, 3))


def read_vtu(path):
    root = ET.parse(path).getroot()

    def arr(node, dtype=float):
        if node.attrib.get("format", "ascii") != "ascii":
            raise ValueError("ASCII VTU required")
        return np.array(node.text.split(), dtype=dtype)

    pts = arr(root.find(".//Points/DataArray")).reshape(-1, 3)
    cells = root.find(".//Cells")
    conn = arr(cells.find("DataArray[@Name='connectivity']"), int)
    offs = arr(cells.find("DataArray[@Name='offsets']"), int)
    types = arr(cells.find("DataArray[@Name='types']"), int)
    fields = {}
    for node in root.findall(".//PointData/DataArray"):
        fields[node.attrib.get("Name", "").lower()] = (
            arr(node),
            int(node.attrib.get("NumberOfComponents", "1")),
        )
    tets = []
    start = 0
    for end, kind in zip(offs, types):
        if kind == 24:
            tets.append(conn[start:end])
        start = end
    if "pressure" in fields and fields["pressure"][1] == 2:
        values = fields["pressure"][0].reshape(-1, 2)
        re_, im_ = values[:, 0], values[:, 1]
    else:
        re_, im_ = fields["pressure 1"][0], fields["pressure 2"][0]
    return pts, np.array(tets), re_, im_


def errors(pts, tets, values, scale):
    """L2 and H1-seminorm errors of a P2 nodal field against scale*exact."""
    xi, w = _rule()
    n_ref, dn_ref = _p2(xi)
    l2 = h1 = 0.0
    # reorder each tet's 10 nodes to [v0..v3, edge midpoints] by coordinates
    order = np.empty_like(tets)
    order[:, :4] = tets[:, :4]
    x = pts[tets]  # (e,10,3)
    for k, (i, j) in enumerate(EDGES):
        mid = (x[:, i] + x[:, j]) / 2
        d = np.linalg.norm(x[:, 4:] - mid[:, None, :], axis=2)
        pick = np.argmin(d, axis=1)
        if np.max(d[np.arange(len(tets)), pick]) > 1e-6:
            raise ValueError("curved or unmatched edge node")
        order[:, 4 + k] = tets[np.arange(len(tets)), 4 + pick]
    for chunk in range(0, len(order), 20000):
        el = order[chunk : chunk + 20000]
        v = pts[el[:, :4]]  # (e,4,3)
        jac = np.stack(
            [v[:, 1] - v[:, 0], v[:, 2] - v[:, 0], v[:, 3] - v[:, 0]], axis=2
        )
        det = np.abs(np.linalg.det(jac))
        inv_t = np.linalg.inv(jac).transpose(0, 2, 1)  # (e,3,3)
        u = values[el]  # (e,10)
        xq = v[:, 0][:, None, :] + np.einsum("eij,qj->eqi", jac, xi)
        uh = u @ n_ref.T  # (e,q)
        grad_ref = np.einsum("en,qnd->eqd", u, dn_ref)
        grad = np.einsum("eij,eqj->eqi", inv_t, grad_ref)
        err = uh - scale * exact(xq)
        gerr = grad - scale * exact_grad(xq)
        l2 += float(np.sum(det[:, None] * w[None, :] * err**2))
        h1 += float(np.sum(det[:, None] * w[None, :] * np.sum(gerr**2, axis=2)))
    return math.sqrt(l2), math.sqrt(h1)


def run(work, out, image=proof.IMAGE):
    work = Path(work)
    rows = []
    src = 3 * math.pi**2 - K**2
    for h in LADDER:
        d = work / f"h{h:g}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "make_mesh.py").write_text(MESH.format(h=h))
        (d / "ELMERSOLVER_STARTINFO").write_text("case.sif\n1\n")
        (d / "deck.json").write_text(
            json.dumps({"frequencies_hz": [K / (2 * math.pi)]})
        )
        attempts = []
        # UMFPACK first (the iterative solvers stagnated on this all-Dirichlet
        # indefinite case at h 0.2); IDR(s) only if the direct solve fails.
        for solver in ("direct", "idrs"):
            (d / "case.sif").write_text(
                SIF.format(a=src, b=IMAG * src, f=K / (2 * math.pi),
                           solver=deck.SOLVERS[solver].replace("1e-10", "1e-12"))
            )  # fmt: skip
            memory = "3g" if h >= 0.05 else "12g"
            cost = proof.run(d, image, cpus=1, memory=memory, timeout=7200,
                             tag=f"mms-{h:g}-{solver}")  # fmt: skip
            attempts.append({"solver": solver, **cost.get("solve", {})})
            if cost.get("solve", {}).get("exit") == 0:
                break
        if cost.get("solve", {}).get("exit") != 0:
            rows.append({"h_nominal": h, "status": "FAILED", "attempts": attempts})
            break
        vtu = sorted(d.glob("mesh/final*.vtu"))
        pts, tets, re_, im_ = read_vtu(vtu[-1])
        l2r, h1r = errors(pts, tets, re_, 1.0)
        l2i, h1i = errors(pts, tets, im_, IMAG)
        rows.append({"h_nominal": h, "nodes": len(pts), "tets": len(tets),
                     "h_eff": len(pts) ** (-1 / 3), "l2_real": l2r, "h1_real": h1r,
                     "l2_imag": l2i, "h1_imag": h1i,
                     "vtu_sha256": hashlib.sha256(vtu[-1].read_bytes()).hexdigest(),
                     "solver": attempts[-1]["solver"], "attempts": attempts,
                     "cost": {k: cost[k] for k in ("solve", "mesh") if k in cost}})  # fmt: skip
    done = [r for r in rows if "h_eff" in r]
    orders = []
    for a, b in itertools.pairwise(done):
        r = math.log(a["h_eff"] / b["h_eff"])
        orders.append({key: math.log(a[key] / b[key]) / r
                       for key in ("l2_real", "h1_real", "l2_imag", "h1_imag")})  # fmt: skip
    monotone = all(
        b[k] < a[k] for a, b in itertools.pairwise(done)
        for k in ("l2_real", "h1_real", "l2_imag", "h1_imag")
    )  # fmt: skip
    fin = orders[-1] if orders else {}
    ok = (
        len(done) == len(LADDER)
        and monotone
        and all(
            BANDS["l2"][0] <= fin[k] <= BANDS["l2"][1] for k in ("l2_real", "l2_imag")
        )
        and all(
            BANDS["h1"][0] <= fin[k] <= BANDS["h1"][1] for k in ("h1_real", "h1_imag")
        )
    )
    doc = {
        "schema": "carbon.f13-helmholtz-mms.v1",
        "decision": "F13-SCIENCE-VALUES-01 B1",
        "scope": "PUBLIC_DEVELOPMENT code verification; not port, lead or Tier 2 evidence",
        "image": image, "mesh_image": deck.MESH_IMAGE, "k": K, "imag_scale": IMAG,
        "element": "Gmsh second-order tetrahedra (Elmer 510)",
        "solver": "UMFPACK per rung, IDR(6)+ILU2 (residual 1e-12) only where the direct solve fails; see rows[].attempts",
        "adapter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "rows": rows, "observed_orders": orders, "finest_pair": fin,
        "bands": BANDS, "monotone": monotone, "pass": ok,
        "host_profile": proof.HOST_PROFILE,
    }  # fmt: skip
    Path(out).write_text(json.dumps(doc, indent=1) + "\n")
    return doc


def main(argv=None):
    parser = argparse.ArgumentParser(prog="f13_mms")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--image", default=proof.IMAGE)
    args = parser.parse_args(argv)
    doc = run(args.work, args.out, args.image)
    print(json.dumps({"finest_pair": doc["finest_pair"], "pass": doc["pass"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
