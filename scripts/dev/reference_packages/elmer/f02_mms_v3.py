"""Code verification of the NONLINEAR heat solve of deck v3 by the method of manufactured solutions (Burst Thermal 3.0, T2).

    python3 f02_mms_v3.py IMAGE OUTDIR EVIDENCE.json

As the 2.5 MMS (`mms_heat.py`), on the unit cube, rho = 1, but with temperature-dependent properties of the registered
FORM of the v3 deck, k(T) = k0 (1 + beta (T - T0)) and c_p(T) = cp0 (1 + gamma (T - T0)):

    T = T0 + S(x, y, z) cos(2 pi t),   S = sin(pi x) sin(pi y) sin(pi z)      (T = T0 on every face)

The source (per unit mass) follows from the PDE rho c_p(T) T_t - div(k(T) grad T) = f, derived symbolically (sympy) and
written as a MATC body force; `source_matc` is the closed form, and the test suite checks it against the sympy derivation
at random points. The properties are given to Elmer as the same smooth functions (a MATC function of Temperature), so the
run verifies the code's discretisation AND its nonlinear (Picard) iteration, with the NUMERICAL settings of deck v3
(`f02_deck_v3.NONLINEAR_*`, recorded here, never tuned).

- space: N = 8, 16, 32 elements per side at dt = 1/512; the observed order from max and RMS nodal errors, expected 2;
- time: N = 16, dt = 1/8, 1/16, 1/32 against the same mesh at dt = 1/256, expected 2;
- acceptance (registered A1): every observed order within [1.7, 2.3] on the finest pair;
- the run is REFERENCE_INVALID when any time step reaches the iteration limit without converging (`f02_deck_v3`).

BETA and GAMMA are TEST values, labelled: they make k and c_p vary about 30 % over the test range (T - T0 in [-1, 1],
k0 = cp0 = 1). They are not material values. This verifies the discretisation and the nonlinear iteration, not f02's
physics, its property tables or reference adequacy.
"""

from __future__ import annotations

import itertools
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f02_deck_v3 as deck
import mms_heat

T_END = mms_heat.T_END  # 0.375: the registered end time of the 2.5 MMS
T0, K0, CP0 = 1.0, 1.0, 1.0
BETA, GAMMA = (
    0.15,
    0.15,
)  # TEST values: about 30 % variation of k and c_p over T - T0 in [-1, 1]
ORDER_BAND = (1.7, 2.3)
TEST_ONLY = "TEST_ONLY"

_S = "sin(pi*tx(0))*sin(pi*tx(1))*sin(pi*tx(2))"


def source_matc():
    """The MATC body force (per unit mass, rho = 1), in closed form:

    f = cp(T) T_t - (k'(T) |grad T|^2 + k(T) lap T)
    T_t = -2 pi S sin(2 pi t),  lap T = -3 pi^2 S cos(2 pi t),
    |grad T|^2 = pi^2 cos^2(2 pi t) (cx^2 sy^2 sz^2 + sx^2 cy^2 sz^2 + sx^2 sy^2 cz^2).
    """
    sx, sy, sz = (f"sin(pi*tx({i}))" for i in range(3))
    cx, cy, cz = (f"cos(pi*tx({i}))" for i in range(3))
    c, n = "cos(2*pi*tx(3))", "sin(2*pi*tx(3))"
    u = f"({_S})*{c}"
    grad2 = f"pi^2*{c}^2*(({cx})^2*({sy})^2*({sz})^2+({sx})^2*({cy})^2*({sz})^2+({sx})^2*({sy})^2*({cz})^2)"
    return (
        f"{CP0}*(1+{GAMMA}*{u})*(-2*pi*({_S})*{n})"
        f"-({K0 * BETA}*{grad2}+{K0}*(1+{BETA}*{u})*(-3*pi^2*({_S})*{c}))"
    )


def exact(p, t=T_END):
    x, y, z = p
    return T0 + math.sin(math.pi * x) * math.sin(math.pi * y) * math.sin(
        math.pi * z
    ) * math.cos(2 * math.pi * t)


def sif_text(dt, steps):
    """The solver input: deck v3's nonlinear settings, the manufactured source, T = T0 on every face."""
    return f"""! f02 nonlinear MMS (test-only properties, tables {TEST_ONLY}); nonlinear max iterations {deck.NONLINEAR_MAX_ITERATIONS}, tolerance {deck.NONLINEAR_TOLERANCE!r}
Header
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
  Heat Conductivity = Variable Temperature
    Real MATC "{K0}*(1+{BETA}*(tx-{T0}))"
  Heat Capacity = Variable Temperature
    Real MATC "{CP0}*(1+{GAMMA}*(tx-{T0}))"
  Density = 1.0
End
Body Force 1
  Heat Source = Variable Coordinate 1, Coordinate 2, Coordinate 3, Time
    Real MATC "{source_matc()}"
End
Initial Condition 1
  Temperature = Variable Coordinate 1, Coordinate 2, Coordinate 3
    Real MATC "{T0}+{_S}"
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
  Nonlinear System Max Iterations = {deck.NONLINEAR_MAX_ITERATIONS}
  Nonlinear System Convergence Tolerance = {deck.NONLINEAR_TOLERANCE!r}
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
  Temperature = {T0}
End
"""


