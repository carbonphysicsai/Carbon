"""Cross-check the lid pre-solve against the pinned Elmer image (registry
cooling-feasibility-02/lid-spreading-registry.json): the nominal 1.5 mm
copper lid, central ratio-3 band, the same Robin law, on a structured 2D
quad mesh written directly.

    python -m scripts.dev.cold_plate.lid_spreading_elmer --out DIR --image ID
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.cold_plate import lid_spreading as ls

NXE, NZE = 600, 30


def write(out, t_mm, k, r2, h):
    out = Path(out)
    (out / "mesh").mkdir(parents=True, exist_ok=True)
    t = t_mm * 1e-3
    xs = np.linspace(0, ls.L, NXE + 1)
    zs = np.linspace(0, t, NZE + 1)
    nid = lambda i, j: 1 + i + (NXE + 1) * j
    with (out / "mesh" / "mesh.nodes").open("w") as f:
        for j, z in enumerate(zs):
            for i, x in enumerate(xs):
                f.write(f"{nid(i, j)} -1 {float(x)!r} {float(z)!r} 0.0\n")
    elems, bnd = [], []
    for j in range(NZE):
        for i in range(NXE):
            elems.append([nid(i, j), nid(i + 1, j), nid(i + 1, j + 1), nid(i, j + 1)])
    for i in range(NXE):
        bnd.append((1, 1 + i, nid(i, 0), nid(i + 1, 0)))  # bottom
        bnd.append((2, 1 + i + NXE * (NZE - 1), nid(i + 1, NZE), nid(i, NZE)))  # top
    with (out / "mesh" / "mesh.elements").open("w") as f:
        for e, ids in enumerate(elems, start=1):
            f.write(f"{e} 1 404 " + " ".join(map(str, ids)) + "\n")
    with (out / "mesh" / "mesh.boundary").open("w") as f:
        for b, (bc, parent, a, c) in enumerate(bnd, start=1):
            f.write(f"{b} {bc} {parent} 0 202 {a} {c}\n")
    n_nodes = (NXE + 1) * (NZE + 1)
    (out / "mesh" / "mesh.header").write_text(
        f"{n_nodes} {len(elems)} {len(bnd)}\n2\n404 {len(elems)}\n202 {len(bnd)}\n"
    )
    x, q = ls.raw_flux(ls.P_W, 3.0, 15.0)
    sample = np.linspace(0, ls.L, 301)
    qtab = "\n".join(
        f"      {float(xx)!r} {float(qq)!r}"
        for xx, qq in zip(sample, np.interp(sample, x, q))
    )
    rise = ls.coolant_rise(ls.P_W)
    u = 1.0 / (r2 + 1.0 / h)
    t_in = 273.15 + ls.INLET_C
    (out / "case.sif").write_text(f"""Header
  Mesh DB "." "mesh"
End
Simulation
  Coordinate System = Cartesian 2D
  Simulation Type = Steady State
  Steady State Max Iterations = 1
End
Body 1
  Equation = 1
  Material = 1
End
Material 1
  Heat Conductivity = {k!r}
  Density = 8960.0
  Heat Capacity = 385.0
End
Equation 1
  Active Solvers(1) = 1
End
Solver 1
  Equation = Heat Equation
  Variable = Temperature
  Procedure = "HeatSolve" "HeatSolver"
  Linear System Solver = Direct
  Linear System Direct Method = Umfpack
  Nonlinear System Max Iterations = 1
End
Solver 2
  Exec Solver = After Simulation
  Equation = ResultOutput
  Procedure = "ResultOutputSolve" "ResultOutputSolver"
  Output File Name = lid
  Vtu Format = Logical True
  Ascii Output = Logical True
  Single Precision = Logical False
End
Boundary Condition 1
  Target Boundaries(1) = 1
  Heat Transfer Coefficient = {u!r}
  External Temperature = Variable Coordinate 1
    Real MATC "{t_in!r} + {rise!r} * tx / {ls.L!r}"
End
Boundary Condition 2
  Target Boundaries(1) = 2
  Heat Flux = Variable Coordinate 1
    Real
{qtab}
    End
End
""")
    (out / "ELMERSOLVER_STARTINFO").write_text("case.sif\n1\n")
    return u, t_in, rise


def run(out, image, t_mm=1.5, k=391.0, r2=6e-6, h=None):
    u, t_in, rise = write(out, t_mm, k, r2, h)
    cmd = ["docker", "run", "--rm", "--network", "none", "--read-only", "--tmpfs", "/tmp", "--cpus", "1",
           "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{Path(out).resolve()}:/case", image,
           "bash", "-c", "ElmerSolver case.sif > solver.log 2>&1"]  # fmt: skip
    subprocess.run(cmd, check=True)
    vtu = next(Path(out).rglob("lid*.vtu")).read_text()
    pts = (
        re.search(r"<Points>\s*<DataArray[^>]*>(.*?)</DataArray>", vtu, re.DOTALL)
        .group(1)
        .split()
    )
    temp = [
        float(v)
        for v in re.search(r'Name="temperature"[^>]*>(.*?)</DataArray>', vtu, re.DOTALL)
        .group(1)
        .split()
    ]
    xyz = [tuple(map(float, pts[i : i + 3])) for i in range(0, len(pts), 3)]
    bottom = sorted((p[0], tt) for p, tt in zip(xyz, temp) if abs(p[1]) < 1e-12)
    xb = np.array([b[0] for b in bottom])
    qb = u * (np.array([b[1] for b in bottom]) - (t_in + rise * xb / ls.L))
    # trapezoid mean over x
    mean = float(np.sum((qb[1:] + qb[:-1]) / 2 * np.diff(xb)) / ls.L)
    return {"peak_over_mean": float(qb.max() / mean), "peak_x_mm": float(xb[int(np.argmax(qb))] * 1e3),
            "mean_flux_w_m2": mean}  # fmt: skip


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="lid_spreading_elmer")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--h", type=float, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.out, args.image, h=args.h)))
