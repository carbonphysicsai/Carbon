"""Code verification by the method of manufactured solutions (MMS) for the
pinned Elmer image's transient heat conduction, as f02 uses it (trilinear
hexahedra, BDF order 2). Owner-approved process step, 2026-10-10.

    python3 mms_heat.py IMAGE OUTDIR EVIDENCE.json

Manufactured solution on the unit cube, k = rho = cp = 1:
    T = 1 + S(x) cos(2 pi t),  S = sin(pi x) sin(pi y) sin(pi z)
so T = 1 on every face, T(t=0) = 1 + S, and the source (per unit mass) is
    f = S (3 pi^2 cos(2 pi t) - 2 pi sin(2 pi t)).
Errors at t = 0.5 against the exact field at the nodes.

- space: N = 8, 16, 32 elements per side, dt = 1/512 (time error far below);
  observed order from max and RMS nodal errors, expected 2.
- time: N = 16, dt = 1/8, 1/16, 1/32 against the same mesh at dt = 1/256
  (removes the spatial error), expected 2.
Package check: observed order within 0.3 of 2 on the finest pair. This
verifies the code's discretisation, not f02's physics or reference adequacy.
"""

from __future__ import annotations

import itertools
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f02_deck as deck

T_END = 0.5
EXPECTED, TOL = 2.0, 0.3


def write_mesh(out, n):
    out = Path(out) / "mesh"
    out.mkdir(parents=True, exist_ok=True)
    nid = lambda i, j, k: 1 + i + (n + 1) * (j + (n + 1) * k)
    with (out / "mesh.nodes").open("w") as f:
        for k in range(n + 1):
            for j in range(n + 1):
                for i in range(n + 1):
                    f.write(f"{nid(i, j, k)} -1 {i / n!r} {j / n!r} {k / n!r}\n")
    hexes = []
    for k in range(n):
        for j in range(n):
            for i in range(n):
                hexes.append([nid(i, j, k), nid(i + 1, j, k), nid(i + 1, j + 1, k), nid(i, j + 1, k),
                              nid(i, j, k + 1), nid(i + 1, j, k + 1), nid(i + 1, j + 1, k + 1), nid(i, j + 1, k + 1)])  # fmt: skip
    with (out / "mesh.elements").open("w") as f:
        for e, ids in enumerate(hexes, start=1):
            f.write(f"{e} 1 808 " + " ".join(map(str, ids)) + "\n")
    quads = []
    e_of = lambda i, j, k: 1 + i + n * (j + n * k)
    for a in range(n):
        for b in range(n):
            quads.append(
                (
                    e_of(a, b, 0),
                    [
                        nid(a, b, 0),
                        nid(a + 1, b, 0),
                        nid(a + 1, b + 1, 0),
                        nid(a, b + 1, 0),
                    ],
                )
            )
            quads.append(
                (
                    e_of(a, b, n - 1),
                    [
                        nid(a, b, n),
                        nid(a + 1, b, n),
                        nid(a + 1, b + 1, n),
                        nid(a, b + 1, n),
                    ],
                )
            )
            quads.append(
                (
                    e_of(a, 0, b),
                    [
                        nid(a, 0, b),
                        nid(a + 1, 0, b),
                        nid(a + 1, 0, b + 1),
                        nid(a, 0, b + 1),
                    ],
                )
            )
            quads.append(
                (
                    e_of(a, n - 1, b),
                    [
                        nid(a, n, b),
                        nid(a + 1, n, b),
                        nid(a + 1, n, b + 1),
                        nid(a, n, b + 1),
                    ],
                )
            )
            quads.append(
                (
                    e_of(0, a, b),
                    [
                        nid(0, a, b),
                        nid(0, a + 1, b),
                        nid(0, a + 1, b + 1),
                        nid(0, a, b + 1),
                    ],
                )
            )
            quads.append(
                (
                    e_of(n - 1, a, b),
                    [
                        nid(n, a, b),
                        nid(n, a + 1, b),
                        nid(n, a + 1, b + 1),
                        nid(n, a, b + 1),
                    ],
                )
            )
    with (out / "mesh.boundary").open("w") as f:
        for q, (parent, ids) in enumerate(quads, start=1):
            f.write(f"{q} 1 {parent} 0 404 " + " ".join(map(str, ids)) + "\n")
    (out / "mesh.header").write_text(
        f"{(n + 1) ** 3} {len(hexes)} {len(quads)}\n2\n808 {len(hexes)}\n404 {len(quads)}\n"
    )