def run(image, out, n, dt):
    """One solve in the pinned image; ``(field, wall, iterations)`` with the nonlinear iterations read from the log."""
    d = Path(out) / f"n{n}-dt{1 / dt:g}"
    mms_heat.write_mesh(d, n)
    (d / "case.sif").write_text(sif_text(dt, round(T_END / dt)))
    (d / "ELMERSOLVER_STARTINFO").write_text("case.sif\n1\n")
    t0 = time.monotonic()
    code = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "--read-only", "--tmpfs", "/tmp", "--cpus", "1",
         "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{d.resolve()}:/case", "-w", "/case", image,
         "bash", "-c", "ElmerSolver case.sif > solver.log 2>&1"],
        check=False,
    ).returncode  # fmt: skip
    wall = time.monotonic() - t0
    if code != 0:
        raise RuntimeError(f"{d.name}: ElmerSolver exit {code}")
    status = log_status(d / "solver.log")
    xyz, temp, _, _ = mms_heat.deck._vtu_arrays(d)
    field = {
        (round(x, 9), round(y, 9), round(z, 9)): t
        for (x, y, z), t in zip(xyz, temp, strict=True)
    }
    return field, wall, status


_ITERATION = re.compile(r"ITER=(\d+)\)\s*\(NRM,RELC\):\s*\(\s*(\S+)\s+(\S+)\s*\)")


def log_status(path):
    """``{"max_iterations_seen", "steps", "invalid"}`` from a solver log: a step whose last iteration is the limit with a
    relative change above the tolerance makes the run REFERENCE_INVALID (as `f02_deck_v3.reference_status`).
    """
    steps, last = [], None
    for line in Path(path).read_text(errors="replace").splitlines():
        found = _ITERATION.search(line)
        if found is None:
            continue
        iteration = int(found.group(1))
        if iteration == 1 and last is not None:
            steps.append(last)
        last = (iteration, float(found.group(3)))
    if last is not None:
        steps.append(last)
    invalid = (not steps) or any(
        n >= deck.NONLINEAR_MAX_ITERATIONS and change > deck.NONLINEAR_TOLERANCE
        for n, change in steps
    )
    return {
        "max_iterations_seen": max((n for n, _ in steps), default=0),
        "steps": len(steps),
        "invalid": invalid,
    }


def orders(rows):
    """Observed orders between consecutive ``(label, max, rms)`` rows (each refinement halves the step or size)."""
    return [
        {"pair": f"{a[0]}->{b[0]}", "max": mms_heat.order(a[1], b[1]), "rms": mms_heat.order(a[2], b[2])}
        for a, b in itertools.pairwise(rows)
    ]  # fmt: skip


def accepted(space_orders, time_orders, band=ORDER_BAND):
    """Registered A1: the finest pair's max and RMS orders, in space and in time, all within ``band``."""
    low, high = band
    return all(
        low <= o[k] <= high
        for o in (space_orders[-1], time_orders[-1])
        for k in ("max", "rms")
    )


def main(image, out, evidence):
    space, time_rows, walls, invalid = [], [], {}, []
    for n in (8, 16, 32):
        field, walls[f"space n{n}"], status = run(image, out, n, 1 / 512)
        invalid += [status["invalid"]]
        space.append((n, *mms_heat.norms([t - exact(p) for p, t in field.items()])))
    ref, walls["time ref"], status = run(image, out, 16, 1 / 256)
    invalid += [status["invalid"]]
    iterations = [status["max_iterations_seen"]]
    for inv in (8, 16, 32):
        field, walls[f"time dt1/{inv}"], status = run(image, out, 16, 1 / inv)
        invalid += [status["invalid"]]
        iterations += [status["max_iterations_seen"]]
        time_rows.append(
            (f"1/{inv}", *mms_heat.norms([t - ref[p] for p, t in field.items()]))
        )
    space_orders = orders([(f"{n}", m, r) for n, m, r in space])
    time_orders = orders(time_rows)
    passed = accepted(space_orders, time_orders) and not any(invalid)
    doc = {
        "schema": "carbon.reference-package.mms-nonlinear.v1",
        "image": image,
        "solver": "Elmer HeatSolver, hex808, BDF2, nonlinear (Picard) iteration",
        "solution": f"T = {T0} + sin(pi x) sin(pi y) sin(pi z) cos(2 pi t), unit cube, rho = 1, t_end {T_END}",
        "properties": {"k": f"{K0}(1+{BETA}(T-{T0}))", "cp": f"{CP0}(1+{GAMMA}(T-{T0}))", "label": TEST_ONLY},
        "nonlinear_settings": {"max_iterations": deck.NONLINEAR_MAX_ITERATIONS, "tolerance": deck.NONLINEAR_TOLERANCE},
        "max_nonlinear_iterations_seen": max(iterations),
        "space_errors": [{"n": n, "max": m, "rms": r} for n, m, r in space],
        "space_orders": space_orders,
        "time_errors_vs_dt1_256": [{"dt": d, "max": m, "rms": r} for d, m, r in time_rows],
        "time_orders": time_orders,
        "expected_band": list(ORDER_BAND),
        "reference_invalid": any(invalid),
        "pass": passed,
        "wall_s": {k: round(v, 1) for k, v in walls.items()},
        "scope": "code verification only (discretisation order and the nonlinear iteration); not f02 physics, not its property tables, not reference adequacy",
    }  # fmt: skip
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
