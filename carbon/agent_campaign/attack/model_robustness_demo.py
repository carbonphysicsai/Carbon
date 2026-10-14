"""One-command synthetic probe replay. Never trains/loads a participant model."""

from __future__ import annotations

import json

from . import engine
from .model_robustness import (
    FAMILIES,
    Boundary,
    Policy,
    Witness,
    corrupt,
    deform,
    grid,
    probe,
)


def fixture_predict(payload):
    """Analytic toy nodal field, with honest unsupported-input refusal."""
    nodes, cells = payload["nodes"], payload["cells"]
    invalid = len(nodes) > 40 or any(
        not (0 <= x <= 1.2 and 0 <= y <= 1.2) for x, y in nodes
    )
    for cell in cells:
        if any(i < 0 or i >= len(nodes) for i in cell):
            invalid = True
            continue
        a, b, c = (nodes[i] for i in cell)
        if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) <= 0:
            invalid = True
    if invalid:
        return {"status": "REFUSE", "values": [], "reason": "toy_unsupported"}
    return {"status": "PREDICT", "values": [x + 2 * y for x, y in nodes], "reason": ""}


def bad_predict(payload):
    """Confident extrapolator / mesh-blind toy; deliberately wrong in supported scope too."""
    return {
        "status": "PREDICT",
        "values": [100.0] * len(payload["nodes"]),
        "reason": "",
    }


def fixture_boundary(predict=fixture_predict, name="correct-toy"):
    return Boundary(
        "synthetic-triangle-field",
        engine.digest(name),
        engine.digest("toy-runtime-v1"),
        frozenset(FAMILIES),
        predict,
        "SYNTHETIC_FIXTURE",
    )


def fixture_witness(mesh):
    return Witness(
        mesh.identity,
        engine.digest("toy-analytic-reference-v1"),
        tuple(x + 2 * y for x, y in mesh.nodes),
        "synthetic-unit",
    )


def fixture_policy():
    return Policy(
        "synthetic-triangle-field",
        "FIXTURE_ONLY_not_scientific_policy",
        (0.0, 1.2, 0.0, 1.2),
        40,
        0.05,
        0.0,
        "synthetic-unit",
    )


def run_fixture():
    base = grid(2)
    attacks = (
        (FAMILIES[0], deform(base, stretch=1.1, shear=0.0), True),
        (FAMILIES[0], deform(base, stretch=1.0, shear=1.0), False),
        (FAMILIES[1], grid(4, irregularity=0.2), True),
        (FAMILIES[1], grid(8), False),
        *(
            (FAMILIES[1], corrupt(base, kind), False)
            for kind in ("degenerate", "inverted", "invalid_index")
        ),
    )
    return [
        probe(
            family,
            fixture_policy(),
            fixture_boundary(),
            baseline=base,
            attack=mesh,
            negative=fixture_boundary(bad_predict, "bad-toy"),
            control_witness=fixture_witness(base),
            attack_witness=fixture_witness(mesh) if supported else None,
        )
        for family, mesh, supported in attacks
    ]


def main():
    print(
        json.dumps(
            {
                "basis": "SYNTHETIC_FIXTURE_NOT_TRAINED_MODEL_EVIDENCE",
                "records": run_fixture(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