SIF = """Header
  Mesh DB "." "mesh"
End
Simulation
  Max Output Level = 3
  Coordinate System = Cartesian 3D
  Simulation Type = Transient
  Timestepping Method = BDF
  BDF Order = 2
  Timestep Sizes(1) = {dt!r}
  Timestep Intervals(1) = {steps}
  Steady State Max Iterations = 1
End
Body 1
  Equation = 1
  Material = 1
  Body Force = 1
  Initial Condition = 1
End
Material 1
  Heat Conductivity = 1.0
  Heat Capacity = 1.0
  Density = 1.0
End
Body Force 1
  Heat Source = Variable Coordinate 1, Coordinate 2, Coordinate 3, Time
    Real MATC "sin(pi*tx(0))*sin(pi*tx(1))*sin(pi*tx(2))*(3*pi^2*cos(2*pi*tx(3))-2*pi*sin(2*pi*tx(3)))"
End
Initial Condition 1
  Temperature = Variable Coordinate 1, Coordinate 2, Coordinate 3
    Real MATC "1+sin(pi*tx(0))*sin(pi*tx(1))*sin(pi*tx(2))"
End
Equation 1
  Active Solvers(2) = 1 2
End
Solver 1
  Equation = Heat Equation
  Procedure = "HeatSolve" "HeatSolver"
  Variable = Temperature
  Linear System Solver = Iterative
  Linear System Iterative Method = CG
  Linear System Preconditioning = ILU0
  Linear System Convergence Tolerance = 1e-12
  Linear System Max Iterations = 5000
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
  Temperature = 1.0
End
"""


def run(image, out, n, dt):
    d = Path(out) / f"n{n}-dt{1 / dt:g}"
    write_mesh(d, n)
    (d / "case.sif").write_text(SIF.format(dt=dt, steps=round(T_END / dt)))
    (d / "ELMERSOLVER_STARTINFO").write_text("case.sif\n1\n")
    t0 = time.monotonic()
    rc = subprocess.run(["docker", "run", "--rm", "--network", "none", "--read-only", "--tmpfs", "/tmp", "--cpus", "1",
                         "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{d.resolve()}:/case", "-w", "/case", image,
                         "bash", "-c", "ElmerSolver case.sif > solver.log 2>&1"], check=False).returncode  # fmt: skip
    wall = time.monotonic() - t0
    if rc != 0:
        raise RuntimeError(f"{d.name}: ElmerSolver exit {rc}")
    xyz, temp, _, _ = deck._vtu_arrays(d)
    return {
        (round(x, 9), round(y, 9), round(z, 9)): t for (x, y, z), t in zip(xyz, temp)
    }, wall


def exact(p):
    x, y, z = p
    return 1 + math.sin(math.pi * x) * math.sin(math.pi * y) * math.sin(
        math.pi * z
    ) * math.cos(2 * math.pi * T_END)


def norms(errors):
    return max(abs(e) for e in errors), math.sqrt(
        sum(e * e for e in errors) / len(errors)
    )


def order(a, b, ratio=2.0):
    return math.log(a / b) / math.log(ratio)


def main(image, out, evidence):
    space, walls = [], {}
    for n in (8, 16, 32):
        field, walls[f"space n{n}"] = run(image, out, n, 1 / 512)
        space.append((n, *norms([t - exact(p) for p, t in field.items()])))
    ref, walls["time ref"] = run(image, out, 16, 1 / 256)
    time_rows = []
    for inv in (8, 16, 32):
        field, walls[f"time dt1/{inv}"] = run(image, out, 16, 1 / inv)
        time_rows.append((inv, *norms([t - ref[p] for p, t in field.items()])))
    space_orders = [
        {"pair": f"{a[0]}->{b[0]}", "max": order(a[1], b[1]), "rms": order(a[2], b[2])}
        for a, b in itertools.pairwise(space)
    ]
    time_orders = [
        {
            "pair": f"1/{a[0]}->1/{b[0]}",
            "max": order(a[1], b[1]),
            "rms": order(a[2], b[2]),
        }
        for a, b in itertools.pairwise(time_rows)
    ]
    passed = all(
        abs(o[k] - EXPECTED) <= TOL
        for o in (space_orders[-1], time_orders[-1])
        for k in ("max", "rms")
    )
    doc = {"schema": "carbon.reference-package.mms.v1", "image": image, "solver": "Elmer HeatSolver, hex808, BDF2",
           "solution": "T = 1 + sin(pi x) sin(pi y) sin(pi z) cos(2 pi t), unit cube, k = rho cp = 1, t_end 0.5",
           "space_errors": [{"n": n, "max": m, "rms": r} for n, m, r in space], "space_orders": space_orders,
           "time_errors_vs_dt1_256": [{"dt": f"1/{i}", "max": m, "rms": r} for i, m, r in time_rows],
           "time_orders": time_orders, "expected_order": EXPECTED, "tolerance": TOL, "pass": passed,
           "wall_s": {k: round(v, 1) for k, v in walls.items()},
           "scope": "code verification only (discretisation order); not f02 physics, not reference adequacy"}  # fmt: skip
    Path(evidence).write_text(json.dumps(doc, indent=1) + "\n")
    print(
        json.dumps(
            {"space_orders": space_orders, "time_orders": time_orders, "pass": passed},
            indent=1,
        )
    )
    return doc


if __name__ == "__main__":
    main(*sys.argv[1:4])
