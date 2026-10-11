"""PROVISIONAL code verification (MMS) for the pinned PyBaMM truth stack's
particle diffusion sub-model (spherical finite volumes, as the DFN's
particles use). Owner-approved process step 2026-10-10; replace with
packets Codex's spec when it lands.

    python -m scripts.dev.battery.pybamm_mms OUT.json    (inside the truth image)

dc/dt = D (1/r^2) d/dr (r^2 dc/dr) + S on r in (0, 1), D = 1, zero flux at
both ends, exact c = 1 + exp(-t) cos(pi r), so
S = -exp(-t) cos(pi r) + D pi exp(-t) (2 sin(pi r)/r + pi cos(pi r)).
Errors at t = 0.5 at the cell centres for 10..160 cells; expected order 2;
package check: finest-pair order within 0.3 of 2.
"""

from __future__ import annotations

import itertools
import json
import math
import sys

import numpy as np
import pybamm

EXPECTED, TOL, T_END = 2.0, 0.3, 0.5


def solve(n):
    model = pybamm.BaseModel()
    r = pybamm.SpatialVariable(
        "r_n", domain=["negative particle"], coord_sys="spherical polar"
    )
    c = pybamm.Variable("c", domain="negative particle")
    t = pybamm.t
    source = -pybamm.exp(-t) * pybamm.cos(np.pi * r) + np.pi * pybamm.exp(-t) * (
        2 * pybamm.sin(np.pi * r) / r + np.pi * pybamm.cos(np.pi * r)
    )
    model.rhs = {c: pybamm.div(pybamm.grad(c)) + source}
    model.boundary_conditions = {
        c: {
            "left": (pybamm.Scalar(0), "Neumann"),
            "right": (pybamm.Scalar(0), "Neumann"),
        }
    }
    model.initial_conditions = {c: 1 + pybamm.cos(np.pi * r)}
    model.variables = {"c": c}
    geometry = {
        "negative particle": {r: {"min": pybamm.Scalar(0), "max": pybamm.Scalar(1)}}
    }
    mesh = pybamm.Mesh(geometry, {"negative particle": pybamm.Uniform1DSubMesh}, {r: n})
    pybamm.Discretisation(
        mesh, {"negative particle": pybamm.FiniteVolume()}
    ).process_model(model)
    sol = pybamm.CasadiSolver(rtol=1e-11, atol=1e-13, mode="fast").solve(
        model, np.linspace(0, T_END, 11)
    )
    nodes = mesh["negative particle"].nodes
    num = sol["c"].entries[:, -1]
    err = num - (1 + math.exp(-T_END) * np.cos(np.pi * nodes))
    return float(np.max(np.abs(err))), float(np.sqrt(np.mean(err**2)))


def main(out):
    rows = [(n, *solve(n)) for n in (10, 20, 40, 80, 160)]
    orders = [{"pair": f"{a[0]}->{b[0]}", "max": math.log2(a[1] / b[1]), "rms": math.log2(a[2] / b[2])}
              for a, b in itertools.pairwise(rows)]  # fmt: skip
    ok = all(abs(orders[-1][k] - EXPECTED) <= TOL for k in ("max", "rms"))
    doc = {"schema": "carbon.reference-package.mms.v1", "status": "PROVISIONAL (self-derived; replace with packets Codex's spec)",
           "solver": f"PyBaMM {pybamm.__version__} FiniteVolume, spherical particle, CasadiSolver",
           "solution": "c = 1 + exp(-t) cos(pi r), D = 1, zero flux, t_end 0.5",
           "errors": [{"cells": n, "max": m, "rms": s} for n, m, s in rows], "orders": orders,
           "expected_order": EXPECTED, "tolerance": TOL, "pass": ok,
           "scope": "code verification of the particle diffusion discretisation only; not the DFN couplings or electrochemistry"}  # fmt: skip
    with open(out, "w") as handle:
        handle.write(json.dumps(doc, indent=1) + "\n")
    print(json.dumps({"orders": orders[-1], "pass": ok, "pybamm": pybamm.__version__}))


if __name__ == "__main__":
    main(sys.argv[1])
