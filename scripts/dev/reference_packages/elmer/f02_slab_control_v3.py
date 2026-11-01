"""The Kirchhoff slab control of the nonlinear solve of deck v3 (Burst Thermal 3.0, T3).

    python3 f02_slab_control_v3.py IMAGE OUTDIR EVIDENCE.json

A steady 1D slab (the deck's copper slab mesh, laterally insulated): the underside held at a fixed temperature T_a, a
uniform flux q entering on the top, with k(T) = k0 (1 + beta (T - T0)). The exact solution is the Kirchhoff transform:

    phi(T) = int_{T0}^{T} k(s)/k0 ds = (T - T0) + beta/2 (T - T0)^2,  and  k0 phi(T(z)) is LINEAR in z:
    k0 phi(T(z)) = k0 phi(T_a) + q z   =>   T(z) = T0 + (-1 + sqrt(1 + 2 beta phi(z))) / beta  (beta -> 0: linear).

Elmer vs the analytic top and mid-depth temperatures at 2 meshes x 2 load levels, within the registered slab band
(<= max(0.25 C, 1 % of the rise), as `f02_controls`). Two property paths, both exact:

- ``matc``: the smooth k(T) above, given to Elmer as a MATC function;
- ``table``: a piecewise-linear TEST k(T) table, given as the Elmer `Variable Temperature` real table the production decks
  use (the TABLE PATH test of OWNER-F02-V3-PICKS-01: an Elmer table lookup against direct evaluation). Its exact solution is
  the same transform with the table's integral: int_{T_a}^{T} k(s) ds = q z, inverted by bisection.
 BETA is a TEST value, labelled (k varies about 30 % over the ~100 K
rise); it is not a material value. This verifies the solver's nonlinear conduction, not f02's property tables.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f02_deck_v3 as deck

K0, T0_K, BETA = (
    390.0,
    354.0,
    0.0025,
)  # TEST values: k varies ~30 % over the slab's ~100 K rise
TA_K = 303.15  # the held underside
LENGTH = deck.LAYERS["copper"][1] * deck.MM  # 2 mm
LOADS_W_M2 = (
    8.0e6,
    2.0e7,
)  # two load levels: rises of about 40 K and 100 K across the 2 mm slab
LEVELS = (1, 2)  # two meshes
BAND_ABS_C, BAND_REL = 0.25, 0.01
TEST_ONLY = "TEST_ONLY"
PATHS = ("matc", "table")
#: A TEST table of k(T), W/mK, with bends (not a material): linear between the knots, clamped outside 280-420 K.
K_TABLE = [
    (280.0, 440.0),
    (300.0, 415.0),
    (330.0, 380.0),
    (360.0, 350.0),
    (400.0, 320.0),
    (420.0, 310.0),
]


def phi(t_k, beta=BETA, t0=T0_K):
    """The Kirchhoff transform of k(T) = k0 (1 + beta (T - T0)), normalised by k0."""
    u = t_k - t0
    return u + beta * u * u / 2


def temperature(z, q, *, ta=TA_K, k0=K0, beta=BETA, t0=T0_K):
    """The exact steady temperature at height ``z`` above the held face for flux ``q`` into the top."""
    value = phi(ta, beta, t0) + q * z / k0
    if beta == 0:
        return t0 + value
    inside = 1 + 2 * beta * value
    if inside <= 0:
        raise ValueError("the manufactured k(T) is not positive on this range")
    return t0 + (-1 + math.sqrt(inside)) / beta


def temperature_table(z, q, *, table=None, ta=TA_K):
    """The exact steady temperature for a piecewise-linear k table: the T with int_{ta}^{T} k(s) ds = q z (bisection on the
    exact table integral; k > 0 makes it increasing)."""
    table = K_TABLE if table is None else table
    target = q * z
    low, high = ta, ta + 1.0
    while deck.integral(table, ta, high) < target:
        high = ta + 2 * (high - ta)
        if high - ta > 1e5:
            raise ValueError("no temperature carries this flux")
    for _ in range(200):
        mid = (low + high) / 2
        if deck.integral(table, ta, mid) < target:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def exact_temperature(path, z, q):
    if path not in PATHS:
        raise ValueError("unknown property path")
    return temperature(z, q) if path == "matc" else temperature_table(z, q)


def band(rise):
    return max(BAND_ABS_C, BAND_REL * abs(rise))


def _conductivity(path):
    if path == "table":
        return deck._property_lines("Heat Conductivity", K_TABLE)
    return f"""  Heat Conductivity = Variable Temperature
    Real MATC "{K0}*(1+{BETA}*(tx-{T0_K}))"
"""


def sif_text(q, path="matc"):
    return f"""! f02 Kirchhoff slab control, {path} path (test-only properties, tables {TEST_ONLY}); nonlinear max iterations {deck.NONLINEAR_MAX_ITERATIONS}, tolerance {deck.NONLINEAR_TOLERANCE!r}
