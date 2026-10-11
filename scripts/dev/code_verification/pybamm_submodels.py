"""Data Collection runs this ONLY inside the existing pinned battery overlay.

No DFN experiment, bank material or customer parameter fitting. Particle MMS
and lumped-heat ODE verify two sub-model paths, not the complete battery model.
"""

import argparse
import hashlib
import json
import math
import os
from itertools import pairwise
from pathlib import Path

os.environ.setdefault("PYBAMM_DISABLE_TELEMETRY", "true")


def run_particle(n):
    import numpy as np
    import pybamm as p

    if p.__version__ != "26.8.0.0":
        raise RuntimeError("wrong PyBaMM version; re-pin prospectively")
    r = p.SpatialVariable(
        "r", domain=["negative particle"], coord_sys="spherical polar"
    )
    c = p.Variable("c", domain=["negative particle"])
    model = p.BaseModel()
    model.rhs = {c: p.div(p.grad(c)) - p.exp(-p.t) * (7 + 21 * r**2 + r**4)}
    model.initial_conditions = {c: 1 + r**2 + r**4}
    model.boundary_conditions = {
        c: {"left": (p.Scalar(0), "Neumann"), "right": (6 * p.exp(-p.t), "Neumann")}
    }
    model.variables = {"c": c}
    geometry = {"negative particle": {r: {"min": 0, "max": 1}}}
    mesh = p.Mesh(geometry, {"negative particle": p.Uniform1DSubMesh}, {r: n})
    p.Discretisation(mesh, {"negative particle": p.FiniteVolume()}).process_model(model)
    solver = p.IDAKLUSolver(rtol=1e-10, atol=1e-12)
    solution = solver.solve(model, [0, 0.2])
    sub = mesh["negative particle"]
    edges = sub.edges
    values = np.asarray(solution["c"].entries)[:, -1].tolist()
    return {
        "h": 1 / n,
        "t": 0.2,
        "points": [[float(x)] for x in sub.nodes],
        "values": values,
        "weights": [(float(b) ** 3 - float(a) ** 3) / 3 for a, b in pairwise(edges)],
    }


def run_heat():
    import pybamm as p

    theta = p.Variable("theta")
    model = p.BaseModel()
    model.rhs = {theta: 1 - theta}
    model.initial_conditions = {theta: p.Scalar(0)}
    model.variables = {"theta": theta}
    p.Discretisation().process_model(model)
    rows = []
    for tol in (1e-4, 1e-6, 1e-8):
        solution = p.IDAKLUSolver(rtol=tol, atol=tol / 100).solve(model, [0, 1])
        rows.append(
            {
                "rtol": tol,
                "value": float(solution["theta"].entries[-1]),
                "absolute_error": abs(
                    float(solution["theta"].entries[-1]) - (1 - math.exp(-1))
                ),
            }
        )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-digest", required=True)
    parser.add_argument("--spec-digest", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # DC records actual immutable Docker image inspection outside this worker.
    # Supplied labels alone never attest which image executed it.
    rows = [run_particle(n) for n in (20, 40, 80)]
    raw = [
        hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest() for r in rows
    ]
    report = {
        "schema": "carbon.code-verification.fields.v1",
        "scope": "PUBLIC_DEVELOPMENT",
        "kind": "pybamm-particle",
        "family": "battery-v3",
        "image_digest": args.image_digest,
        "spec_digest": args.spec_digest,
        "adapter_digest": "sha256:"
        + hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "rows": rows,
        "raw_outputs": ["sha256:" + v for v in raw],
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    args.output.with_suffix(".heat.json").write_text(
        json.dumps(
            {
                "image_digest": args.image_digest,
                "submodel": "lumped-heat",
                "exact": "1-exp(-t)",
                "rows": run_heat(),
                "accepted_pass": None,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
