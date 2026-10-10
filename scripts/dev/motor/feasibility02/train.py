"""Motor 10p/12s public TRAIN, stage 1 (OWNER-MOTOR-TRAIN-GRANT-01).

    python -m scripts.dev.motor.feasibility02.train --sidecar SIDECAR --out PLAN [--size 128]

Seeded Latin hypercube over the registered six-coordinate grammar; a point is
kept only if it is geometrically valid and at normalised distance >= 0.10
from every panel/study design in the sidecar. Each geometry gets the panel's
11-solve bundle (J 0; J 10 and J 15 at gamma -10/-5/0/+5/+10) with the flux
observers, so 0/2/4-deg step skew is reconstructed exactly as the panel.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.motor.feasibility02 import topology as tp

KEYS = list(tp.GRAMMAR)
TOPO = tp.TOPOLOGIES["10p12s"]
BUNDLE = [(0.0, 0.0)] + [
    (j, g) for j in (10.0, 15.0) for g in (-10.0, -5.0, 0.0, 5.0, 10.0)
]
SEED, MIN_DIST = 1010, 0.10


def _u(d):
    return [
        (d[k] - tp.GRAMMAR[k][0]) / (tp.GRAMMAR[k][1] - tp.GRAMMAR[k][0]) for k in KEYS
    ]


def draw(existing, size):
    rng = np.random.default_rng(SEED)
    kept, batch = [], 0
    while len(kept) < size:
        batch += 1
        m = size * 4  # one LHS block per round; keep valid, far points in order
        lhs = (
            np.argsort(rng.random((len(KEYS), m)), axis=1).T
            + rng.random((m, len(KEYS)))
        ) / m
        for u in lhs:
            d = {
                k: tp.GRAMMAR[k][0]
                + float(u[i]) * (tp.GRAMMAR[k][1] - tp.GRAMMAR[k][0])
                for i, k in enumerate(KEYS)
            }
            if tp.validity(TOPO, d):
                continue
            if (
                min(math.dist(u, e) for e in existing + [_u(x) for x in kept])
                < MIN_DIST
            ):
                continue
            kept.append(d)
            if len(kept) == size:
                break
    return kept, batch


def main(argv=None):
    parser = argparse.ArgumentParser(prog="motor train")
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--size", type=int, default=128)
    args = parser.parse_args(argv)
    existing = [
        _u(v["grammar"])
        for v in json.loads(args.sidecar.read_text())["designs"].values()
    ]
    designs, rounds = draw(existing, args.size)
    cases = []
    for n, d in enumerate(designs):
        for j, g in BUNDLE:
            cases.append({"case_id": f"mtrain-t{n:03d}-j{j:g}g{g:g}", "topology": "10p12s", "design": d,
                          "j_a_mm2": j, "gamma_deg": g, "options": {"flux_observers": True}})  # fmt: skip
    body = {"batch": "motor-10p12s-train-stage1", "role": "PUBLIC_TRAIN", "seed": SEED, "min_dist": MIN_DIST,
            "existing_designs": len(existing), "lhs_rounds": rounds, "cases": cases}  # fmt: skip
    text = json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n"
    args.out.write_text(text)
    print(
        json.dumps(
            {
                "geometries": len(designs),
                "cases": len(cases),
                "plan_sha256": hashlib.sha256(text.encode()).hexdigest(),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