Header
  Mesh DB "." "mesh"
End
Simulation
  Max Output Level = 3
  Coordinate System = Cartesian 3D
  Simulation Type = Steady State
  Steady State Max Iterations = 1
End
Body 1
  Equation = 1
  Material = 1
  Initial Condition = 1
End
Material 1
{_conductivity(path)}  Heat Capacity = 385.0
  Density = 8960.0
End
Initial Condition 1
  Temperature = {TA_K!r}
End
Equation 1
  Active Solvers(2) = 1 2
End
Solver 1
  Equation = Heat Equation
  Variable = Temperature
  Procedure = "HeatSolve" "HeatSolver"
  Linear System Solver = Direct
  Linear System Direct Method = Umfpack
  Steady State Convergence Tolerance = 1e-9
  Nonlinear System Max Iterations = {deck.NONLINEAR_MAX_ITERATIONS}
  Nonlinear System Convergence Tolerance = {deck.NONLINEAR_TOLERANCE!r}
End
Solver 2
  Exec Solver = After Simulation
  Equation = SaveScalars
  Procedure = "SaveData" "SaveScalars"
  Filename = scalars.dat
  Variable 1 = Temperature
  Operator 1 = boundary max
  Save Coordinates(2,3) = 0.0 0.0 {LENGTH!r} 0.0 0.0 {LENGTH / 2!r}
End
Boundary Condition 1
  Target Boundaries(1) = 1
  Temperature = {TA_K!r}
End
Boundary Condition 2
  Target Boundaries(1) = 2
  Heat Flux = {q!r}
End
"""


def write_control(out, level, q, path="matc"):
    """The slab mesh (the deck's own, copper only: bc 1 the underside, bc 2 the top) and this control's solver input."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    deck.write_mesh(out, level, slab=True)
    (out / "case.sif").write_text(sif_text(q, path))
    (out / "ELMERSOLVER_STARTINFO").write_text("case.sif\n1\n")


def read_result(case_dir):
    """``(top, mid)`` temperatures in K from the solver's scalars file (the top-centre and mid-depth centre points)."""
    cols, rows = deck.read_scalars(case_dir)
    points = [
        i for i, c in enumerate(cols) if c.startswith("value: temperature at node")
    ]
    if len(points) != 2 or len(rows) != 1:
        raise ValueError("the scalars file is not this control's")
    return rows[0][points[0]], rows[0][points[1]]


def compare(q, top, mid, path="matc"):
    """The control's verdict for one (level, load): errors at the top and mid-depth against the exact solution."""
    exact_top, exact_mid = exact_temperature(path, LENGTH, q), exact_temperature(
        path, LENGTH / 2, q
    )
    rise = exact_top - TA_K
    limit = band(rise)
    errors = (abs(top - exact_top), abs(mid - exact_mid))
    return {
        "q_w_m2": q,
        "rise_c": rise,
        "top_error_c": errors[0],
        "mid_error_c": errors[1],
        "band_c": limit,
        "pass": max(errors) <= limit,
    }


def run_elmer(image, case_dir, timeout_s=3600):
    cmd = [
        "docker", "run", "--rm", "--network", "none", "--read-only", "--tmpfs", "/tmp",
        "--cpus", "1", "--user", f"{os.getuid()}:{os.getgid()}",
        "-v", f"{Path(case_dir).resolve()}:/case", "-w", "/case", image,
        "bash", "-c", "ElmerSolver case.sif > solver.log 2>&1",
    ]  # fmt: skip
    start = time.monotonic()
    done = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout_s, check=False
    )
    return done.returncode, time.monotonic() - start


def main(image, out, evidence):
    results = []
    for path in PATHS:
        for level in LEVELS:
            for q in LOADS_W_M2:
                case_dir = Path(out) / f"{path}-level{level}-q{q:g}"
                write_control(case_dir, level, q, path)
                code, wall = run_elmer(image, case_dir)
                row = {
                    "path": path,
                    "level": level,
                    "exit": code,
                    "wall_s": round(wall, 1),
                }
                if code == 0:
                    row.update(compare(q, *read_result(case_dir), path))
                else:
                    row["pass"] = False
                results.append(row)
                print(json.dumps(row), flush=True)
    document = {
        "schema": "carbon.reference-package.kirchhoff-slab.v2",
        "image": image,
        "properties": {
            "matc": {"k": f"{K0}(1+{BETA}(T-{T0_K}))", "label": TEST_ONLY},
            "table": {"k": K_TABLE, "label": TEST_ONLY},
        },
        "band": f"max({BAND_ABS_C} C, {BAND_REL} of the rise)",
        "results": results,
        "pass": all(r["pass"] for r in results),
        "scope": "the nonlinear conduction of the solver and the Elmer table lookup against exact solutions; not f02's property tables",
    }
    Path(evidence).write_text(json.dumps(document, indent=1) + "\n")
    return document


if __name__ == "__main__":
    main(*sys.argv[1:4])
